"""Дашборд: read-only HTTP-сервер поверх state.sqlite (http.server, stdlib).

Маршруты:
  /           — HTML: проекты -> задачи по статусам, «кто работает», N событий;
  /api/state  — JSON-снимок состояния.

Привязка к localhost. Никаких мутаций — только чтение state.sqlite.
"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .collector import STATUS_LABELS, StateStore, TaskSnapshot

_STATUS_ORDER = [s[len("status:"):] for s in STATUS_LABELS]


def _state_payload(store: StateStore, events_limit: int = 20) -> dict:
    snaps = store.all_snapshots()
    tasks = [
        {
            "project": s.project,
            "number": s.number,
            "title": s.title,
            "status": s.status,
            "assignee": s.assignee,
            "updated_at": s.updated_at,
            "url": s.url,
            "needs_human": s.needs_human,
            "last_comment_excerpt": s.last_comment_excerpt,
        }
        for s in sorted(snaps, key=lambda t: (t.project, t.number))
    ]
    return {"tasks": tasks, "events": store.recent_events(events_limit)}


def _render_html(payload: dict) -> str:
    tasks: list[dict] = payload["tasks"]
    events: list[dict] = payload["events"]

    # Группировка по проекту -> статусу.
    projects: dict[str, dict[str, list[dict]]] = {}
    for t in tasks:
        projects.setdefault(t["project"], {})
        bucket = t["status"] or "(без статуса)"
        projects[t["project"]].setdefault(bucket, []).append(t)

    def esc(x) -> str:
        return html.escape(str(x if x is not None else ""))

    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        "<title>Observer — доска</title>",
        "<style>",
        "body{font:14px/1.5 system-ui,sans-serif;margin:1.5rem;color:#222}",
        "h1{font-size:1.3rem} h2{font-size:1.1rem;margin-top:1.4rem}",
        "h3{font-size:.95rem;color:#555;margin:.8rem 0 .2rem}",
        ".task{padding:.15rem 0} .nh{color:#b60205;font-weight:600}",
        ".who{color:#1d76db} a{color:#0366d6;text-decoration:none}",
        ".ev{font-size:.85rem;color:#444} .muted{color:#888}",
        "</style></head><body>",
        "<h1>Observer — доска задач</h1>",
    ]

    if not tasks:
        parts.append("<p class='muted'>Снимков пока нет. "
                     "Запусти <code>python -m observer collect-once</code>.</p>")

    for project, buckets in projects.items():
        parts.append(f"<h2>{esc(project)}</h2>")
        for status in _STATUS_ORDER + sorted(
            k for k in buckets if k not in _STATUS_ORDER
        ):
            items = buckets.get(status)
            if not items:
                continue
            parts.append(f"<h3>{esc(status)} ({len(items)})</h3>")
            for t in items:
                who = f" <span class='who'>@{esc(t['assignee'])}</span>" if t["assignee"] else ""
                nh = " <span class='nh'>needs:human</span>" if t["needs_human"] else ""
                title = esc(t["title"])
                link = (f"<a href='{esc(t['url'])}'>#{t['number']}</a>"
                        if t["url"] else f"#{t['number']}")
                parts.append(f"<div class='task'>{link} {title}{who}{nh}</div>")

    # «Кто работает» — задачи в in-progress с исполнителем.
    working = [t for t in tasks if t["status"] == "in-progress"]
    parts.append("<h2>Кто работает</h2>")
    if working:
        for t in working:
            who = esc(t["assignee"]) if t["assignee"] else "—"
            parts.append(f"<div class='task'><span class='who'>{who}</span> · "
                         f"{esc(t['project'])} #{t['number']} {esc(t['title'])}</div>")
    else:
        parts.append("<p class='muted'>Никто не в работе.</p>")

    parts.append("<h2>Последние события</h2>")
    if events:
        for e in events:
            parts.append(
                f"<div class='ev'>{esc(e['created_at'])} · {esc(e['project'])} "
                f"#{e['number']} · <b>{esc(e['event_type'])}</b> · {esc(e['title'])}</div>"
            )
    else:
        parts.append("<p class='muted'>Событий пока нет.</p>")

    parts.append("<p class='muted'><a href='api/state'>/api/state (JSON)</a></p>")
    parts.append("</body></html>")
    return "".join(parts)


def make_handler(db_path: Path | None):
    """Фабрика обработчика, замкнутого на путь к БД (по запросу открываем БД)."""

    class _Handler(BaseHTTPRequestHandler):
        server_version = "observer-dash/0.1"

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 — имя задаётся http.server
            store = StateStore(db_path)
            try:
                payload = _state_payload(store)
            finally:
                store.close()

            if self.path.rstrip("/") in ("", "/") or self.path == "/":
                body = _render_html(payload).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
            elif self.path.split("?")[0] == "/api/state":
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

        def log_message(self, *args) -> None:  # тихий лог
            pass

    return _Handler


def serve(host: str = "127.0.0.1", port: int = 8787,
          db_path: Path | None = None) -> None:
    """Запускает дашборд (блокирующе). Привязка к localhost по умолчанию."""
    httpd = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"Observer dashboard: http://{host}:{port}/  (Ctrl+C — стоп)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлен.")
    finally:
        httpd.server_close()
