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
export BOTS_CLAUDE_BIN BOTS_MODEL  # модель/бинарь Claude для роли (roles/models.json), см. preflight п.8
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
  # АВТО-САЛЬВАЖ (29.09.2026): работа прошлого прогона не должна молча исчезать при сбросе.
  # Дважды (#49 17.09, #56 24.09) reset снёс коммит кодера перед запуском ревьюера.
  # Вложенные worktree субагентов (.claude/worktrees/*): работа кодера может быть ТОЛЬКО там (30.09, #61).
  for WT in "$GATE"/.claude/worktrees/*/; do
    [ -d "$WT/.git" ] || [ -f "$WT/.git" ] || continue
    if [ -n "$(git -C "$WT" status --porcelain)" ]; then
      git -C "$WT" add -A && git -C "$WT" -c user.name=bot-run -c user.email=bot-run@local commit -q -m "salvage: вложенный worktree перед сбросом ($(date +%F\ %T))" || true
    fi
    WH=$(git -C "$WT" rev-parse HEAD)
    if ! git -C "$SRC" branch -a --contains "$WH" 2>/dev/null | grep -q . ; then
      WB="salvage/$REPO-wt-$(basename "$WT")-$(date +%Y%m%d-%H%M%S)"
      git -C "$SRC" fetch -q "$WT" "HEAD:refs/heads/$WB" && echo "САЛЬВАЖ: worktree $(basename "$WT") ($WH) -> $WB" >&2
      git -C "$SRC" push -q origin "$WB" 2>/dev/null && echo "САЛЬВАЖ: $WB запушена" >&2 || echo "САЛЬВАЖ: push $WB не удался" >&2
    fi
  done
  if [ -n "$(git -C "$GATE" status --porcelain --untracked-files=normal | grep -vE 'CLAUDE.local.md|\.claude/' )" ]; then
    git -C "$GATE" add -A -- . ':!CLAUDE.local.md' ':!.claude' && \
    git -C "$GATE" -c user.name=bot-run -c user.email=bot-run@local commit -q -m "salvage: незакоммиченное из гейта перед сбросом ($(date +%F\ %T))" || true
  fi
  GH=$(git -C "$GATE" rev-parse HEAD)
  if ! git -C "$SRC" merge-base --is-ancestor "$GH" "$(git -C "$SRC" rev-parse HEAD)" 2>/dev/null \
     && ! git -C "$SRC" branch -a --contains "$GH" 2>/dev/null | grep -q . ; then
    SB="salvage/$REPO-$(date +%Y%m%d-%H%M%S)"
    git -C "$SRC" fetch -q "$GATE" "HEAD:refs/heads/$SB" && \
      echo "САЛЬВАЖ: несохранённая работа гейта ($GH) -> ветка $SB в $SRC" >&2
    git -C "$SRC" push -q origin "$SB" 2>/dev/null && echo "САЛЬВАЖ: $SB запушена в origin" >&2 || \
      echo "САЛЬВАЖ: push $SB не удался — ветка только локально в $SRC" >&2
  fi
  # BOT_BASE — явная база гейта (ветка/коммит канона), напр. BOT_BASE=bot/lte-cov-56 для T2-ревью.
  git -C "$GATE" fetch -q "$SRC" "${BOT_BASE:-HEAD}"
  git -C "$GATE" reset -q --hard FETCH_HEAD
  git -C "$GATE" clean -qfd
  # Имя ветки гейта = база прогона (04.10.2026: tester честно вернул BLOCKED — гейт стоял на ветке
  # со старым именем bot/vols-gold-54 при правильном коде — сборку нельзя было подтвердить).
  GBR="${BOT_BASE:-$(git -C "$SRC" rev-parse --abbrev-ref HEAD 2>/dev/null || echo gate-work)}"
  [ "$GBR" = "HEAD" ] && GBR=gate-work
  git -C "$GATE" checkout -q -B "$GBR" 2>/dev/null || true
  echo "гейт: база ${BOT_BASE:-HEAD канона} -> $(git -C "$GATE" rev-parse --short HEAD) (ветка $(git -C "$GATE" rev-parse --abbrev-ref HEAD))"
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
# Идентификатор прогона задаётся ЗДЕСЬ, один на весь прогон: иначе предполёт,
# оркестратор и журнал говорили бы о разных прогонах.
RUN_ID="${BOTS_RUN_ID:-$REPO-$(date +%Y%m%d-%H%M%S)-$ROLE}"
echo "run-id: $RUN_ID"

cd "$BOTS_DIR"
env PYTHONPATH="$BOTS_DIR" BOTS_CHECKOUT="$GATE" BOTS_ROLE="$ROLE" \
    BOTS_RUN_ID="$RUN_ID" python3 -P -m orchestrator "$@"
