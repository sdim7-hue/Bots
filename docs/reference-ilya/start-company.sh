#!/bin/bash
# Claude Digital Company — Canonical startup (per-role model distribution)
# Validated 2026-05-30 после experimental session.
# Canonical Model Distribution: см. CLAUDE/DIGITAL-COMPANY.md в vault.
# System Rules R-DC-1..R-DC-5: те же.

SESSION="${1:-company}"
BASE_DIR="$(dirname "$(realpath "$0")")"

# Per-role mapping: <role>:<model>:<effort>
# 2026-06-03 Tester: opus-4-8 medium + Auto Mode (--permission-mode auto) для Dynamic Workflows — паритет с Architect
declare -A MODELS=(
  [architect]="claude-opus-4-8:xhigh"
  [dispatcher]="claude-opus-4-7:low"      # 2026-06-14: уход от sonnet (узкое ctx-окно, частые сжатия) → opus-4-7 ради контекста+качества (4.6 имел те же 200k ctx что sonnet — 4.7 апгрейд), low ради экономии токенов; роль не визионер
  [coder-1]="claude-opus-4-8:high"
  [coder-2]="claude-opus-4-8:high"
  [reviewer]="claude-opus-4-8:high"
  [tester]="claude-opus-4-8:medium"
  [writer]="claude-opus-4-7:low"          # 2026-06-14: уход от sonnet → opus-4-7 ради контекста+качества (4.6 имел те же 200k ctx что sonnet — 4.7 апгрейд), low ради экономии; Ада ёмко документирует, глубокий reasoning не нужен
  [devops]="claude-opus-4-7:medium"   # эксперимент 2026-06-12: opus-4-7 (4.6 давал те же 200k ctx что sonnet; 4.7 — апгрейд качества) (снять боль 100% ctx), effort=medium чтобы НЕ раздувать reasoning/токены — роль остаётся быстрым исполнителем, не визионером
  [analyst]="claude-opus-4-8:medium"      # 2026-06-14: Клейтон-визионер на opus-4-8 (Dynamic Workflows + глубина продуктовых суждений)
  [designer]="claude-opus-4-8:high"
  [coder-3]="claude-opus-4-8:high"      # 2026-06-26: третий кодер (не хватало на параллельных задачах редизайна админки)
  [security]="claude-opus-4-8:high"     # 2026-06-26: безопасник (сетевая/код/продукт). Внедряется в этой сессии через архитектора; фидбэк по роли — после сессии
)

AGENTS=(architect dispatcher coder-1 coder-2 reviewer tester writer devops analyst designer coder-3 security)

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "⚠️  Сессия '$SESSION' уже запущена."
    echo "   tmux attach -t $SESSION — подключиться"
    echo "   tmux kill-session -t $SESSION — остановить"
    exit 1
fi

echo "🏢 Запускаю Digital Company (сессия: $SESSION) — canonical per-role distribution..."
tmux new-session -d -s "$SESSION" -n "control"
tmux send-keys -t "$SESSION:control" "echo '🏢 Digital Company ready — canonical per-role models 2026-05-30'" Enter

for i in "${!AGENTS[@]}"; do
    AGENT="${AGENTS[$i]}"
    WINDOW=$((i + 1))
    
    IFS=':' read -r MODEL EFFORT <<< "${MODELS[$AGENT]}"

    # Architect + Tester + Analyst + Designer — Auto Mode для Dynamic Workflows (classifier ловит реальные
    # действия субагентов per-action). Tester добавлен 2026-06-03 (эксперимент: свой
    # workflow тестировщику, opus-4-8 medium). Остальные — bypass как раньше.
    if [ "$AGENT" = "architect" ] || [ "$AGENT" = "tester" ] || [ "$AGENT" = "analyst" ] || [ "$AGENT" = "designer" ]; then
        PERM="--permission-mode auto"
    else
        PERM="--dangerously-skip-permissions"
    fi

    tmux new-window -t "$SESSION:$WINDOW" -n "$AGENT"
    tmux send-keys -t "$SESSION:$WINDOW" "cd $BASE_DIR/$AGENT && claude --model $MODEL --effort $EFFORT $PERM" Enter
    sleep 0.5
    echo "  ✓ $AGENT (окно $WINDOW): $MODEL @ $EFFORT [$PERM]"
done

echo ""
echo "✅ 12 ботов запущены с canonical per-role distribution"
echo "   tmux attach -t $SESSION"
