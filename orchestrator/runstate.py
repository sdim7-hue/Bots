"""Состояние одного прогона: каталог + манифест + журнал событий.

Зачем (playbook import-ai-ops B1/B5). Сейчас состояние прогона живёт в выводе
команды и в комментарии issue: упал процесс — не осталось ничего, по чему можно
восстановить, что произошло. Разделение слоёв: знания — в vault, механика — в
репозитории, КОД проекта — в гейте, а состояние прогона — здесь:

    ~/.local/state/bots/<run-id>/
        manifest.json     кто/что/на каком SHA, валидируется при записи
        events.sqlite     журнал событий прогона
        bot.log           сырой вывод бота
        evidence/         артефакты, на которые ссылаются события

Главный инвариант: **СНАЧАЛА ЗАПИСЬ, ПОТОМ СИГНАЛ.** Событие получает id и
ложится в журнал ДО попытки кого-либо уведомить. Потерянное уведомление, убитый
процесс или сбой сети не теряют сам факт.

ACK. Схема события несёт поля подтверждения (`requires_ack`, `state`, `ack_by`,
`ack_at`), потому что они нужны передаче работы между ролями (см. B3). Сегодня
в одиночном цикле ACK никто не ставит — и это НЕ повод считать событие
подтверждённым: `state` остаётся `recorded`, а не превращается в `acked` по
таймауту. **Истёкший срок никогда не означает разрешение продолжить** —
роль остаётся в безопасном ожидании (B1).
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Корень состояния прогонов; переопределяется через ENV.
STATE_ROOT = Path(os.environ.get(
    "BOTS_RUN_ROOT", Path.home() / ".local" / "state" / "bots"))

# Допустимые виды событий (import-ai-ops B1, адаптировано под доску Forgejo).
KINDS = (
    "run-started", "run-finished",
    "bot-result", "status-changed",
    "blocked", "needs-human",
    "handoff", "review-result", "test-result",
    "closeout", "superseded",
    "critical",
)
SEVERITIES = ("info", "warning", "critical")


class ManifestError(ValueError):
    """Манифест не прошёл валидацию — прогон не начинается."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_run_id(repo: str, role: str) -> str:
    """`<repo>-<yyyymmdd-HHMMSS>-<role>` — сортируется по времени, читается глазом."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "-" for c in s)
    return f"{safe(repo)}-{stamp}-{safe(role)}"


def validate_manifest(data: dict) -> dict:
    """Манифест — валидируемые ДАННЫЕ, не скрипт.

    Никаких промптов, паролей, токенов и произвольных команд. База — только
    точный 40-символьный SHA, не имя ветки: `branch head` меняется под ногами.
    `production_authorized=true` отклоняется на этом уровне (B2).
    """
    required = ("run_id", "repo", "role", "base_sha", "node")
    for field in required:
        if not data.get(field):
            raise ManifestError(f"в манифесте нет обязательного поля {field}")

    sha = str(data["base_sha"])
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha.lower()):
        raise ManifestError("base_sha должен быть точным 40-символьным SHA, не веткой")

    if data.get("production_authorized"):
        raise ManifestError("production_authorized=true недопустим: выкладка не "
                            "авторизуется манифестом прогона")
    data["production_authorized"] = False

    banned = ("token", "password", "secret", "bearer", "api_key", "apikey",
              "credential", "prompt", "command", "cmd", "script")
    for key in data:
        low = key.lower()
        if any(b in low for b in banned):
            raise ManifestError(f"поле {key} недопустимо в манифесте "
                                "(секреты и исполняемое — не данные прогона)")
    return data


class RunState:
    """Каталог прогона: манифест, журнал событий, место под артефакты."""

    def __init__(self, run_id: str, root: Path | None = None) -> None:
        self.run_id = run_id
        self.dir = (root or STATE_ROOT) / run_id
        self.evidence = self.dir / "evidence"
        self.evidence.mkdir(parents=True, exist_ok=True)
        # bot.log — сырой вывод бота: может содержать что угодно, включая то,
        # что бот прочитал в репозитории. Каталог прогона закрываем.
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        self._conn = sqlite3.connect(self.dir / "events.sqlite")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # --- манифест ---------------------------------------------------------
    def write_manifest(self, **fields) -> dict:
        data = validate_manifest({"run_id": self.run_id, "created_at": _now(), **fields})
        (self.dir / "manifest.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def manifest(self) -> dict:
        path = self.dir / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    # --- журнал -----------------------------------------------------------
    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS event (
                event_id     TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                sender       TEXT NOT NULL,
                recipient    TEXT,
                kind         TEXT NOT NULL,
                severity     TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                expires_at   TEXT,
                reply_to     TEXT,
                dedupe_key   TEXT,
                requires_ack INTEGER NOT NULL DEFAULT 0,
                payload_ref  TEXT,
                summary      TEXT,
                state        TEXT NOT NULL DEFAULT 'recorded',
                ack_by       TEXT,
                ack_at       TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS event_dedupe
                ON event(run_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
            """
        )
        self._conn.commit()

    def record(self, kind: str, *, sender: str, summary: str = "",
               severity: str = "info", recipient: str | None = None,
               requires_ack: bool = False, dedupe_key: str | None = None,
               reply_to: str | None = None, payload_ref: str | None = None,
               expires_at: str | None = None) -> str:
        """Записывает событие и возвращает event_id. Вызывается ДО сигнала.

        Идемпотентно по (run_id, dedupe_key): повторная запись того же события
        возвращает существующий event_id, а не плодит дубль.
        """
        if kind not in KINDS:
            raise ValueError(f"неизвестный вид события: {kind}")
        if severity not in SEVERITIES:
            raise ValueError(f"неизвестная важность: {severity}")

        if dedupe_key:
            row = self._conn.execute(
                "SELECT event_id FROM event WHERE run_id=? AND dedupe_key=?",
                (self.run_id, dedupe_key)).fetchone()
            if row:
                return row["event_id"]

        event_id = f"ev-{uuid.uuid4().hex[:12]}"
        self._conn.execute(
            """INSERT INTO event (event_id, run_id, sender, recipient, kind,
                   severity, created_at, expires_at, reply_to, dedupe_key,
                   requires_ack, payload_ref, summary)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, self.run_id, sender, recipient, kind, severity, _now(),
             expires_at, reply_to, dedupe_key, int(requires_ack), payload_ref,
             summary[:2000]),
        )
        self._conn.commit()
        return event_id

    def ack(self, event_id: str, by: str) -> bool:
        """ACK = «получил и принял ответственность», НЕ «согласен» и НЕ «готово».

        Ставится только явно. Ни таймаут, ни истечение expires_at ACK не дают.
        """
        cur = self._conn.execute(
            "UPDATE event SET state='acked', ack_by=?, ack_at=? "
            "WHERE event_id=? AND state='recorded'",
            (by, _now(), event_id))
        self._conn.commit()
        return cur.rowcount > 0

    def events(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM event WHERE run_id=? ORDER BY created_at, rowid LIMIT ?",
            (self.run_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def pending_ack(self) -> list[dict]:
        """События, ждущие подтверждения. Прогон с непустым списком не закрывают."""
        rows = self._conn.execute(
            "SELECT * FROM event WHERE run_id=? AND requires_ack=1 AND state='recorded'",
            (self.run_id,)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()


def latest_runs(limit: int = 10, root: Path | None = None) -> list[str]:
    base = root or STATE_ROOT
    if not base.is_dir():
        return []
    dirs = [d for d in base.iterdir() if (d / "events.sqlite").exists()]
    return [d.name for d in sorted(dirs, key=lambda d: d.name, reverse=True)[:limit]]
