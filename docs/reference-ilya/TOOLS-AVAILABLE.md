# 🛠 Инструменты доступные команде Digital Company

> Обновлено: 2026-06-26 (+markitdown; роли 12: +coder-3, +security) | 2026-06-06 v2 (AI-стек verified)
> Источник истины: этот файл. CLAUDE.md ролей будут обновлены Tech Writer'ом в следующей сессии.

## Где работают боты

Все **10 ролей** живут в `~/digital-company/agents/<role>/` на машине **buka-home** (Ubuntu 26.04).
Bash из tmux pane наследует PATH машины. Имеют SSH-ключи `~/.ssh/digital_company_deploy`
для доступа к серверам (dev2, lus, bot, mamaison, core, ainode).

**tmux session `company` — карта окон (актуально 2026-06-06):**

| Window | Роль | Описание |
|---|---|---|
| 0 | control | Управление / оркестратор |
| 1 | architect | Архитектор |
| 2 | dispatcher | Диспетчер |
| 3 | coder-1 | Кодер-1 |
| 4 | coder-2 | Кодер-2 |
| 5 | reviewer | Ревьюер |
| 6 | tester | Тестировщик |
| 7 | writer | Tech Writer |
| 8 | devops | DevOps |
| 9 | analyst | Аналитик |
| 10 | designer | Дизайнер |

## CLI инструменты (по ролям)

### Для всех — базовое
- `git` 2.53.0, `node` 22.22.1, `npm` 9.2.0, `python3` 3.14.4 (pyenv), `pipx` 1.8.0
- `ssh`, `curl`, `wget`, `jq`, `pip3` — стандартные
- **`eslint` v10.4.1** ✨updated 2026-05-30 — `~/.npm-global/bin/eslint` (был v6.4.0 в /usr/local/bin/, теперь user-level и current version)
- **`prettier` 3.8.3** ✨installed 2026-05-30 — `~/.npm-global/bin/prettier` (JS/TS/JSON/CSS форматтер)
- **`ruff` 0.15.15** ✨installed 2026-05-30 — `~/.local/bin/ruff` (Python линтер+форматтер через pipx)
- **`markitdown` 0.1.6** ✨installed 2026-06-26 — `~/.local/bin/markitdown` (Microsoft, MIT, через pipx; форматы docx/pdf/pptx/xls/xlsx/outlook). Конвертирует офисные документы → Markdown. Применение: препроцессор для RAG/индексации, обработка клиентских файлов (ТЗ/договоры/декки), vault-документация, n8n-пайплайны. Вызов: `markitdown file.pdf > out.md`. НЕ для NVR. Качество: текст+таблицы — хорошо; сложные сканы — нужен OCR-бэкенд (az-doc-intel). Доустановка форматов: `pipx inject markitdown 'markitdown[audio-transcription,youtube-transcription]'`.

### Tester
- **`playwright`** 1.60.0 — `/usr/local/bin/playwright`
  - Доступен сам CLI и пакет `@playwright/test`
  - При первом использовании может потребоваться `npx playwright install chromium`
    (~150MB, разово)
  - Пример: `npx playwright test tests/admin-overview.spec.js`
- **`newman`** 6.2.2 — `/usr/local/bin/newman`
  - Для запуска Postman collections (API regression)
  - Пример: `newman run collection.json --reporters cli,json`
- **`k6`** v2.0.0 — `/usr/local/bin/k6`
  - Load testing (синтетика, нагрузочные сценарии)
  - Пример: `k6 run script.js`

### Reviewer (security/static)
- **`semgrep`** 1.163.0 — `/usr/local/bin/semgrep`
  - Static analysis, security rules
  - Пример: `/home/buka/.local/bin/semgrep --config=auto frontend/src/`
- **`gitleaks`** 8.21.2 — `/usr/local/bin/gitleaks`
  - Detection of secrets, tokens, keys в коммитах
  - Пример: `/home/buka/bin/gitleaks detect --source=. --verbose`
  - **Использовать перед каждым merge в main!**

### DevOps
- **`smartctl`** 7.5 — `/usr/sbin/smartctl`
  - SMART-проверки дисков (через ssh на сервер: `ssh dev2 sudo smartctl -A /dev/sda`)
  - Локально на buka-home обычно не нужно
- Через SSH алиасы: `dev2`, `lus`, `bot`, `mamaison`, `core`, `ainode`
- `docker compose`, `git` — на серверах через ssh

### Кодеры (1, 2)
- `eslint` — для JS/JSX line check
- `python3` для bash скриптов сложных операций
- Не пытаться установить новые npm пакеты — у buka-home npm prefix=/usr/local требует sudo

### Analyst (продукт / визионер)
- **web_search** — рынок, конкуренты (Milestone, Genetec, Trassir, Ivideon, Frigate, Flussonic), индустрия-паттерны.
- **playwright** — наш портал (как реализовано) + конкуренты; живое сопоставление, а не по памяти.
- **obsidian** — `MODULES/`, эпики, `DECISIONS/` (что есть и решено).
- Чтение кода (`Read`/`Grep`) — как блок реализован, какие паттерны.
- НЕ пишет код. Модель: `sonnet-4-6 high` (эксперимент 2026-06-05, критерий апа на opus — в `analyst/CLAUDE.md`).

### Designer (форма / UX)
- **Claude Design** — канвас + дизайн-инструменты (макеты, варианты, итерация через чат).
- **playwright** — наш портал вживую (сетка/типографика/компоненты/паттерны) + конкуренты.
- Чтение frontend-кода (`Read`/`Grep`) — существующие компоненты/токены (не плодить новые).
- **obsidian** — frontend/design-system модули, эпики.
- НЕ пишет код — отдаёт спеки/токены Кодерам. Модель: `opus-4-8 high`.

## Что НЕ установлено (если потребуется — попросить Илью)

- `docker` локально на buka-home — деплой только через `ssh dev2`
- `trufflehog` — есть `gitleaks` как альтернатива
- `prettier` — есть `eslint` для line check
- Никаких `pa11y`, `axe-core` (accessibility testing) — пока не в скопе

## Если короткий путь не работает (semgrep, gitleaks)

Использовать ПОЛНЫЕ пути:
- `semgrep`
- `gitleaks`

Это потому что эти 2 инструмента установлены в user-level директории и не в PATH ботов.
В следующей сессии (после `start-company.sh`) — PATH будет обновлён через `~/.bashrc`,
и короткие имена заработают.

## AI-стек (ainode 212.42.45.35 — gate-prep Б-4, 2026-06-06)

> Inventory verified 2026-06-06 (DevOps ACK + Architect sign-off). ⚠️ = installed, pending resolution. Pending-items — секция внизу AI-стека.

### Vision (GPU1 YOLOv8n, BC.3 active)

| Пакет | Версия | Статус |
|---|---|---|
| `torch` (cu118) | 2.3.1+cu118 | PIN: cu118, НЕ cu121 (V100 CC7.0); `torchaudio` 2.3.1, `torchvision` 0.18.1 |
| `ultralytics` (YOLOv8n) | 8.2.103 | — |
| `opencv-python` | 4.11.0 | — |
| `onnxruntime-gpu` | 1.23.2 | установлен, **не используется в 0.4.0** (CUDA 11.8 vs cu12 пакет — инференс через PyTorch) |
| `fastapi` + `uvicorn` | installed (version not in ACK) | vision-service runtime |

**venv:** `/home/buka/vision-native/venv` на ainode  
**Модель:** YOLOv8n на GPU1 (`CUDA_VISIBLE_DEVICES=1`, cuda:0 внутри процесса)  
**Веса + все модели:** `/home/buka/vision-native/models/` на ainode. Disk: 182G used / 565G avail (после установки AI-стека).

**V100 CC7.0 инварианты (обязательно при любых изменениях):**
- `--dtype float16` / `torch.float16` — НЕ `bfloat16` (BF16 не поддерживается)
- `attn_implementation="sdpa"` — НЕ `flash_attention_2` (требует CC ≥ 8.0)
- `torch` cu118 — НЕ cu121+ (CC7.0 граничный, Marlin/FP8 не работают)
- `CUDA_VISIBLE_DEVICES=1` mask → процесс видит cuda:0 (НЕ device_index=1)

### Audio / STT (GPU2 Whisper, Б-4)

| Компонент | Версия | Статус |
|---|---|---|
| **GigaAM-v3** (PRIMARY RU, Сбер) | import OK, 429MB, MIT | Pluggable STT; e2e вариант ✅ (достаточно для 0.4.0 STT-примитива); HF: ai-sage/GigaAM-v3 |
| `faster-whisper` | 1.2.1 | Fallback mixed/multilingual; `sentencepiece` 0.2.1, `hydra-core` 1.3.2 |
| `soundfile` / `librosa` | not in ACK | — |

Pluggable STT (Б-4): GigaAM-v3 как primary RU, faster-whisper как fallback. Детали: `RESEARCH/AI-MODELS-LANDSCAPE.md §6`.

### Transformers Stack (shared, все inference-компоненты)

| Пакет | Версия |
|---|---|
| `transformers` | 4.57.6 |
| `accelerate` | 1.13.0 |
| `safetensors` | 0.7.0 |
| `tokenizers` | 0.22.2 |
| `qwen-vl-utils` | 0.0.14 |
| `huggingface_hub` | 0.36.2 |

### VLM-гибрид (пункт-6 / Б-4+, temporal + anomaly)

| Компонент | Источник | Статус |
|---|---|---|
| **VideoChat-R1.5-7B** | 16GB, AutoConfig ✅ | Temporal grounding, Apache 2.0 |
| **Qwen2.5-VL-7B-Instruct** | 16GB, AutoConfig ✅ | Planner + AnyAnomaly backbone; Apache 2.0 (Qwen2.5+ переехал с кастомной; коммерческое on-prem ✅) |
| **AnyAnomaly** | 13MB, GitHub clone ✅ | Zero-shot anomaly detection, MIT (WACV 2026) |
| **Holmes-VAU-2B** | 4.2GB ⚠️ | Дообучаемый VAD + ATS; trust_remote_code/KeyError → loading отложен на волну LoRA (BAD, +2нед); MIT |

GPU layout для VLM-гибрида: `GPU0`=Qwen planner / `GPU1`=YOLOv8n+classify / `GPU2`=Whisper/VLM. Детали: `RESEARCH/AI-MODELS-LANDSCAPE.md §ADDENDUM`.

### Training / Fine-tune (Б-4/BF, LoRA на 3×V100)

| Пакет | Версия | Назначение |
|---|---|---|
| `deepspeed` | 0.14.5 | ZeRO-2 LoRA training 3×V100; 0.15.x+ не нужен для 0.4.0 базы; пересмотрим на волне LoRA |
| `peft` | 0.19.1 | LoRA/QLoRA адаптеры |
| `accelerate` | 1.13.0 | HuggingFace multi-GPU wrapper (также в Transformers Stack) |
| `datasets` | not in ACK | HIVAU-70k формат для Holmes-VAU fine-tune |

**LoRA run на 3×V100:** ~27 GB/GPU, DeepSpeed ZeRO-2, FP16, `flash_attn` отключить.

### ⏳ AI-стек: Pending (не считать закрытыми)

| Item | Статус |
|---|---|
| HolmesVAU-2B loading config | AutoConfig trust_remote_code → отложено на волну LoRA (+2 нед) |

> ⚠️ **HolmesVAU-2B venv-конфликт (критично для волны LoRA):** репо требует `transformers==4.37.2` / `torch==2.1.2` / `flash-attn` — несовместимо с V100 CC7.0 и нашим общим venv (`transformers=4.57.6`, `torch cu118`). **Решение:** отдельный изолированный venv при волне LoRA. Планировать +2нед overhead.

---

## Docs-automation (Tech Writer, установлено 31.05.2026)

- **lychee 0.24.2** — dead-link checker для markdown/HTML. `lychee --no-progress <file.md>` или `lychee .` по vault. Установлен на buka-home.
- **markdownlint-cli 0.48.0** — markdown linter (headings, списки, frontmatter). `markdownlint <file.md>` или `markdownlint '**/*.md'`. Установлен на buka-home. Конфиг: `.markdownlint.json` в корне vault.

## Designer toolchain (Норман, установлено 2026-06-14 на buka-home)

> Запрошены Норманом по итогам карт-бланш редизайна (его реальные «слепые пятна»). Все — npm global на **buka-home**. ⚠️ На smirnov-ubuntu НЕ установлены (ставить при работе там — см. столбец «Машина» в TOOLS-REQUESTS).

| Инструмент | Версия | Что делает | Как звать |
|---|---|---|---|
| **pa11y** | 9.1.1 | a11y + контраст WCAG AA автопроверка (закрывает главный слепой пятак — контраст на глаз) | `pa11y <url/file>` |
| **@axe-core/cli** (`axe`) | 4.11.3 | accessibility-аудит рендера | `axe <url>` |
| **pixelmatch** | 7.2.0 | попиксельный diff рендеров (мокап vs сборка кодеров, ловит регрессии/сдвиги) | npm-пакет, `import pixelmatch` |
| **pngjs** | 7.0.0 | чтение/запись PNG для pixelmatch | npm-пакет |
| **lucide-static** | 1.18.0 | те же crisp-иконки, что у кодеров, прямо в мокап | npm-пакет (SVG-ассеты) |
| **svgo** | 4.0.1 | оптимизация/чистка SVG | `svgo <file>` |
| **stylelint** (+config-standard) | 17.13.0 | линтинг CSS — дубли, специфичность, до хендоффа кодерам | `stylelint <file.css>` |
| **style-dictionary** | 5.4.4 | один источник токенов → тёмная + светлая тема системно | `style-dictionary build` |

**Поток Нормана с новыми инструментами:** генерация → рендер (playwright) → `pa11y`/`axe` (контраст AA) → `pixelmatch` (diff с эталоном) → `stylelint` (CSS-гигиена) → правка. Светлая тема — через `style-dictionary`.

## Coders + Reviewer CSS-toolchain (установлено 2026-06-14 на buka-home)

> Под задачу чистки старого CSS (редизайн админки 15.06) + общую CSS-гигиену production-кода.

| Инструмент | Версия | Что делает | Кому | Машина |
|---|---|---|---|---|
| **stylelint** (+config-standard) | 17.13.0 | линтинг production-CSS: дубли, специфичность, хардкод hex (P51) | **Coders** (пишут), **Reviewer** (verify-гейт: убедиться 0 ошибок) | buka-home |
| **purgecss** | 8.0.0 | поиск МЁРТВОГО/неиспользуемого CSS — какие классы нигде не используются | **Coders** (чистка старого CSS при переработке) | buka-home |

**Кодеры:** при переработке (напр. редизайн админки) — `purgecss` находит мёртвые стили → удалить; `stylelint` → дубли/специфичность до пуша.
**Ревьювер (Кнут):** `stylelint` как verify — прогнать на финальном CSS, убедиться что кодеры почистили (0 ошибок), НЕ для написания. purgecss ему не нужен.

## Personal Vault RAG (все роли)

- **CLI:** `cd ~/personal-local-rag && python3 -m code.cli search "<query>" [--top-k 5] [--mode hybrid|vector|bm25] [--format json|text]`
- **MCP:** инструменты `search_vault` и `get_chunk_context` в Claude Desktop (после настройки конфига)
- **SKILL:** `~/digital-company/skills/personal-local-rag/SKILL.md`
- **Установлен:** 2026-05-30 (Phase 4)

## Сообщить новые потребности

Если роль нуждается в инструменте которого нет — записать запрос в:
`NVR-2026/claude/TOOLS-REQUESTS.md` (раздел "На рассмотрении"). Илья и Claude-оркестратор
решают на следующей retro.
