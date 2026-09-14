# RULES-FILESYSTEM.md — Правила работы с файловой системой для Digital Company

> **Для кого:** все боты Digital Company (architect, dispatcher, coder-1, coder-2, coder-3, reviewer, tester, writer, devops, analyst, designer, security) и Claude-оркестратор (claude-ilya).
>
> **Цель:** систематизировать где боты записывают файлы, чтобы не захламлять корень `~/` и упростить cleanup/backup.
>
> **Главный принцип:** **вся рабочая активность Digital Company происходит внутри `~/digital-company/`** — никогда в корне `~/`.

---

## 🚨 Главный запрет

**НИКОГДА** не создавай файлы и папки прямо в корне `~/`. Если нужно записать что-то — это должно попадать в одну из подпапок:

- `~/digital-company/<подпапка>/...` — для рабочей активности команды
- `~/.config/<app>/...` — для конфигов и persistent state приложения
- `/tmp/<file>` — для эфемерных файлов одной операции (помни, `/tmp` это tmpfs, очищается при reboot — см. lesson #14)

**Корень `~/` это пользовательский каталог Ильи, не песочница для ботов.**

---

## 📁 Структура `~/digital-company/`

```
~/digital-company/
│
├── agents/                    # Конфиги ролей — read-only для ботов через CLAUDE.md
│   ├── architect/
│   │   └── CLAUDE.md           # Инструкция роли Architect (Декстер)
│   ├── dispatcher/             # CLAUDE.md роли (Маргарет)
│   ├── coder-1/                # CLAUDE.md роли (Деннис)
│   ├── coder-2/                # CLAUDE.md роли (Кен)
│   ├── coder-3/                # CLAUDE.md роли
│   ├── reviewer/               # CLAUDE.md роли (Кнут)
│   ├── tester/                 # CLAUDE.md роли (Барбара)
│   ├── writer/                 # CLAUDE.md роли (Ада)
│   ├── devops/                 # CLAUDE.md роли (Линус)
│   ├── analyst/                # CLAUDE.md роли (Клейтон)
│   ├── designer/               # CLAUDE.md роли (Норман)
│   ├── security/               # CLAUDE.md роли (Безопасник)
│   └── start-company.sh        # Скрипт запуска всей команды (12 tmux окон, 12 ролей)
│
│   # tmux карта 12 окон (start-company.sh):
│   #   1=architect  2=dispatcher  3=coder-1  4=coder-2
│   #   5=reviewer   6=tester      7=writer   8=devops
│   #   9=analyst   10=designer  11=coder-3  12=security
│
├── tools/                     # Общие скрипты (используются всеми ролями)
│   ├── tg-monitor.sh           # Telegram мониторинг (cron каждые 5 минут)
│   ├── tg-notify.sh            # Отправка одного сообщения в TG
│   └── ...                     # Будущие общие утилиты
│
├── monitor/                   # Опционально — для TG monitoring артефактов
│                              # (сейчас пустой, оставлен под будущее)
│
├── worktrees/                 # Git worktrees для feature branches
│   ├── coder-1-patch7.8/        # Пример: Coder-1 работает над патчем 7.8
│   ├── coder-2-c3-profile-page/
│   ├── reviewer-park10/
│   └── ...                     # Создаётся ботом через `git worktree add`,
│                              # удаляется после merge через `git worktree remove`
│
├── tmp/                       # Временные файлы сессии
│   ├── brief-architect-2026-05-26-1430.txt
│   ├── inbox-snapshot.json
│   └── ...                     # ОЧИЩАТЬ при closure сессии (через cleanup script)
│
├── logs/                      # Долгоживущие логи операций
│   ├── start-company-2026-05-26.log
│   ├── tg-monitor.log
│   └── ...                     # Архивировать или удалять старше 30 дней
│
├── reviews/                   # Отчёты ревью (опционально, можно в agents/reviewer/reviews/)
│
├── tests/                     # Test plans и regression reports
│
├── TOOLS-AVAILABLE.md         # Справочник инструментов команды
├── RULES-FILESYSTEM.md        # Этот файл
└── .git/                      # Git репо для версионирования конфигов и правил
```

---

## ✅ Где какие операции происходят

### Worktrees (feature branches)

**Правило:** при работе над фичей бот создаёт git worktree в `~/digital-company/worktrees/<role>-<scope>/`.

```bash
# Bot Coder-1 хочет работать над patch 7.8 в nvr-cloud-2206:
cd ~/digital-company/worktrees/
git -C ~/nvr-cloud-2206 worktree add ~/digital-company/worktrees/coder-1-patch7.8 -b patch/7.8-race-fix
cd ~/digital-company/worktrees/coder-1-patch7.8
# ... работа над патчем ...
# После merge:
cd ~/nvr-cloud-2206
git worktree remove ~/digital-company/worktrees/coder-1-patch7.8
```

**Запрет:** НЕ клонировать `nvr-cloud-2206` или другие репо отдельно в `~/`. Только worktrees из существующего клона.

### Временные файлы (брифы, snapshot'ы)

**Для эфемерных файлов одной операции** (бриф который сейчас отправляется через `tmux load-buffer`):
- Использовать `/tmp/brief-<role>-<timestamp>.txt`
- Очищать после операции — `rm /tmp/brief-*.txt` при closure

**Для файлов нужных на всю сессию** (snapshot inbox, состояние таска):
- Использовать `~/digital-company/tmp/<descriptive-name>.json`
- Очищать при closure сессии

**Запрет:** НЕ использовать `/tmp` для persistent state (см. lesson #14 — `/tmp` это tmpfs, очищается при reboot).

### Логи long-running операций

- `~/digital-company/logs/<operation>-<date>.log`
- Архивировать или удалять старше 30 дней через cleanup script
- Не писать логи в `~/` или `~/digital-company/` корень

### Конфиги и secrets

- App configs: `~/.config/<app>/` (например `~/.config/teslatel-bot/.env` для TG_BOT_TOKEN)
- Persistent state скриптов: тоже `~/.config/<app>/` (см. tg-monitor v3 после reboot incident)
- Никогда не secrets в plain text в repo — только в `CONTEXT_SECRETS.local.md` (gitignored) или в `~/.config/<app>/.env` с `chmod 600`

### Output Claude-оркестратора (claude-ilya)

Claude-оркестратор работает через MCP, не через файловую систему напрямую. Если нужно создавать output файлы:
- Использовать `~/digital-company/tmp/<file>` для временных
- Использовать `~/Obsidian/Claude-Vault/<path>` для постоянных через obsidian MCP

---

## ⛔️ Запретная зона: `~/` корень

**Не создавать:**
- Папки уровня `~/bot-tools/`, `~/nvr-bots/`, `~/jarvis/` и подобные ботские артефакты
- Скрипты `~/<name>.sh` (использовать `~/digital-company/tools/`)
- Тестовые/временные `~/test.py`, `~/data.json` и т.п.
- Бэкапы и сейвы `~/backup-*`, `~/<name>.bak`

**Допустимы стандартные пользовательские:**
- Standard XDG папки: Desktop, Documents, Downloads, Music, Pictures, Public, Templates, Videos
- Dot-конфиги Linux: `.ssh/`, `.config/`, `.local/`, `.bashrc` и т.п.
- Установленные пользователем папки: `Obsidian/`, `nvr-cloud-2206/`, `digital-company/`, `whisper-voice-repo/`, `miniconda3/`, `anaconda3/`

**Сомнительные (исторически появились, нужно мигрировать или удалить):**
- `~/bot-tools/` — старые скрипты ботов, мигрировать в `~/digital-company/tools/`
- `~/nvr-bots/` — старая папка ботов NVR, deprecate
- `~/pixel-agent-desk/` — визуализатор Digital Company (упоминается в `NVR-2026/claude/DIGITAL-COMPANY.md`), OK на месте
- `~/jarvis/` — JARVIS voice assistant prototype, OK если активно используется
- `~/launch-gnome-app.sh` — launcher, переместить в `~/digital-company/tools/` или `~/.local/bin/`

---

## 🧹 Cleanup discipline

### При completion индивидуальной задачи:

- Worktree остаётся до merge (это нужно для возможности revert)
- После merge — `git worktree remove ~/digital-company/worktrees/<role>-<scope>`
- Tmp файлы операции — `rm` из `/tmp/` или `~/digital-company/tmp/`

### При closure сессии Digital Company:

- `find ~/digital-company/tmp -type f -mtime +0 -delete` (удалить все tmp старше 1 дня)
- `find ~/digital-company/logs -type f -mtime +30 -delete` (логи старше 30 дней)
- Worktrees: проверить что нет orphaned (worktrees от уже-смерженных feature branches)
- См. closure checklist в `NVR-2026/claude/DIGITAL-COMPANY.md`

### Никогда не делать:
- ❌ Cleanup `rm -rf ~/` или подобное (никаких массовых удалений в home)
- ❌ Cleanup `rm -rf /tmp/*` (могут быть нужные файлы других процессов)
- ❌ Cleanup чужих папок (`~/Documents/`, `~/.config/` и т.д.)

---

## 🎯 Quick reference (для брифов ботам)

При написании брифа боту — указывай **точно** куда писать output:

| Что | Где |
|---|---|
| Feature ветка для разработки | `~/digital-company/worktrees/<role>-<scope>/` |
| Бриф следующему боту через tmux | `/tmp/brief-<role>-<timestamp>.txt` |
| Snapshot inbox для дальнейшей работы | `~/digital-company/tmp/inbox-<date>.json` |
| Лог cron-задачи | `~/digital-company/logs/<job>.log` |
| Test plan | `~/digital-company/agents/tester/tests/<feature>-plan.md` |
| Review report | `~/digital-company/agents/reviewer/reviews/<feature>-review.md` |
| Конфиг приложения | `~/.config/<app>/<file>` |

---

## История версий

| Версия | Дата | Что |
|---|---|---|
| 1.0 | 26.05.2026 | Initial draft. Зафиксированы правила после обнаружения ботских артефактов в корне `~/` (bot-tools, nvr-bots, pixel-agent-desk и т.д.). Илья попросил структурировать. |

---

## Связи (внешние документы в нашем vault)

- `NVR-2026/claude/DIGITAL-COMPANY.md` — общая структура команды, closure checklist, стиль брифов
- `NVR-2026/lessons/2026-05-25-session-lessons.md` lesson #14 — `/tmp` это tmpfs, persistent state в `~/.config/`
- `DOCS/SETUP-AI-WORKSTATION.md` — развёртывание полного AI-окружения на новой машине (включая digital-company)


## 📡 Коммуникация команды (ОБЯЗАТЕЛЬНО — правка Ильи 2026-06-06)

- **Enter ОБЯЗАТЕЛЕН при отправке сообщения.** Когда шлёшь сообщение другой роли / Диспетчеру через tmux — ВСЕГДА финальный `send-keys Enter` после `paste-buffer`. Без Enter сообщение виснет в input-строке получателя НЕотправленным (частый сбой, особенно после clear/compact: одни роли жмут Enter, другие забывают). После отправки ПРОВЕРЬ `capture-pane` получателя — сообщение ушло, а не висит в `❯`. Не нажал Enter = собеседник тебя не получил.

- **Язык: русский ИЛИ английский.** Веди коммуникацию и артефакты на русском или английском — оба допустимы. НЕ на украинском. Не смешивай языки хаотично внутри одного сообщения (замечен дрейф ru→uk и мешанина — устранить). Один язык консистентно в рамках сообщения.
