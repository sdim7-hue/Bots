# Observer & Notifier — build spec (stage 1)

Status: spec, 2026-06-16. Implements ARCH-OBSERVABILITY (vault myobs).
Read-only observability + notification layer over the task board, running on the
always-on backbone (map-server). Surfaces agent/task status and pings the human
(Telegram + email) when attention is needed. NEVER triggers paid bot runs or merges.

## Constraints
- Python 3.11, stdlib-first (urllib, sqlite3, http.server, smtplib, json). No heavy deps;
  Flask optional, dashboard only.
- Reuse orchestrator clients: `orchestrator/github_client.py` and
  `orchestrator/forgejo_client.py` (same interface: list_issues_by_label / get_issue / labels).
- Secrets from ENV only (never in git): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
  SMTP_HOST/PORT/USER/PASS, MAIL_TO.
- Read-only: no set_status, no add_comment, no merge, no bot launch anywhere in `observer/`.

## Components (new package `observer/`)
1. `registry.py` — projects loaded from `observer/projects.json`; each entry:
   {name, backend: github|forgejo, owner, repo, api_base?, cafile?}.
2. `collector.py` — per project pull issues with status labels, normalize to Task snapshot:
   {project, number, title, status, assignee, updated_at, url, last_comment_excerpt};
   persist to `observer/state.sqlite` (tables: snapshot, event).
3. `notifier.py` — diff new snapshot vs previous; emit events:
   status->review, status->failed, label needs:human present (budget-over later).
   Dedup by (project, number, event_type, status). Channels:
   - `channels/telegram.py` (Bot API sendMessage via urllib),
   - `channels/email.py` (smtplib),
   - `channels/console.py` (stdout, for testing without secrets).
   Active channels chosen by which secrets are present in ENV.
4. `dashboard.py` — http.server serving:
   - `/` HTML: projects -> tasks by status, "who is working", last N events;
   - `/api/state` JSON snapshot. Read-only from state.sqlite. Bind localhost.
5. `__main__.py` — CLI: `collect-once`, `notify-dry` (console), `serve` (dashboard),
   `run` (loop: collect -> detect -> notify -> sleep(interval)).

## Events -> human (supervisory mode)
review, failed, needs:human -> Telegram + email. done -> informational (configurable).

## Board contract (status labels)
Reuse existing Bots labels: status:queued / in-progress / review / tested / failed / done;
needs:human as escalation label. Do NOT assume labels exist in every repo — a separate
registry/setup step ensures labels per project ("use across all projects").

## Deploy (map-server — LATER step)
- systemd: observer-loop.service (run), observer-dash.service (serve).
- Secrets in /etc/observer.env (chmod 600), EnvironmentFile=.
- Dashboard behind Caddy at /ops/ (TLS).
- Admin access method to map-server: see playbook COMMON-INFRA (ssh:22 from office is closed).

## Acceptance (stage 1)
- `python -m observer collect-once` writes a snapshot for >=1 project, NO board mutation.
- `python -m observer notify-dry` prints events to console from a simulated status change.
- With TELEGRAM_* in ENV, a review event delivers a Telegram message.
- `serve` renders projects/tasks/events; `/api/state` returns JSON.
- Audit: no set_status/add_comment/merge calls anywhere under `observer/`.

## Out of scope (later)
Email polish, Ilya-style live-office skin, budget hook, queue auto-failover.

---

## Дисциплина уведомлений (добавлено 14.09.2026, playbook import-ai-ops B7)

Одно дедуплицированное сообщение на человеческом языке — на значимый переход состояния.

**Уведомляем:** переход в `review`, переход в `failed`, появление `needs:human`,
закрытие `done` (опционально, `--include-done`).

**НЕ уведомляем:** промежуточный прогресс, idle, retry, неизменившиеся снимки,
межботовые сообщения, логи, диффы, стектрейсы, секреты, а также задачи с маркером
`superseded` — решение по ним перекрыто более поздним (`bots.md` L85).

**Формат** (`observer/message.py`). Внутренний номер задачи НЕ может быть заголовком или
единственным содержанием: владелец не обязан помнить внутреннюю нумерацию.

    [map · ревью] FIN-3 (бот): этажность точки в карточке
    Бот закончил работу, результат ждёт проверки.
    Осталось в очереди: 3
    Сейчас: задача на ревью, дальше нужен вердикт
    Нужно от владельца: посмотреть результат и решить — принять или вернуть на доработку
    Техническая ссылка: ev-map-47-status-review

**Предохранитель** (`observer/redact.py`) стоит в канале-обёртке `channels.SafeChannel`,
а не в формирователе текста — обойти его, собрав сообщение иначе, нельзя. Блокируются
категории: токены GitHub, JWT, приватные ключи, `слово-маркер=значение`
(`token/password/secret/bearer/apikey/credential`), IP-адреса, hex-строки от 32 символов,
абсолютные пути ФС, стектрейсы. Найденные ЗНАЧЕНИЯ в текст отказа не попадают — иначе
секрет оказался бы в логе. **Отказ означает «переформулируй», а не «обойди фильтр».**
Техническая деталь живёт в дашборде, в сообщении — только `event_id` для сверки.

**Журналирование только доставленного.** Дедуп-запись делается лишь после фактической
доставки: иначе заблокированное событие «съедалось» бы дедупом и владелец не увидел бы
его никогда.

**Успех доставки в Telegram = ответ API с `message_id`.** HTTP 200 сам по себе ничего не
доказывает: Telegram отдаёт `ok=false` с кодом 200 (например, бот заблокирован
получателем). Без `message_id` считаем НЕ доставленным.

⚠ `observer/projects.json` рассчитан на **map-сервер** (`api_base` =
`http://127.0.0.1:3000/api/v1`). Для локальной проверки с другого узла — не править файл,
а передать свой через `OBSERVER_PROJECTS=<path>` (+ `OBSERVER_STATE_DB` для отдельной БД).

