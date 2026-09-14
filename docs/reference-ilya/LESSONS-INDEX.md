---
type: reference
project: claude
status: active
created: 2026-05-25
updated: 2026-05-27
scope: ../LESSONS.md (129 lessons L1-L130, L104 missing)
purpose: компактная навигация — заменяет чтение LESSONS.md целиком при старте бота
---

# LESSONS Navigation Index

## Зачем этот файл

Полный `../LESSONS.md` = **124 KB / 1061 строка / 129 уроков**. Чтение целиком при старте бота обходится в ~30K токенов контекста, из которых обычно нужны 5-10%.

**Workflow:**
1. **При старте** бот читает этот индекс (~6 KB) вместо `../LESSONS.md` целиком.
2. **По мере погружения в тему** — открывает конкретный урок через `obsidian:read-note "LESSONS#L67"` (якорь по заголовку).
3. **При появлении нового урока** в `LESSONS.md` — обновлять и этот индекс (новая строка в таблице + теги).

**Этот файл — навигация, не источник правды.** Источник — `../LESSONS.md`. При расхождении доверяй ему.

L104 пропущен намеренно (перенесён в `WhisperLocal/LESSONS` как L12). См. `LESSONS.md §Конвенция`.

---

## Карта по тегам (быстрый поиск)

| Тег | Когда применять | Уроки |
|---|---|---|
| `bot-work` | Универсальные правила работы ботов Claude Code; читать всем ролям digital-company | L67, L80-L93, L99, L100-L102, L105-L111 |
| `code` | Правка кода (JS/Python/CSS) — общие грабли | L2-L13, L15-L16, L28-L34, L36-L44, L82, L86-L88, L97-L98, L110 |
| `ssh` | SSH-доступ к серверам, smoke-test, ControlMaster | L67, L69, L84 |
| `git` | Git workflow (vault и код), commit body, rebase | L46, L71, L75, L77, L79, L91, L108, L109 |
| `vault` | Obsidian, wikilinks, структура, daily-артефакты | L95, L99, L100-L102, L105, L108, L109 |
| `nvr-video` | MSE-плеер, кодеки H.264/H.265, экспорт | L1-L13, L15, L17-L22 |
| `nvr-audio` | Hikvision audio, ISAPI capability, ipcm strip | L1, L9, L23-L27 |
| `nvr-cameras` | Camera config, ISAPI, ONVIF, motion, capabilities | L17-L19, L23-L25, L39-L40, L50, L53-L55, L86, L120 |
| `mediamtx` | MediaMTX config, recordPath, retention | L1, L45-L52, L55 |
| `lus` | LUS, лицензии, обновления, releases | L77-L79 |
| `host-agent` | host-agent self-update механика | L77, L78, L110 |
| `db` | PostgreSQL, миграции, schema, timezone | L35-L44, L62, L113-L118 |
| `auth` | Keycloak, JWT, ROPC, email_verified | L56-L62 |
| `infra` | Docker, диски, сеть, recovery, backups, fail2ban | L28-L34, L63-L70, L113-L120 |
| `ux-ilya` | Коммуникация с Ильёй: тон, продуктовый язык, TESLATEL vs prod | L94-L96 |
| `tooling` | Claude Code TUI, MCP, paste-buffer, флаги CLI | L99-L111 |
| `jarvis` | Voice assistant Jarvis (отдельный проект, не NVR) | L121-L130 |

---

## Per-role hints для digital-company

Что читать сразу при работе в роли:

| Роль | Обязательные уроки |
|---|---|
| **Architect** | bot-work + L81 (git log перед эпиком), L83 (бот может расширить scope), L87-L90 (бриф формулировки) |
| **Dispatcher** | bot-work + L85 (sleep 2), L100-L102 (load-buffer), L111 (призрачный input TUI) |
| **Coder-1 / Coder-2** | code + git + ssh + L82 (thundering herd), L91 (параллельный rebase), L109 (.bak файлы) |
| **Reviewer** | bot-work + code + L82, L86, L87, L91, L109 (чеклист findings) |
| **Tester** | bot-work + L86 (структура API), L99 (разные клиенты Claude) |
| **Tech Writer** | vault + L95 (язык Ильи), L99, L105, L108 (github MCP) |
| **DevOps** | infra + ssh + L67, L69, L84, L91, L107 (VPS freeze) |

---

## Полная таблица уроков

### 🎬 Video / Player / MSE / Codecs (22)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L1 | Hikvision ipcm-аудио в fMP4 — Chrome MSE не поддерживает | nvr-video, nvr-audio, mediamtx, code | 7 |
| L2 | SourceBuffer InvalidStateError — race appendBuffer/remove | nvr-video, code | 5 |
| L3 | MSE sequence mode vs segments | nvr-video, code | 4 |
| L4 | stripInitSegment для 2-го и далее сегмента | nvr-video, code | 3 |
| L5 | MSE timeline drift — двойной счёт duration | nvr-video, code | 5 |
| L6 | MSE stall после буферизации — 3 уровня защиты | nvr-video, code | 5 |
| L7 | MSE race condition enqueue | nvr-video, code | 4 |
| L8 | Двойной appendBuffer в async-функции | nvr-video, code | 4 |
| L9 | data_offset в trun при strip audio | nvr-video, nvr-audio, code | 4 |
| L10 | isSbValid() — проверка MediaSource open | nvr-video, code | 4 |
| L11 | restartMSE — пересоздание сессии | nvr-video, code | 4 |
| L12 | mseEvictOldBuffer — QuotaExceededError | nvr-video, code | 4 |
| L13 | Lazy token resolution в очереди фетчей | nvr-video, code | 4 |
| L14 | tsPct() 0–95% vs mouse 0–100% | nvr-video, code | 4 |
| L15 | new Date(NaN).toISOString() — краш React | code | 5 |
| L16 | Admin sidebar bottom не уезжает вниз (flex layout) | code | 5 |
| L17 | CamerasPage: не грузить mp4 для всех камер | nvr-cameras, code | 4 |
| L18 | Статус камеры — всегда по основному stream_id | nvr-cameras | 4 |
| L19 | Hikvision субпоток — только /Streaming/Channels/102 | nvr-cameras | 4 |
| L20 | MSE-плеер НЕ поддерживает H.265 — main только H.264 | nvr-video, nvr-cameras | 6 |
| L21 | Архивный плеер открывается ТОЛЬКО из «Камер» или «Раскладок» | nvr-video, ux-ilya | 5 |
| L22 | Exporter — битрейт ограничен, не «копия» | nvr-video | 11 |

### 🎤 Audio (5)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L23 | detectAudio через ISAPI для NVR возвращает глобальное аудио | nvr-audio, nvr-cameras | 5 |
| L24 | audio_capable vs has_audio — теория vs реальность | nvr-audio, nvr-cameras | 4 |
| L25 | MaMaison audio_capable отражает setting, не capability | nvr-audio, nvr-cameras | 11 |
| L26 | Архитектура звука NVR (summary, перенесено → modules/audio-architecture) | nvr-audio | 5 |
| L27 | Архивный звук — три независимых бага одновременно | nvr-audio, code | 7 |

### 🐳 Docker / Compose / Build (7)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L28 | Пересобирать API контейнер при backend-изменениях | infra, code | 5 |
| L29 | docker-compose v1: ContainerConfig KeyError | infra | 5 |
| L30 | Docker /proc изоляция | infra, code | 4 |
| L31 | Dockerfile должен быть универсален под любой GPU | infra | 5 |
| L32 | Детекция энкодера через test-encode, не «устройство есть» | infra, code | 11 |
| L33 | ext4 reserved blocks = ~100GB фантомного usage | infra, code | 4 |
| L34 | Auto-pull DEV2 ≠ полное обновление контейнеров | infra, git | 9 |

### 💾 DB / Migrations / Schema (10)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L35 | Осиротевшие записи в archives | db, nvr-cameras | 12 |
| L36 | Экспорт — фильтрация по SQL, не в памяти | db, code | 4 |
| L37 | ArchivePage: передавать stream_id серверу | db, code | 4 |
| L38 | Дубликаты в archives — UNIQUE INDEX | db | 4 |
| L39 | Дубли stream_id в БД: нельзя просто DELETE если есть связанные | db, nvr-cameras | 7 |
| L40 | Bulk UPDATE recording_enabled без проверки | db, nvr-cameras | 5 |
| L41 | Async-endpoints без try/catch + нет глобальных error handlers | code, infra | 7 |
| L42 | Backup-таблицы не должны попадать в миграции/dump | db | 4 |
| L43 | Company в текущей main — НЕ отдельная таблица | db | 14 |
| L44 | Export timezone — через профильную TZ клиента | db, code | 9 |

### 🎛 MediaMTX (11)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L45 | 🚨 recordDeleteAfter: 0s ВСЕГДА | mediamtx, infra | 3 |
| L46 | mediamtx.yml серверно-специфичный — в .gitignore | mediamtx, git, infra | 4 |
| L47 | Sub-stream пути не терять при правках compose/mediamtx | mediamtx, nvr-cameras | 4 |
| L48 | MediaMTX mtxRequest — без query string отбрасывает parsing | mediamtx, code | 3 |
| L49 | recordPath на SSD overlay — catastrophic | mediamtx, infra | 4 |
| L50 | ONVIF PullPoint expires ~10 мин | nvr-cameras, code | 5 |
| L51 | Watchdog пути: TESLATEL vs MaMaison | mediamtx, infra | 4 |
| L52 | Два процесса watchdog одновременно | mediamtx, infra | 5 |
| L53 | Элегантное правило main/sub при добавлении камеры | nvr-cameras, code | 7 |
| L54 | Умные границы main/sub clamp через ISAPI capabilities | nvr-cameras, code | 11 |
| L55 | UI-toggle в БД не равно change в runtime config | mediamtx, db, code | 11 |

### 🔐 Auth / Keycloak (7)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L56 | KC sync: пароль ставить ПОСЛЕДНИМ | auth, code | 4 |
| L57 | KC getRoles empty on first call — retry | auth, code | 4 |
| L58 | KC auth — auto-retry при 401 | auth, code | 4 |
| L59 | offline_access в default-roles | auth | 4 |
| L60 | ROPC flow через /auth/ nginx proxy | auth, infra | 4 |
| L61 | Users.email_verified = false после restore из бэкапа | auth, db | 5 |
| L62 | Keycloak после восстановления пустой | auth, infra | 14 |

### 🌐 Network / SSL / Domains (8)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L63 | Nginx кэширует старый IP Keycloak | infra, auth | 5 |
| L64 | Netplan: имя интерфейса меняется после замены железа | infra | 5 |
| L65 | Скачивание больших файлов — одноразовый токен | code | 5 |
| L66 | Cache-Control no-cache на index.html | infra, code | 5 |
| L67 | ⭐ Ошибка в исходных инструкциях не значит «так и есть» | bot-work, ssh, infra | 6 |
| L68 | Два default route = asymmetric routing | infra | 5 |
| L69 | sshpass × много команд = fail2ban бан | ssh, infra | 4 |
| L70 | Chrome MCP делит сессию с пользователем (self-signed certs) | tooling | 9 |

### 📦 Releases / LUS / Apply (9)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L71 | Параллельные коммиты в main + production — техдолг | git, lus | 8 |
| L72 | Не смешивать исправление инсталлера с доработкой системы | lus, infra | 8 |
| L73 | Heredoc stdin к интерактивному bash-скрипту: каждая строка = один read | bot-work, code | 8 |
| L74 | Pre-flight checks в инсталлере спасают клиента | lus, code | 5 |
| L75 | Приватный git-репо требует PAT в URL для git clone в скриптах | git, infra | 6 |
| L76 | install-v3.sh интерактивные prompts несовместимы с ботами | lus, bot-work | 5 |
| L77 | Bootstrap paradox для self-update механики | host-agent, lus, infra | 12 |
| L78 | «Failed to fetch» / «Unexpected token '<'» во время apply ≠ failed apply | host-agent, lus | 6 |
| L79 | git commit без body теряет ценность для release notes | git, lus | 28 |

### 🤖 Боты / оркестрация / brief discipline (14)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L80 | Паттерн патчей на сервер — scp + node inject | bot-work, ssh, code | 4 |
| L81 | ⭐ Перед планированием эпика — читать git log на теги фаз | bot-work, git | 12 |
| L82 | ⭐ Batch-операции должны учитывать assignments-in-flight | bot-work, code | 11 |
| L83 | ⭐ Бот может расширить scope если план логичен и безопасен | bot-work | 9 |
| L84 | ⭐ Проверять hostname перед началом работы с SSH-коннектором | bot-work, ssh | 4 |
| L85 | ⭐ Пауза 2 сек между paste-buffer и send-keys Enter | bot-work, tooling | 4 |
| L86 | Motion events API не имеют поля id (проверять структуру) | bot-work, code | 5 |
| L87 | ⭐ Parser/serializer несоответствие на больших задачах одного бота | bot-work, code | 9 |
| L88 | ⭐ Бриф «замени X Y → Z» бот понимает буквально | bot-work | 11 |
| L89 | ⭐ Не разделяю scope задачи и scope сессии | bot-work | 8 |
| L90 | ⭐ Спрашиваю когда не надо, не спрашиваю когда надо | bot-work | 8 |
| L91 | ⭐ Параллельная работа двух ботов (P64) | bot-work, git, code | 10 |
| L92 | Mockup-страницы с фиктивными данными — инструмент согласования | nvr-video, ux-ilya | 5 |
| L93 | SectionHeader — паттерн зрелый, переиспользован на 3 разделах | code | 10 |

### 💬 Коммуникация с Ильёй (3)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L94 | ⭐ TESLATEL = полигон, архив некритичен | ux-ilya | 11 |
| L95 | ⭐ Сводки Илье на продуктовом языке, не техническом | ux-ilya, bot-work | 20 |
| L96 | Кнопка переключения темы показывает КУДА перейдёшь | ux-ilya, code | 11 |

### 🛠 Tooling / Claude Desktop / MCP / TUI (14, L104 пропущен)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L97 | CSS в index.css — ТОЛЬКО добавлять | code | 8 |
| L98 | useEffect + нестабильные deps = interval не работает | code | 9 |
| L99 | ⭐ Claude Desktop vs Claude в Chrome — разные клиенты | bot-work, tooling | 7 |
| L100 | ⭐ tmux load-buffer + paste-buffer надёжнее heredoc | bot-work, tooling | 7 |
| L101 | ⭐ tmux paste-buffer -p для bracketed paste в Claude Code TUI | bot-work, tooling | 5 |
| L102 | Лимит ssh_execute в wincli = ~4000 символов | bot-work, tooling | 6 |
| L103 | Флаг --thinking в Claude Code заменён на --effort | tooling | 10 |
| L105 | ⭐ CLAUDE.md съедает контекст бота на старте | bot-work, tooling | 6 |
| L106 | --permission-mode auto недоступен на Claude Max плане | tooling | 9 |
| L107 | ⭐ VPS-хостер может заморозить VM | infra | 5 |
| L108 | ⭐ Перед github MCP write проверять локальные изменения | git, vault, tooling | 6 |
| L109 | ⭐ .bak_* файлы обманчивы — источник правды git history | git, code | 11 |
| L110 | Python <3.12 f-string + bash quoting — паттерн «extract to var» | code, lus | 18 |
| L111 | ⭐ TUI Claude Code: «призрачный» input после rating prompt | bot-work, tooling | 10 |
| L112 | Design tokens loop — общий CSS-токен для двух страниц | code | 16 |

### ⚙ Инфраструктура / SSH / Backups / Recovery (8)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L113 | БД на системном SSD выживает при замене HDD | infra, db | 5 |
| L114 | Бэкап cron не работает если БД недоступна | infra, db | 5 |
| L115 | setup_disks.sh форматирует диск — mkfs убивает данные | infra | 4 |
| L116 | os.path.relpath() через mount points | infra, code | 4 |
| L117 | inotify не следует за symlinks | infra, code | 5 |
| L118 | Timezone на границе дня | db, code | 11 |
| L119 | nvr-recovery.sh v1/v2 — 6 багов, исправлены в v3.0 | infra | 11 |
| L120 | Не все IP-устройства в cameras — это IP-камеры | nvr-cameras | 12 |

### 🎙 Jarvis (Voice Assistant — отдельный проект) (10)

| L# | Заголовок | Теги | LOC |
|---:|---|---|---:|
| L121 | «Plugin фреймворк» из README может оказаться «референсной реализацией» | jarvis | 7 |
| L122 | Whisper с initial_prompt — источник галлюцинаций на коротких записях | jarvis | 7 |
| L123 | Silence detection по peak amplitude не работает с веб-камерой на -50 dBFS | jarvis | 7 |
| L124 | Веб-камера = недостаточный мик для wake word без клавиатурного триггера | jarvis | 7 |
| L125 | Whisper галлюцинирует в 1 лицо: «открой» → «открываю» | jarvis | 7 |
| L126 | Snap-приложения на Wayland не разворачивают окно при повторном Activate | jarvis, infra | 7 |
| L127 | `gio launch <.desktop>` — правильный способ открыть приложение | jarvis, infra | 5 |
| L128 | Voice assistant pipeline требует видимых звуковых вех | jarvis | 5 |
| L129 | pre_speech_timeout_sec критичен для «естественного» обращения | jarvis | 5 |
| L130 | Не путать voice satellite (LVA) ≠ desktop assistant (Jarvis) | jarvis | 9 |

---

## Условные обозначения

- ⭐ — **критичные универсальные** уроки, особенно важные для digital-company бот-работы
- LOC — приблизительная длина урока в строках (для оценки чтения)
- L104 — пропущен (перенесён в WhisperLocal/LESSONS, см. `LESSONS.md §Конвенция`)

---

## Связано

- [[NVR-2026/LESSONS]] — полный текст всех уроков (источник правды)
- [[CRITICAL-RULES]] — поведенческие правила; некоторые ссылаются на L#
- [[PRINCIPLES-INDEX]] — навигация по принципам (парный документ)
- [[NVR-2026/IDEAS/2026-05-25-LESSONS-PRINCIPLES-RESTRUCTURE]] — обоснование этой реструктуризации
- [[README]] — точка входа в `claude/`

---

*Этап 1 реструктуризации LESSONS+PRINCIPLES. Создано Architect-ботом digital-company 25.05.2026 по запросу Ильи.*
*При добавлении нового урока в `LESSONS.md` — добавить строку в этот индекс с тегами `applies-to`.*
