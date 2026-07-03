---
type: reference
project: NVR-2026
status: active
created: 2026-05-02
updated: 2026-05-28
name: nvr-bot-brief
description: Use this skill whenever Claude needs to send a coding task to a Claude Code bot running in tmux on the bot-server (193.233.19.237) for the TESLATEL Cloud NVR project. Triggers include phrases like "отправь бриф боту", "дай задачу боту 0.0", "пусть бот сделает", "запусти на боте", or any moment when Claude has formulated a code change for the NVR system that should be delegated. This skill is NOT for Claude doing work itself - only when delegating to a sub-agent bot via tmux. Skip this skill for documentation tasks, vault edits, or read-only diagnostics.
---


# nvr-bot-brief

This skill encodes the proven pattern for delegating coding tasks to Claude Code bots in the TESLATEL Cloud NVR project. Following it precisely prevents the most common failures: cyrillic truncation in tmux, non-fast-forward push rejections, P50 violations, and missing self-checks.

---

## Behavioral principles (Karpathy + NVR-specific)

These five principles govern how bots must behave. Every brief must implicitly or explicitly enforce them.

### 1. Think Before Coding
**Не делай предположений молча. Выяви противоречия до написания кода.**
- Перед реализацией явно назови предположения. Если неясно — спроси.
- Если существует несколько интерпретаций — перечисли их, не выбирай молча.
- Если путь проще — скажи об этом.
- Если что-то вызывает сомнение — остановись, сформулируй вопрос.

### 2. Simplicity First
**Минимум кода который решает задачу. Ничего спекулятивного.**
- Никаких фич сверх запрошенного.
- Никаких абстракций для одноразового кода.
- Если написал 200 строк а могло быть 50 — перепиши.
- Спроси себя: "Скажет ли senior engineer что это overcomplicated?" Если да — упрости.

### 3. Surgical Changes
**Трогай только то что нужно. Убирай только свой мусор.**
- Не "улучшай" соседний код, комментарии, форматирование.
- Не рефактори то что не сломано.
- Если заметил несвязанный мёртвый код — упомяни, не удаляй.
- Тест: каждая изменённая строка должна прямо следовать из запроса.

### 4. Goal-Driven Execution
**Определи критерии успеха. Работай пока не выполнишь. Верифицируй.**
Для каждой задачи:
```
1. [Шаг] → проверка: [что должно быть]
2. [Шаг] → проверка: [что должно быть]
3. [Шаг] → проверка: [что должно быть]
```
Слабые критерии ("сделай чтобы работало") требуют постоянных уточнений.
Сильные критерии ("curl вернул 200, в логах нет error") позволяют работать автономно.

### 5. Verify System Effects (NVR-специфичный)
**После каждого изменения — проверь что НЕ сломал смежное.**

Обязательно после каждого коммита:
- **Пути и файлы:** если создаёшь путь в конфиге — убедись что он реально существует на сервере.
- **Docker compose:** после изменения compose.yml — запусти `docker compose config` и убедись что нет warnings.
- **Смежные сервисы:** если трогаешь backend — проверь frontend. Если трогаешь install скрипт — проверь что он не хардкодит пути которых нет на нетипичном железе.
- **Feature flags:** если добавляешь новый модуль — убедись что FF_* флаг включён в install скриптах по умолчанию.
- **БД-зависимости:** если создаёшь таблицу вручную — сразу создавай JS-миграцию чтобы следующие серверы получили её автоматически.

Если нашёл проблему — исправь СЕЙЧАС, не в следующем брифе.

---

## When to use this skill

Use it when:
- Илья asks Claude to delegate a coding task to a bot
- Claude has finished diagnosis and needs the bot to write/modify code
- A task requires git commits, docker rebuild, or anything beyond read-only inspection
- The work belongs on DEV2 (`185.33.175.130`) — single-writer per P50

Do NOT use it when:
- The task is documentation-only (vault edits, no code)
- Claude is doing read-only diagnosis itself via SSH
- Илья is asking Claude to push to DEV1/MaMaison directly

---

## Critical context for every brief

The bot is `claude-code` running in `tmux session "mywork"` on bot-server `193.233.19.237`:
- `pane 0.0` — Opus 4.7, larger tasks (multi-file, architectural).
- `pane 0.1` — Opus 4.7, pointed tasks (CSS, single-file fixes).
- `pane 0.2` — Ultra Review only. Never sends code, only reads.

Bot SSH to DEV2: `ssh -i /root/.ssh/nvr_bot_ed25519 -p 20022 nvradmin@185.33.175.130`. Sudo NOPASSWD.

---

## The five immutable rules

1. **P50 — DEV2 single writer.** Never DEV1, never MaMaison, never Core Node directly.
2. **Pull-rebase before push.** `git pull --rebase origin main` before every push.
3. **One task = one commit.** No batching unrelated changes.
4. **Self-check after rebuild.** Wait 10s → curl health → docker logs | grep error.
5. **Backend change → rebuild API.** Frontend-only → rebuild frontend only.

---

## Brief template

```
Действуй самостоятельно. DEV2 (185.33.175.130:20022, nvradmin, key /root/.ssh/nvr_bot_ed25519).
Sudo NOPASSWD. main. Один коммит.

ЗАДАЧА: <одно предложение>

ПРИЧИНА: <что сломано или зачем нужно>

РЕШЕНИЕ:
<конкретные файлы и изменения>

ПРОВЕРКА — верифицируй каждый шаг:
1. [Шаг] → ожидаемый результат: [конкретно]
2. [Шаг] → ожидаемый результат: [конкретно]

СМЕЖНЫЕ ЭФФЕКТЫ — проверь что не сломал:
- [что может быть затронуто косвенно]

Сборка: docker compose build --no-cache [сервис] && docker compose up -d [сервис]
sleep 15 && curl -ks https://nvrdev.multimonitor.pro/api/health

git add [файлы]
git commit -m "fix/feat(...): ..."
git pull --rebase origin main && git push origin main

ОТЧЁТ:
1. Commit hash
2. Результат каждой проверки из секции ПРОВЕРКА
3. Что проверил из СМЕЖНЫЕ ЭФФЕКТЫ
4. Health ok
```

---

## Delivery technique (cyrillic-safe)

**Direct `tmux send-keys` FORBIDDEN for briefs with cyrillic.** Use buffer pattern:

```bash
cat > /tmp/brief.txt << 'BRIEF'
[содержимое брифа]
BRIEF
wc -lc /tmp/brief.txt
tmux load-buffer /tmp/brief.txt
tmux paste-buffer -t mywork:0.0
sleep 1
tmux send-keys -t mywork:0.0 Enter
```

For briefs >5KB — split into chunks. After each chunk verify `wc -lc`.

---

## Choosing the pane

- Single-file fix, ≤2 files → **pane 0.1**
- Multi-file feature, migrations, architectural → **pane 0.0**
- Ultra Review (read-only) → **pane 0.2**
- Both panes busy → wait, do not queue into busy pane.

Check pane state before sending:
```bash
tmux capture-pane -t mywork:0.0 -p | tail -3
```
Idle = `❯` prompt visible. Working = `Crunching…`/`Cogitated for…` at bottom.

---

## Anti-patterns — never do these

- **Не давай боту свободу "make it better"** — только конкретная задача с критерием готовности.
- **Не делай бриф из 5 несвязанных задач** — один коммит = одна задача.
- **Не трогай DEV1/MaMaison/Core Node через бота** — только DEV2.
- **Не игнорируй секцию СМЕЖНЫЕ ЭФФЕКТЫ** — это предотвращает проблемы типа "инсталлятор хардкодит несуществующий путь".
- **Не принимай коммит без прочтения отчёта** — бот должен явно подтвердить каждую проверку.

---

## Checklist before sending

- [ ] Pane свободен
- [ ] Контекст < 70% (если больше — `/clear`)
- [ ] CURRENT_HEAD актуален
- [ ] Задача = одна вещь = один коммит
- [ ] Секция ПРОВЕРКА есть и конкретная
- [ ] Секция СМЕЖНЫЕ ЭФФЕКТЫ заполнена
- [ ] load-buffer/paste-buffer, не send-keys



---

## ⚡ PRIMARY delivery — `nvr-brief` helper (с 11.05.2026)

**С 11.05.2026 на bot-сервере 193.233.19.237 установлена утилита `/usr/local/bin/nvr-brief`** — упрощает доставку длинных брифов в 7+ раз.

**Преимущества:**
- **1 SSH-вызов для save** (через stdin — не рвётся на размере как printf аргументы)
- **1 SSH-вызов для send** (внутри tmux load-buffer + paste + send-keys Enter)
- Поддержка кириллицы до 100KB без потерь
- Логирование в `/var/log/nvr-brief.log`
- Хранение в `/var/lib/nvr-briefs/` для повторного использования

### Использование

```bash
# 1. Сохранить бриф (содержимое через stdin)
cat << 'EOF' | ssh bot 'nvr-brief save my_task'
Действуй самостоятельно. CLAUDE.md прочитан.
ЗАДАЧА: ...
СЕРВЕР: DEV2 (185.33.175.130:20022 nvradmin, ключ ~/.ssh/nvr_bot_ed25519). P50.
...
EOF
# → [brief] saved my_task: 2902 bytes, 50 lines

# 2. Отправить в pane бота
ssh bot 'nvr-brief send 0.0 my_task'
# → [brief] sent my_task to mywork:0.0 (2902 bytes, 50 lines)
```

**Поддерживаемые форматы pane:**
- `0.0`, `0.1`, `0.2` → расширяется до `mywork:0.0` и т.д.
- `session:pane` (например `test_brief:0`) — используется как есть

### Подкоманды

| Команда | Что делает |
|---|---|
| `nvr-brief save <name>` | Читает stdin, сохраняет в `/var/lib/nvr-briefs/<name>.txt`. Валидирует имя `[a-z0-9_-]+`, размер <100KB |
| `nvr-brief send <pane> <name>` | Отправляет сохранённый бриф в указанный pane через tmux buffer |
| `nvr-brief list` | Показывает все сохранённые брифы (имя, размер, mtime) |
| `nvr-brief read <name>` | Выводит содержимое брифа в stdout |
| `nvr-brief cleanup [days]` | Удаляет брифы старше N дней (default 7) |
| `nvr-brief --help` | Справка |

### Когда использовать nvr-brief vs старый printf+ssh

**PRIMARY (всегда предпочтительно):** `nvr-brief save` + `nvr-brief send`
- Брифы любого размера
- Брифы с кириллицей и спецсимволами
- Когда хочется сохранить бриф для re-send (например на другой pane)

**FALLBACK (только если bot-server недоступен или утилита сломана):** старый printf+ssh+tmux (см. секцию ниже)
- Для очень коротких команд (1-2 строки) без особенностей кодировки
- Когда диагностируем сам bot-server (утилита может не работать)

### Limit: 5 KB per chunk при сохранении

В отличие от printf, `nvr-brief save` через stdin **не имеет ограничения 5 KB** — bash heredoc стримит весь контент за один вызов. До 100 KB tested и работает.

### Логи и storage

- **Storage:** `/var/lib/nvr-briefs/` (claude-agent owner, 755) — читаемо без sudo
- **Лог:** `/var/log/nvr-brief.log` — каждое действие с timestamp + bytes
- **Permissions:** утилита запускается под root, но `sudo -u claude-agent tmux` внутри — корректные права на tmux session `mywork`

### Что делать если nvr-brief упал

1. `ssh bot 'nvr-brief --help'` — проверить что утилита есть
2. `ssh bot 'cat /var/log/nvr-brief.log | tail -20'` — посмотреть последние действия и ошибки
3. `ssh bot 'ls -la /usr/local/bin/nvr-brief /var/lib/nvr-briefs/'` — проверить файлы и права
4. Если утилита потеряна (snapshot rollback?) — пересоздать (см. [[CONTEXT_SECRETS.local#12. Incident 11.05.2026]] раздел про bot-server — можно использовать тот же подход)
5. Fallback на printf+ssh+tmux pattern (секция ниже)

---

*nvr-brief создан ботом 0.1 11.05.2026 (commit нет — это утилита bot-сервера, не в репо). Все 6 тестов PASS, кириллица 10KB round-trip ✓. Подтверждён в боевых условиях с бамп-релизом v0.2.21.*
