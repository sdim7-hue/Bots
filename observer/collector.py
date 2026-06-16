"""Сбор снимков задач и локальное состояние (SQLite).

Коллектор по каждому проекту тянет issues со статусными метками, нормализует
в снимок задачи (TaskSnapshot) и складывает в observer/state.sqlite.

Только чтение очереди (list_issues_by_label). Ни одной мутации доски.

Таблицы state.sqlite:
  snapshot — последний известный снимок каждой задачи (project, number);
  event    — журнал уведомлений (для дедупликации и дашборда).
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from . import registry
from .registry import Project

# Статусы доски (docs/labels.md + spec): по каждому тянем issues отдельно,
# т.к. read-интерфейс клиента — list_issues_by_label.
STATUS_LABELS = (
    "status:queued",
    "status:in-progress",
    "status:review",
    "status:tested",
    "status:failed",
    "status:done",
)
NEEDS_HUMAN_LABEL = "needs:human"
_STATUS_PREFIX = "status:"

# state.sqlite рядом с пакетом; путь переопределяется через ENV.
DEFAULT_DB_PATH = Path(
    os.environ.get("OBSERVER_STATE_DB", Path(__file__).parent / "state.sqlite")
)

# Длина выдержки последнего комментария/тела.
_EXCERPT_LIMIT = 280


@dataclass
class TaskSnapshot:
    project: str
    number: int
    title: str
    status: str | None
    assignee: str | None
    updated_at: str | None
    url: str | None
    last_comment_excerpt: str
    needs_human: bool

    def key(self) -> tuple[str, int]:
        return (self.project, self.number)


def _excerpt(text: str | None) -> str:
    """Однострочная выдержка фиксированной длины (без переводов строк)."""
    flat = " ".join((text or "").split())
    return flat[:_EXCERPT_LIMIT]


def _assignee(issue: dict) -> str | None:
    """Логин исполнителя: assignee, затем первый из assignees."""
    who = issue.get("assignee")
    if isinstance(who, dict) and who.get("login"):
        return who["login"]
    assignees = issue.get("assignees")
    if isinstance(assignees, list):
        for item in assignees:
            if isinstance(item, dict) and item.get("login"):
                return item["login"]
    return None


def _label_names(issue: dict) -> list[str]:
    return [lbl["name"] for lbl in issue.get("labels", []) if isinstance(lbl, dict)]


def _status_of(labels: list[str]) -> str | None:
    return next(
        (l[len(_STATUS_PREFIX):] for l in labels if l.startswith(_STATUS_PREFIX)),
        None,
    )


def _url_of(issue: dict) -> str | None:
    # GitHub: html_url. Forgejo/Gitea: html_url тоже присутствует.
    return issue.get("html_url") or issue.get("url")


def _to_snapshot(project: Project, issue: dict) -> TaskSnapshot:
    labels = _label_names(issue)
    # last_comment_excerpt: read-интерфейс клиента не отдаёт ленту комментариев,
    # поэтому в stage 1 берём выдержку из тела issue (лучшее доступное чтение).
    return TaskSnapshot(
        project=project.name,
        number=int(issue["number"]),
        title=issue.get("title", ""),
        status=_status_of(labels),
        assignee=_assignee(issue),
        updated_at=issue.get("updated_at"),
        url=_url_of(issue),
        last_comment_excerpt=_excerpt(issue.get("body")),
        needs_human=NEEDS_HUMAN_LABEL in labels,
    )


def collect_project(project: Project) -> list[TaskSnapshot]:
    """Собирает снимки всех задач проекта по статусным меткам (+ needs:human).

    Возвращает по одному снимку на задачу (дедуп по номеру). Только чтение.
    """
    client = registry.make_client(project)
    by_number: dict[int, TaskSnapshot] = {}
    # Статусные метки + needs:human (задача без статуса, но с эскалацией).
    for label in (*STATUS_LABELS, NEEDS_HUMAN_LABEL):
        issues = client.list_issues_by_label(label)
        for issue in issues:
            snap = _to_snapshot(project, issue)
            by_number[snap.number] = snap
    return list(by_number.values())


class StateStore:
    """Локальное состояние observer'а: снимки задач и журнал событий."""

    def __init__(self, db_path: Path | None = None) -> None:
        db_path = Path(db_path or DEFAULT_DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshot (
                project              TEXT    NOT NULL,
                number               INTEGER NOT NULL,
                title                TEXT    NOT NULL,
                status               TEXT,
                assignee             TEXT,
                updated_at           TEXT,
                url                  TEXT,
                last_comment_excerpt TEXT,
                needs_human          INTEGER NOT NULL DEFAULT 0,
                seen_at              TEXT    NOT NULL,
                PRIMARY KEY (project, number)
            );
            CREATE TABLE IF NOT EXISTS event (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project     TEXT    NOT NULL,
                number      INTEGER NOT NULL,
                event_type  TEXT    NOT NULL,
                status      TEXT,
                title       TEXT,
                url         TEXT,
                created_at  TEXT    NOT NULL,
                UNIQUE (project, number, event_type, status)
            );
            """
        )
        self._conn.commit()

    # --- снимки -----------------------------------------------------------
    def load_snapshots(self) -> dict[tuple[str, int], TaskSnapshot]:
        """Все известные снимки, индексированные по (project, number)."""
        rows = self._conn.execute(
            "SELECT project, number, title, status, assignee, updated_at, url, "
            "last_comment_excerpt, needs_human FROM snapshot"
        ).fetchall()
        result: dict[tuple[str, int], TaskSnapshot] = {}
        for r in rows:
            snap = TaskSnapshot(
                project=r["project"],
                number=r["number"],
                title=r["title"],
                status=r["status"],
                assignee=r["assignee"],
                updated_at=r["updated_at"],
                url=r["url"],
                last_comment_excerpt=r["last_comment_excerpt"] or "",
                needs_human=bool(r["needs_human"]),
            )
            result[snap.key()] = snap
        return result

    def upsert_snapshot(self, snap: TaskSnapshot) -> None:
        self._conn.execute(
            """
            INSERT INTO snapshot (project, number, title, status, assignee,
                updated_at, url, last_comment_excerpt, needs_human, seen_at)
            VALUES (:project, :number, :title, :status, :assignee, :updated_at,
                :url, :last_comment_excerpt, :needs_human, :seen_at)
            ON CONFLICT(project, number) DO UPDATE SET
                title=excluded.title,
                status=excluded.status,
                assignee=excluded.assignee,
                updated_at=excluded.updated_at,
                url=excluded.url,
                last_comment_excerpt=excluded.last_comment_excerpt,
                needs_human=excluded.needs_human,
                seen_at=excluded.seen_at
            """,
            {
                **asdict(snap),
                "needs_human": int(snap.needs_human),
                "seen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )
        self._conn.commit()

    def all_snapshots(self) -> list[TaskSnapshot]:
        return list(self.load_snapshots().values())

    # --- события ----------------------------------------------------------
    def event_exists(self, project: str, number: int, event_type: str,
                     status: str | None) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM event WHERE project=? AND number=? AND event_type=? "
            "AND IFNULL(status,'')=IFNULL(?, '')",
            (project, number, event_type, status),
        ).fetchone()
        return row is not None

    def record_event(self, project: str, number: int, event_type: str,
                     status: str | None, title: str | None,
                     url: str | None) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO event
                (project, number, event_type, status, title, url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project, number, event_type, status, title, url,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT project, number, event_type, status, title, url, created_at "
            "FROM event ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
