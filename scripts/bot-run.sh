#!/bin/bash
# Универсальный запуск бота-роли для ЛЮБОГО проекта (не только Bots).
# Usage:
#   bot-run.sh <repo> <role> run-next [--timeout N]
#   bot-run.sh <repo> <role> run-bot --file <brief> [--timeout N]
# Флаги: --no-preflight  пропустить чеклист (только для отладки, НЕ для платного прогона)
# Примеры:
#   bot-run.sh telecom-digital-twin coder run-next --timeout 1200
#   bot-run.sh Bots reviewer run-bot --file /tmp/brief.txt
#
# Механика (playbook L65/L66):
# - гейт-клон ~/work/gates/<repo>: клон с ЛОКАЛЬНОГО канонического клона
#   ~/work/<repo>, origin удалён, credential.helper пуст — бот не может пушить;
# - роль подключается копированием roles/<role>.md -> CLAUDE.local.md в гейте;
# - оркестратор из репо Bots, очередь issue целевого репо (BOTS_REPO=<repo>);
# - перед прогоном гейт обновляется fetch'ем из локального клона (reset+clean).
# - ДО запуска обязателен scripts/preflight.sh: любой FAIL останавливает прогон
#   до создания процессов (частичного запуска не бывает).
# Артефакты бот оставляет в гейте — забирает оператор (это и есть гейт).
set -euo pipefail
REPO="${1:?repo}"; ROLE="${2:?role}"; shift 2
SKIP_PREFLIGHT=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--no-preflight" ]; then SKIP_PREFLIGHT=1; else ARGS+=("$a"); fi
done
set -- ${ARGS[@]+"${ARGS[@]}"}
BOTS_DIR="${BOTS_HOME:-$HOME/work/Bots}"
SRC="$HOME/work/$REPO"
GATE="$HOME/work/gates/$REPO"
[ -d "$SRC/.git" ] || { echo "нет локального клона $SRC" >&2; exit 1; }
[ -f "$BOTS_DIR/roles/$ROLE.md" ] || { echo "нет роли $ROLE" >&2; exit 1; }
. "$HOME/.bots/env"
export BOTS_REPO="$REPO"

if [ "$SKIP_PREFLIGHT" = "1" ]; then
  echo "ВНИМАНИЕ: pre-flight пропущен (--no-preflight)" >&2
else
  "$BOTS_DIR/scripts/preflight.sh" "$REPO" "$ROLE" || exit 1
fi

if [ ! -d "$GATE/.git" ]; then
  git clone -q "$SRC" "$GATE"
  git -C "$GATE" remote remove origin
  git -C "$GATE" config --local credential.helper ""
else
  git -C "$GATE" fetch -q "$SRC" HEAD
  git -C "$GATE" reset -q --hard FETCH_HEAD
  git -C "$GATE" clean -qfd
fi
# граница гейта перепроверяется ПОСЛЕ подготовки — до неё гейта могло не быть
if git -C "$GATE" remote | grep -q . ; then
  echo "STOP: в гейте появился remote — граница записи не доказана" >&2; exit 1
fi
LOCK="$GATE/.bot-run.lock"
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

cp "$BOTS_DIR/roles/$ROLE.md" "$GATE/CLAUDE.local.md"
grep -q "^CLAUDE.local.md$" "$GATE/.gitignore" 2>/dev/null || true
# ⚠ НЕ делать `cd "$GATE"` перед запуском оркестратора. При `python -m` в
# sys.path[0] попадает cwd, а гейт — клон этого же репозитория, значит его
# КОПИЯ `orchestrator/` перекрывает настоящую. Последствия: (1) правки раннера
# не применяются (ловилось смоуком песочницы 14.09, playbook L91), (2) бот,
# имеющий запись в гейт, может подменить код оркестратора для следующего
# прогона — то есть выполнить код ВНЕ песочницы. Каталог бота передаётся
# переменной BOTS_CHECKOUT (config.CHECKOUT), её читает run_bot.
cd "$BOTS_DIR"
env PYTHONPATH="$BOTS_DIR" BOTS_CHECKOUT="$GATE" python3 -P -m orchestrator "$@"
