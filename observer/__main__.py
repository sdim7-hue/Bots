"""CLI наблюдателя.

  python -m observer collect-once   — собрать снимок доски (>=1 проект), без мутаций.
  python -m observer notify-dry     — сухой прогон: вывести события в консоль.
  python -m observer serve          — поднять дашборд (localhost).
  python -m observer run            — цикл: collect -> detect -> notify -> sleep.

Реестр проектов — observer/projects.json. Секреты каналов — только из ENV.
Пакет строго read-only: доску не меняет, ботов не запускает.
"""

from __future__ import annotations

import argparse
import sys
import time

from . import notifier, registry
from .channels import active_channels
from .collector import DEFAULT_DB_PATH, StateStore, collect_project


def _load_projects() -> list:
    try:
        return registry.load_projects()
    except registry.RegistryError as exc:
        print(f"Ошибка реестра: {exc}", file=sys.stderr)
        raise SystemExit(2)


def _collect_all(projects: list) -> list:
    """Собирает снимки по всем проектам. Сбой одного проекта не валит остальные."""
    snapshots: list = []
    for project in projects:
        try:
            project_snaps = collect_project(project)
        except registry.RegistryError as exc:
            print(f"Пропуск {project.name}: {exc}", file=sys.stderr)
            continue
        except registry.client_errors() as exc:
            print(f"Пропуск {project.name}: ошибка API: {exc}", file=sys.stderr)
            continue
        print(f"{project.name}: {len(project_snaps)} задач")
        snapshots.extend(project_snaps)
    return snapshots


def cmd_collect_once() -> int:
    projects = _load_projects()
    snapshots = _collect_all(projects)
    store = StateStore()
    try:
        for snap in snapshots:
            store.upsert_snapshot(snap)
    finally:
        store.close()
    print(f"Снимок записан: {len(snapshots)} задач в {DEFAULT_DB_PATH}")
    return 0


def cmd_notify_dry(include_done: bool) -> int:
    projects = _load_projects()
    snapshots = _collect_all(projects)
    store = StateStore()
    try:
        prev = store.load_snapshots()
    finally:
        store.close()

    events = notifier.detect(prev, snapshots, include_done=include_done)
    channels = active_channels(force_console=True)
    # Dry-режим: без store -> без дедупа и без записи журнала/снимков.
    sent = notifier.dispatch(events, [c for c in channels if c.name == "console"])
    print(f"notify-dry: {sent} событий (снимок и журнал НЕ изменены)")
    return 0


def cmd_serve(host: str, port: int) -> int:
    from .dashboard import serve

    serve(host=host, port=port)
    return 0


def cmd_run(interval: int, include_done: bool) -> int:
    projects = _load_projects()
    channels = active_channels()
    print("Активные каналы: " + ", ".join(c.name for c in channels))
    store = StateStore()
    try:
        while True:
            prev = store.load_snapshots()
            snapshots = _collect_all(projects)
            events = notifier.detect(prev, snapshots, include_done=include_done)
            sent = notifier.dispatch(events, channels, store=store)
            for snap in snapshots:
                store.upsert_snapshot(snap)
            print(f"[run] {len(snapshots)} задач, {sent} новых уведомлений; "
                  f"сон {interval}s")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nОстановлен.")
        return 0
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="observer",
                                     description="Bots observer & notifier (read-only)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("collect-once", help="собрать снимок доски (без мутаций)")

    p_dry = sub.add_parser("notify-dry", help="сухой прогон: события в консоль")
    p_dry.add_argument("--include-done", action="store_true",
                       help="включить информационные события done")

    p_serve = sub.add_parser("serve", help="поднять дашборд (localhost)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8787)

    p_run = sub.add_parser("run", help="цикл collect->detect->notify->sleep")
    p_run.add_argument("--interval", type=int, default=120,
                       help="пауза между циклами, секунды (по умолчанию 120)")
    p_run.add_argument("--include-done", action="store_true",
                       help="включить информационные события done")

    args = parser.parse_args(argv)

    if args.command == "collect-once":
        return cmd_collect_once()
    if args.command == "notify-dry":
        return cmd_notify_dry(args.include_done)
    if args.command == "serve":
        return cmd_serve(args.host, args.port)
    if args.command == "run":
        return cmd_run(args.interval, args.include_done)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
