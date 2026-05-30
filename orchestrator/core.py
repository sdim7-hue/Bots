"""Ядро: модель задачи и локальное состояние (SQLite).

OS-агностично. Состояние — кэш очереди: что оркестратор видел и когда.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Префиксы меток (совпадают с docs/labels.md).
_STATUS_PREFIX = "status:"
_TYPE_PREFIX = "type:"


@dataclass
class Task:
    number: int
    title: str
    status: str | None
    type: str | None
    labels: list[str]

    @classmethod
    def from_issue(cls, issue: dict) -> "Task":
        labels = [lbl["name"] for lbl in issue.get("labels", [])]
        status = next(
            (l[len(_STATUS_PREFIX):] for l in labels if l.startswith(_STATUS_PREFIX)),
            None,
        )
        type_ = next(
            (l[len(_TYPE_PREFIX):] for l in labels if l.startswith(_TYPE_PREFIX)),
            None,
        )
        return cls(
            number=issue["number"],
            title=issue.get("title", ""),
            status=status,
            type=type_,
            labels=labels,
        )


class StateStore:
    """Локальный кэш состояния задач в SQLite."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                number     INTEGER PRIMARY KEY,
                title      TEXT NOT NULL,
                status     TEXT,
                type       TEXT,
                labels     TEXT,
                seen_at    TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def upsert(self, task: Task) -> None:
        self._conn.execute(
            """
            INSERT INTO tasks (number, title, status, type, labels, seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(number) DO UPDATE SET
                title=excluded.title,
                status=excluded.status,
                type=excluded.type,
                labels=excluded.labels,
                seen_at=excluded.seen_at
            """,
            (
                task.number,
                task.title,
                task.status,
                task.type,
                ",".join(task.labels),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
