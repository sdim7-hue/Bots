"""CLI оркестратора.

  python -m orchestrator list      — показать очередь задач со статусом queued.
  python -m orchestrator run-bot   — вручную запустить бота с брифом (проверка адаптера).

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

    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list()
    if args.command == "run-bot":
        return cmd_run_bot(args.message, args.file, args.timeout)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
