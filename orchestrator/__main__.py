"""CLI оркестратора.

  python -m orchestrator list      — показать очередь задач со статусом queued.
  python -m orchestrator run-bot   — вручную запустить бота с брифом (проверка адаптера).
  python -m orchestrator run-next  — взять старейшую queued, прогнать бота, двинуть статус.

Бэкенд очереди (GitHub/Forgejo) и токен — см. config.py. Токен не печатается.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .adapters.local import run_bot
from .core import StateStore, Task

# Дефолтный таймаут ручного запуска бота, секунды.
_RUN_BOT_TIMEOUT = 600

# Максимальная длина вывода бота, попадающего в комментарий issue.
_COMMENT_OUTPUT_LIMIT = 1500


def cmd_list() -> int:
    try:
        client = config.make_client()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    try:
        issues = client.list_issues_by_label("status:queued")
    except config.client_errors() as exc:
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
        result = run_bot(brief, cwd=(Path(config.CHECKOUT) if config.CHECKOUT else Path.cwd()), timeout=timeout)
    except TimeoutError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(result.output, end="" if result.output.endswith("\n") else "\n")
    print(f"exit_code={result.exit_code} ok={result.ok} subtype={result.subtype}")
    return 0 if result.ok else 1


def _bot_comment(new_status: str, result) -> str:
    """Формирует комментарий с итогом бота для ревью (см. L52)."""
    out = (result.output or "").strip()
    if len(out) > _COMMENT_OUTPUT_LIMIT:
        out = out[:_COMMENT_OUTPUT_LIMIT] + "\n…(вывод обрезан)"
    meta = f"exit_code={result.exit_code}, ok={result.ok}"
    if result.subtype:
        meta += f", subtype={result.subtype}"
    if result.cost_usd is not None:
        meta += f", cost=${result.cost_usd:.4f}"
    if result.num_turns is not None:
        meta += f", turns={result.num_turns}"
    return (
        f"Автоцикл оркестратора → status:{new_status} ({meta}).\n\n"
        f"Вывод бота:\n\n{out or '(пусто)'}"
    )


def _finalize(client, store, task, new_status, result, note) -> None:
    """Фиксирует итог: меняет статус, обновляет SQLite, пишет комментарий.

    Сбои API на этом этапе не валят процесс — бот уже отработал; ошибки лишь
    предупреждаем, итог в любом случае пишем в локальное состояние.
    """
    try:
        client.set_status(task.number, new_status)
    except config.client_errors() as exc:
        print(f"Предупреждение: не удалось сменить статус на {new_status}: {exc}",
              file=sys.stderr)
    else:
        task.status = new_status
    store.upsert(task)

    if result is not None:
        comment = _bot_comment(new_status, result)
    else:
        comment = f"Автоцикл оркестратора: {note} → status:{new_status}."
    try:
        client.add_comment(task.number, comment)
    except config.client_errors() as exc:
        print(f"Предупреждение: не удалось добавить комментарий: {exc}",
              file=sys.stderr)


def cmd_run_next(timeout: int) -> int:
    try:
        client = config.make_client()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    store = StateStore(config.STATE_DB)
    try:
        try:
            issues = client.list_issues_by_label("status:queued")
        except config.client_errors() as exc:
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
        except config.client_errors() as exc:
            print(f"Ошибка смены статуса на in-progress: {exc}", file=sys.stderr)
            return 1
        task.status = "in-progress"
        store.upsert(task)

        # Бриф — тело issue как есть (фолбэк на заголовок, если тело пустое).
        brief = issue.get("body") or task.title

        try:
            result = run_bot(brief, cwd=(Path(config.CHECKOUT) if config.CHECKOUT else Path.cwd()), timeout=timeout)
        except TimeoutError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            _finalize(client, store, task, new_status="failed", result=None,
                      note="бот не завершился за отведённое время (timeout)")
            return 1

        new_status = "review" if result.ok else "failed"
        _finalize(client, store, task, new_status=new_status, result=result, note=None)
        extra = f", subtype={result.subtype}" if result.subtype else ""
        cost = f", cost=${result.cost_usd:.4f}" if result.cost_usd is not None else ""
        print(f"#{task.number}: exit_code={result.exit_code} ok={result.ok} "
              f"→ status:{new_status}{extra}{cost}")
        return 0 if result.ok else 1
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
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
