"""CLI оркестратора.

  python -m orchestrator list   — показать очередь задач со статусом queued.

Токен берётся из окружения или конфига Claude (см. config.py). Не печатается.
"""

from __future__ import annotations

import argparse
import sys

from . import config
from .core import StateStore, Task
from .github_client import GitHubClient, GitHubError


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrator", description="Bots orchestrator")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="показать очередь queued")
    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
