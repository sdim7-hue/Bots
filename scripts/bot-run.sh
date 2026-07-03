#!/bin/bash
# Универсальный запуск бота-роли для ЛЮБОГО проекта (не только Bots).
# Usage:
#   bot-run.sh <repo> <role> run-next [--timeout N]
#   bot-run.sh <repo> <role> run-bot --file <brief> [--timeout N]
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
# Артефакты бот оставляет в гейте — забирает оператор (это и есть гейт).
set -euo pipefail
REPO="${1:?repo}"; ROLE="${2:?role}"; shift 2
BOTS_DIR="${BOTS_HOME:-$HOME/work/Bots}"
SRC="$HOME/work/$REPO"
GATE="$HOME/work/gates/$REPO"
[ -d "$SRC/.git" ] || { echo "нет локального клона $SRC" >&2; exit 1; }
[ -f "$BOTS_DIR/roles/$ROLE.md" ] || { echo "нет роли $ROLE" >&2; exit 1; }
. "$HOME/.bots/env"
export BOTS_REPO="$REPO"
if [ ! -d "$GATE/.git" ]; then
  git clone -q "$SRC" "$GATE"
  git -C "$GATE" remote remove origin
  git -C "$GATE" config --local credential.helper ""
else
  git -C "$GATE" fetch -q "$SRC" HEAD
  git -C "$GATE" reset -q --hard FETCH_HEAD
  git -C "$GATE" clean -qfd
fi
cp "$BOTS_DIR/roles/$ROLE.md" "$GATE/CLAUDE.local.md"
grep -q "^CLAUDE.local.md$" "$GATE/.gitignore" 2>/dev/null || true
cd "$GATE"
exec env PYTHONPATH="$BOTS_DIR" python3 -m orchestrator "$@"
