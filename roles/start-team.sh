#!/bin/bash
# Bots — tmux-лончер ролей (адаптация start-company.sh Ильи; оригинал —
# docs/reference-ilya/start-company.sh). Целевая схема на Ubuntu-узлах (L10).
# Роль = Claude Code в своей папке с роль-промптом как CLAUDE.md.
# Координация — ТОЛЬКО доска Forgejo (issues+метки), НЕ tmux-релей между окнами.
set -euo pipefail
SESSION="${1:-bots}"
BASE="${BOTS_TEAM_DIR:-$HOME/work/bots-team}"
REPO_ROLES="$(dirname "$(realpath "$0")")"
# Шаг 1 плана ARCH-MULTIAGENT: только coder + reviewer. Расширять по мере зрелости.
ROLES=(coder reviewer)
declare -A MODELS=( [coder]="" [reviewer]="" )   # пусто = модель по умолчанию
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Сессия '$SESSION' уже запущена: tmux attach -t $SESSION"; exit 1
fi
tmux new-session -d -s "$SESSION" -n control
for i in "${!ROLES[@]}"; do
  r="${ROLES[$i]}"; d="$BASE/$r"
  mkdir -p "$d"; cp -f "$REPO_ROLES/$r.md" "$d/CLAUDE.md"
  tmux new-window -t "$SESSION:$((i+1))" -n "$r"
  m="${MODELS[$r]:-}"; opt=""; [ -n "$m" ] && opt="--model $m"
  tmux send-keys -t "$SESSION:$((i+1))" "cd $d && claude $opt" Enter
done
echo "OK: tmux attach -t $SESSION (окна: control + ${ROLES[*]})"
