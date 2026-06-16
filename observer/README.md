# observer/

Слой наблюдаемости и уведомлений (Python 3.11, только stdlib). Реализует
ARCH-OBSERVABILITY, stage 1. См. `docs/observer-spec.md`.

## Принцип

- **Строго read-only.** Пакет читает доску через read-интерфейс клиентов
  оркестратора (`list_issues_by_label`) и НИКОГДА не меняет её (нет set_status,
  add_comment, merge) и не запускает ботов.
- Состояние — локальный SQLite (`observer/state.sqlite`, в .gitignore).
- Секреты каналов — только из ENV, в git не попадают.

## Структура

```
observer/
├── registry.py        # проекты из projects.json -> read-only клиент очереди
├── collector.py       # снимки задач (snapshot) + состояние SQLite (snapshot, event)
├── notifier.py        # диф снимков -> события (review/failed/needs:human) + дедуп
├── channels/          # доставка: telegram.py, email.py, console.py
├── dashboard.py       # http.server: / (HTML), /api/state (JSON), localhost
└── __main__.py        # CLI: collect-once, notify-dry, serve, run
```

## CLI

```
python -m observer collect-once   # снимок доски (без мутаций)
python -m observer notify-dry     # сухой прогон: события в консоль
python -m observer serve          # дашборд на http://127.0.0.1:8787/
python -m observer run            # цикл collect -> detect -> notify -> sleep
```

## Конфигурация (ENV)

- Токены очереди (как у оркестратора): `GITHUB_TOKEN`/`GH_TOKEN` или
  `BOTS_TOKEN`/`FORGEJO_TOKEN`.
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_TO`.
- Пути (опционально): `OBSERVER_PROJECTS`, `OBSERVER_STATE_DB`.

Активные каналы выбираются по наличию секретов в ENV; без секретов работает
только console (для тестов).
