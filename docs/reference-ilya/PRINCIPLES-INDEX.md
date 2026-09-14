---
type: reference
project: claude
status: active
created: 2026-05-25
updated: 2026-05-27
scope: ../PRINCIPLES.md (67 principles P1-P67 + P_STICKY + P-Park + P-Publish, P60 missing)
purpose: компактная навигация — заменяет чтение PRINCIPLES.md целиком при старте бота
---

# PRINCIPLES Navigation Index

## Зачем этот файл

Полный `../PRINCIPLES.md` = **100 KB / 1347 строк / 67 принципов** + P_STICKY + sub-rules (P-M-A..F, P-D-A..E, P-FF-1..8). При старте бота — большая часть не востребована (NVR-specific принципы не нужны при работе с Jarvis, FF-принципы не нужны при работе с инфрой и т.п.).

**Workflow:**
1. **При старте** бот читает этот индекс (~6 KB).
2. **По мере работы** — читает конкретные P# через `obsidian:read-note "PRINCIPLES#P34"` по тегу/категории.
3. **При добавлении нового принципа** в `PRINCIPLES.md` — обновлять и этот индекс.

**Этот файл — навигация, не источник правды.** Источник — `../PRINCIPLES.md`. При расхождении доверяй ему.

P60 пропущен в нумерации. P_STICKY — sticky-pin принцип без числового номера.

---

## Карта по категориям (быстрый поиск)

| Категория | Описание | Принципы |
|---|---|---|
| `core-active` | **Универсальные, всегда применимые** для любого проекта/роли | P3, P5, P19, P20, P28, P33, P34, P50, P66, P67, P_STICKY, P-Park, P-Publish |
| `vault-active` | Работа с vault, git, документация | P26, P27, P35, P36, P37, P38, P43, P45, P46, P49 |
| `bot-orchestration` | Работа Claude-оркестратора с ботами | P6, P9, P22, P29, P40, P41, P44, P62, P64 |
| `nvr-cameras` | Камеры, ISAPI, ONVIF (NVR-specific) | P11, P13, P30, P31, P42 |
| `nvr-mediamtx` | MediaMTX (NVR-specific, critical в production) | P1, P2, P16 |
| `nvr-infra` | NVR серверы, диски, deploy, сеть | P4, P7, P8, P10, P12, P14, P15, P17, P18, P21, P23, P24, P25, P32, P47, P48, P51 |
| `nvr-ui` | NVR frontend (admin/client portal, UI patterns) | P32, P51, P61, P63 |
| `ff-lus` | Feature Flags / License model (LUS-specific) | P52, P53, P54, P55, P56, P57, P58, P59 |
| `outdated-or-meta` | Устарели или мета-правила, могут быть переселены | P65 (Windows-машина устарела), P39 (актуально, но узко по NVR git) |

---

## Per-role hints для digital-company

| Роль | Обязательные принципы |
|---|---|
| **Architect** | core-active + bot-orchestration + P34, P39, P44, P62, P66, P67, **P-Park**, **P-Publish** |
| **Dispatcher** | core-active + bot-orchestration + P19, P40, P41, P62, P64, **P-Park**, **P-Publish** |
| **Coder-1 / Coder-2** | core-active + nvr-infra (если NVR) + P3, P5, P6, P7, P8, P19, P20, P25, P50, P64, **P-Park** |
| **Reviewer** | core-active + P3, P5, P19, P20, P64, P66, **P-Park** + категория проекта (nvr-* / ff-*) |
| **Tester** | core-active + P9, P11, P14, P19, P32, P57-P58 (если FF), **P-Park** |
| **Tech Writer** | vault-active + P26, P27, P35, P36, P37, P38, P43, P45, P46, P49, P-M-A..F, P-D-A..E, **P-Park**, **P-Publish** (для финальных handover'ов релизов) |
| **DevOps** | core-active + nvr-infra + P1, P2, P5, P7, P8, P10, P15, P21, P23, P25, P48, P50, **P-Park**, **P-Publish** (главный исполнитель LUS publish шага) |

---

## Полная таблица принципов

### 🔴 Critical / Production-safety (NVR-specific)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P1 | MediaMTX на MaMaison НЕ ТРОГАТЬ без согласования | nvr-mediamtx | active | 5 |
| P2 | `recordDeleteAfter: 0s` — проверять после рестарта MediaMTX | nvr-mediamtx | active | 11 |
| P3 | Бот ВСЕГДА делает `git push origin main` после коммита | core-active | active | 5 |
| P4 | CSS только ДОБАВЛЯТЬ, никогда не удалять вручную | nvr-ui | active | 5 |
| P5 | НИКОГДА `docker-compose rm -sf` без явного указания сервиса | core-active | active | 9 |

### 🟡 Рабочий протокол (NVR + general)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P6 | Одна задача за раз, с самопроверкой | bot-orchestration | active | 15 |
| P7 | Backend изменения = пересборка API контейнера | nvr-infra | active | 4 |
| P8 | Перед `git pull` сохранять локальные server-specific файлы | nvr-infra | active | 10 |
| P9 | Режим "только диагностика" существует и используется | bot-orchestration | active | 5 |
| P10 | Docker compose версии различаются (v1 TESLATEL / v2 MaMaison) | nvr-infra | active | 13 |

### 🔵 Архитектурные принципы (NVR-specific)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P11 | Система NVR ВСЕГДА управляет подключёнными камерами | nvr-cameras | active | 5 |
| P12 | TESLATEL — dev/test полигон для ВСЕЙ архитектуры | nvr-infra | active | 6 |
| P13 | Вендоры камер: HIK/HiWatch + Dahua, больше никого | nvr-cameras | active | 4 |
| P14 | MaMaison — one-node prod без резервирования (выбор клиента) | nvr-infra | active | 5 |
| P15 | Recovery.sh принимает новые диски БЕЗ вопросов | nvr-infra | active | 5 |
| P16 | Запись: MediaMTX native, без внешних ffmpeg | nvr-mediamtx | active | 6 |
| P17 | Отдача видео: X-Accel-Redirect zero-copy через nginx | nvr-infra | active | 5 |
| P18 | Git workflow: main → production через cherry-pick | nvr-infra, git | active | 14 |

### 🟢 Двойное подтверждение (core)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P19 | Bulk операции требуют двойного confirm | core-active | active | 6 |
| P20 | Удаление данных = бэкап сначала | core-active | active | 4 |
| P21 | Перед массовой операцией на production — репетиция на TESLATEL | nvr-infra | active | 8 |

### 🟣 Коммуникация Claude ↔ бот

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P22 | Формат задачи боту | bot-orchestration | active | 18 |
| P23 | SSH порты нестандартные — не забывать | nvr-infra | active | 5 |
| P24 | tmux сессия называется `mywork`, не `bot` | nvr-infra | active | 4 |
| P25 | Пути различаются между серверами — не хардкодить | nvr-infra | active | 14 |

### ⚪ Принципы для Claude (meta)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P26 | Обращение к памяти vault каждую сессию | vault-active | active | 5 |
| P27 | userMemories — только общее, детали в vault | vault-active | active | 5 |
| P28 | Не предлагать сложные решения когда есть простые | core-active | active | 5 |
| P29 | Отчёт = что сделано + что проверено + что осталось | bot-orchestration | active | 17 |
| P30 | "Возможности" vs "Настройки" — разделять обязательно | nvr-cameras | active | 27 |
| P31 | Скрывать технические детали за простыми пресетами | nvr-ui | active | 20 |
| P32 | Визуальная проверка UI — сразу после деплоя | nvr-ui, core-active | active | 11 |
| P33 | Не планировать сроки за Илью | core-active | active | 10 |

### 🟣 Для Claude-desktop (роль контролёра)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P34 | Моя роль — контролёр стратегии, не кодер | core-active | active | 25 |
| P35 | Vault — это git-репо, записи требуют push | vault-active | active | 18 |
| P36 | Начало сессии — проверка git-sync vault | vault-active | active | 9 |
| P37 | Vault имеет две ветки: код и заметки | vault-active | active | 13 |
| P38 | Отчёт каждую сессию в человекочитаемой форме | vault-active | active | 13 |
| P39 | Перед планированием — `git log --grep` по основному репо | bot-orchestration | active | 20 |
| P40 | Работа с ботом идёт через Илью — ожидать подтверждение | bot-orchestration | active | 22 |
| P41 | Параллельная работа: бот делает, мы обсуждаем и документируем | bot-orchestration | active | 14 |
| P42 | Логи всех системных изменений камер и объектов | nvr-cameras | candidate | 31 |

### 🟣 Lifecycle / Vault hygiene

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P43 | Жизненный цикл идеи: FUTURE → BACKLOG → TODO → REAL | vault-active | active | 52 |
| P44 | Бриф боту = универсальный под продукт, конкретное железо — пример | bot-orchestration | active | 50 |
| P45 | В конце сессии — ревизия vault на дубли и консолидация | vault-active | active | 56 |
| P46 | Бриф для бота — расходный материал | vault-active | active | 50 |
| P47 | Инструмент ≠ продукт: не смешивать разворачивание и доработку | nvr-infra | active | 26 |
| P48 | Размещение системы и архива: M.2/SSD → система, HDD → архив | nvr-infra | active | 81 |
| P49 | Файл-план дня удаляется в конце дня | vault-active | active | 44 |
| P50 | Master-сервер один — git pull только на нём (DEV2) | core-active, nvr-infra | active | 31 |
| P51 | Цвета и базовые размеры — только через design tokens | nvr-ui | active | 38 |
| P_STICKY | Sticky-pin items в TODO/BACKLOG | vault-active, core-active | active | 26 |

### 🚦 Feature Flags / Licensing (LUS-specific, кандидат на переезд в modules/feature-flags.md)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P52 | Never break the core (FF) | ff-lus | domain-specific | 19 |
| P53 | Silent absence over loud restriction (FF) | ff-lus | domain-specific | 14 |
| P54 | Forward compatibility (FF) | ff-lus | domain-specific | 11 |
| P55 | Source of truth hierarchy (FF) | ff-lus | domain-specific | 13 |
| P56 | Audit license changes (FF) | ff-lus | domain-specific | 15 |
| P57 | Graceful degradation (FF) | ff-lus | domain-specific | 15 |
| P58 | Check at every level (FF) | ff-lus | domain-specific | 13 |
| P59 | Naming convention (FF) | ff-lus | domain-specific | 26 |

### 🆕 Поздние принципы (10.05.2026+)

| P# | Заголовок | Категория | Статус | LOC |
|---:|---|---|---|---:|
| P61 | Разделение Admin Portal и Client Portal | nvr-ui | active | 21 |
| P62 | Архитектура 3-бот разработки (N+1 Ultra Reviewer) | bot-orchestration | active | 19 |
| P63 | Уникальность имён разделов и маршрутов | nvr-ui | active | 17 |
| P64 | Параллельные боты на одном файле = риск merge регрессии | bot-orchestration, git | active | 36 |
| P65 | Claude имеет полный доступ к Windows-машине через workingDir | outdated-or-meta | **deprecated** (Ubuntu везде с 19.05) | 60 |
| P66 | Системный подход вместо обхода коряг | core-active | active | 36 |
| P67 | Изоляция параллельных команд (NVR/SKUD/n8n) | core-active | active | 45 |
| P-Park | Non-blocking workflow (парк → следующее → разбор скопом) | core-active, bot-orchestration | active (25.05.2026) | 45 |
| P-Publish | Релиз не завершён без LUS publish (финальный шаг) | core-active, bot-orchestration | active (25.05.2026) | 60 |

---

## Sub-правила (упомянуты в CRITICAL_RULES §7)

| Код | Где | Описание |
|---|---|---|
| P-M-A | CRITICAL_RULES §7.4.1 | Работа над модулем не закрывается без обновления modules/ |
| P-M-B | CRITICAL_RULES §7.4.3 | Modules пишут ТОЛЬКО люди — боты не правят |
| P-M-C | CRITICAL_RULES §7.4.2 | Modules — первый шаг работы (читать раньше handover) |
| P-M-D | CRITICAL_RULES §7.4.4 | Periodic audit modules/ раз в неделю |
| P-M-E | CRITICAL_RULES §7.4.5 | Frontmatter modules обязателен с полем `updated:` |
| P-M-F | CRITICAL_RULES §7.4.6 | Связь modules/ ↔ decisions/ (закрытие decision → факт в modules) |
| P-D-A | CRITICAL_RULES §7.5 | Один финальный daily-артефакт каждого типа на день |
| P-D-B | CRITICAL_RULES §7.5 | Frontmatter обязателен для daily-артефактов |
| P-D-C | CRITICAL_RULES §7.5 | Тематические отчёты — отдельная категория |
| P-D-D | CRITICAL_RULES §7.5 | При нескольких артефактах за день — переименовать в конце |
| P-D-E | CRITICAL_RULES §7.5 | Эта работа делается в конце сессии |
| P-FF-1..8 | PRINCIPLES P52-P59 | Старые синонимы FF-принципов (см. таблицу выше) |

---

## Условные обозначения

- **active** — принцип применим сейчас, follow it
- **domain-specific** — применим только в своём домене (LUS/FF не нужен для не-LUS работы)
- **candidate** — заявлен, но не реализован полностью (например P42 audit log)
- **deprecated** — устарел, нужна ревизия (P65 — Windows-машины больше нет)
- **outdated-or-meta** — общее мета-правило или потерявшее актуальность

P60 — отсутствует в нумерации (видимо удалён/пропущен исторически).

---

## Открытые вопросы для ревизии PRINCIPLES (Этап 4)

- **P52-P59 (FF)** — переселить в `modules/feature-flags.md`? (см. `ideas/2026-05-25-lessons-principles-restructure §4 Уровень 4`)
- **P65 (Windows-машина)** — пометить `status: deprecated` после reality check, оставить для истории
- **P42 (audit log)** — реализован или всё ещё candidate? Проверить с Кодерами
- **P28 (простые решения), P33 (сроки за Илью)** — мета-правила, не принципы проекта. Кандидаты на переезд в `claude/CRITICAL_RULES` §11 (тон коммуникации)
- **P30 (Возможности vs Настройки), P31 (пресеты)** — узкие NVR-cameras правила. Кандидаты на переезд в `modules/camera-management.md`

Эти вопросы — для Этапа 4 ревизии PRINCIPLES, не для текущей реструктуризации.

---

## Связано

- [[NVR-2026/PRINCIPLES]] — полный текст всех принципов (источник правды)
- [[CRITICAL-RULES]] — концентрат поведенческих правил; ссылается на P-M-*, P-D-*
- [[LESSONS-INDEX]] — навигация по урокам (парный документ)
- [[NVR-2026/IDEAS/2026-05-25-LESSONS-PRINCIPLES-RESTRUCTURE]] — обоснование этой реструктуризации
- [[README]] — точка входа в `claude/`

---

*Этап 1 реструктуризации LESSONS+PRINCIPLES. Создано Architect-ботом digital-company 25.05.2026 по запросу Ильи.*
*При добавлении нового принципа в `PRINCIPLES.md` — добавить строку в этот индекс с категорией и статусом.*
