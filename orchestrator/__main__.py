"""CLI оркестратора.

  python -m orchestrator list      — показать очередь задач со статусом queued.
  python -m orchestrator run-bot   — вручную запустить бота с брифом (проверка адаптера).
  python -m orchestrator run-next  — взять старейшую queued, прогнать бота, двинуть статус.

Токен берётся из окружения или конфига Claude (см. config.py). Не печатается.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .adapters.local import run_bot
from .core import StateStore, Task
from .github_client import GitHubClient, GitHubError

# Дефолтный таймаут ручного запуска бота, секунды.
_RUN_BOT_TIMEOUT = 600


def cmd_list() -> int:
    try:
        token = config.get_token()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    client = GitHubClient(token, config.OWNER, config.REPO)
    try:
        issues = client.list_issues_by_label("status:queued")
    except GitHubError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    store = StateStore(config.STATE_DB)
    tasks = [Task.from_issue(issue) for issue in issues]
    for task in tasks:
        store.upsert(task)
    store.close()

    header = f"Очередь queued ({config.OWNER}/{config.REPO}): {len(tasks)} задач"
    print(header)
    print("-" * len(header))
    for task in sorted(tasks, key=lambda t: t.number):
        type_part = f" [{task.type}]" if task.type else ""
        print(f"  #{task.number}{type_part} {task.title}")
    return 0


def cmd_run_bot(message: str | None, file: str | None, timeout: int) -> int:
    if file:
        try:
            brief = Path(file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Ошибка: не удалось прочитать файл брифа: {exc}", file=sys.stderr)
            return 2
    elif message is not None:
        brief = message
    else:
        print("Ошибка: укажи --message или --file", file=sys.stderr)
        return 2

    try:
        result = run_bot(brief, cwd=Path.cwd(), timeout=timeout)
    except TimeoutError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(result.output, end="" if result.output.endswith("\n") else "\n")
    print(f"exit_code={result.exit_code}")
    return 0 if result.ok else 1


def _finalize(client, store, task, new_status, exit_code, note) -> None:
    """Фиксирует итог: меняет статус, обновляет SQLite, пишет комментарий.

    Сбои API на этом этапе не валят процесс — бот уже отработал; ошибки лишь
    предупреждаем, итог в любом случае пишем в локальное состояние.
    """
    try:
        client.set_status(task.number, new_status)
    except GitHubError as exc:
        print(f"Предупреждение: не удалось сменить статус на {new_status}: {exc}",
              file=sys.stderr)
    else:
        task.status = new_status
    store.upsert(task)

    if exit_code is not None:
        comment = (f"Автоцикл оркестратора: бот завершился с exit_code={exit_code} "
                   f"→ status:{new_status}.")
    else:
        comment = f"Автоцикл оркестратора: {note} → status:{new_status}."
    try:
        client.add_comment(task.number, comment)
    except GitHubError as exc:
        print(f"Предупреждение: не удалось добавить комментарий: {exc}",
              file=sys.stderr)


def cmd_run_next(timeout: int) -> int:
    try:
        token = config.get_token()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    client = GitHubClient(token, config.OWNER, config.REPO)
    store = StateStore(config.STATE_DB)
    try:
        try:
            issues = client.list_issues_by_label("status:queued")
        except GitHubError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1

        if not issues:
            print("Очередь queued пуста — нечего запускать.")
            return 0

        # Старейшая задача — с наименьшим номером issue.
        issue = min(issues, key=lambda it: it["number"])
        task = Task.from_issue(issue)
        print(f"Беру #{task.number}: {task.title}")

        # queued -> in-progress
        try:
            client.set_status(task.number, "in-progress")
        except GitHubError as exc:
            print(f"Ошибка смены статуса на in-progress: {exc}", file=sys.stderr)
            return 1
        task.status = "in-progress"
        store.upsert(task)

        # Бриф — тело issue как есть (фолбэк на заголовок, если тело пустое).
        brief = issue.get("body") or task.title

        try:
            result = run_bot(brief, cwd=Path.cwd(), timeout=timeout)
        except TimeoutError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            _finalize(client, store, task, new_status="failed", exit_code=None,
                      note="бот не завершился за отведённое время (timeout)")
            return 1

        new_status = "review" if result.ok else "failed"
        _finalize(client, store, task, new_status=new_status,
                  exit_code=result.exit_code, note=None)
        print(f"#{task.number}: exit_code={result.exit_code} → status:{new_status}")
        return 0 if result.ok else 1
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrator", description="Bots orchestrator")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="показать очередь queued")

    p_run = sub.add_parser("run-bot", help="вручную запустить бота с брифом (проверка адаптера)")
    src = p_run.add_mutually_exclusive_group()
    src.add_argument("--message", help="бриф текстом")
    src.add_argument("--file", help="прочитать бриф из файла")
    p_run.add_argument(
        "--timeout", type=int, default=_RUN_BOT_TIMEOUT,
        help=f"таймаут запуска, секунды (по умолчанию {_RUN_BOT_TIMEOUT})",
    )

    p_next = sub.add_parser(
        "run-next",
        help="взять старейшую queued, прогнать бота, двинуть статус (in-progress→review/failed)",
    )
    p_next.add_argument(
        "--timeout", type=int, default=_RUN_BOT_TIMEOUT,
        help=f"таймаут запуска бота, секунды (по умолчанию {_RUN_BOT_TIMEOUT})",
    )

    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list()
    if args.command == "run-bot":
        return cmd_run_bot(args.message, args.file, args.timeout)
    if args.command == "run-next":
        return cmd_run_next(args.timeout)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
