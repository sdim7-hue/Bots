#!/usr/bin/env bash
# company-monitor.sh — cron-пульс живости команды Digital Company
# Каждые 15 мин обходит 10 окон tmux `company`, классифицирует роли и при залипании
# СИГНАЛИТ Маргарет (окно 2). НЕ предпринимает авто-действий (не жмёт Enter сам).
# Контекст-watchdog как отдельная фича пока не реализован, НО 100% context ловится как STALLED.
# Создан 2026-06-14. Детект откалиброван на реальных pane (статусбар ⏵⏵ = режим ожидания).

set -uo pipefail
SESSION="company"
DISPATCHER_WINDOW=2
LOG_DIR="/home/buka/digital-company/logs"; LOG="$LOG_DIR/company-monitor.log"
STATE_DIR="/home/buka/digital-company/tmp/monitor-state"
mkdir -p "$LOG_DIR" "$STATE_DIR"
ts() { date '+%Y-%m-%d %H:%M:%S'; }

declare -A NAME=( [1]=Декстер [2]=Маргарет [3]=Деннис [4]=Кен [5]=Кнут [6]=Барбара [7]=Ада [8]=Линус [9]=Клейтон [10]=Норман )

tmux has-session -t "$SESSION" 2>/dev/null || { echo "[$(ts)] session '$SESSION' не поднята — выход" >> "$LOG"; exit 0; }

STALLED_REPORT=""

for W in 1 2 3 4 5 6 7 8 9 10; do
  PANE=$(tmux capture-pane -t "$SESSION:$W" -p -S -6 2>/dev/null)
  [ -z "$PANE" ] && continue
  # последние 2 непустые строки — там либо статусбар ⏵⏵ (ожидание), либо активный спиннер
  LAST2=$(printf '%s' "$PANE" | grep -v '^[[:space:]]*$' | tail -2)

  WORKING=0
  printf '%s' "$LAST2" | grep -qE 'esc to interrupt' && WORKING=1          # выполняется tool
  printf '%s' "$LAST2" | grep -qE '✻ .+ for [0-9]' && WORKING=1            # активный спиннер «думает»
  WAITING=0
  printf '%s' "$LAST2" | grep -qE '⏵⏵ ' && WAITING=1                        # статусбар = режим ожидания
  CTX_FULL=0
  printf '%s' "$PANE" | grep -qE '100% context used' && CTX_FULL=1
  MODEL_ERR=0
  printf '%s' "$PANE" | grep -qiE 'currently unavailable|Please use Opus 4\.8|rate limit|Error: ' && MODEL_ERR=1

  # детект «застрял»: хвост не меняется между прогонами (15 мин)
  STATE_FILE="$STATE_DIR/win-$W.last"
  CUR_HASH=$(printf '%s' "$PANE" | md5sum | cut -d' ' -f1)
  PREV_HASH=""; [ -f "$STATE_FILE" ] && PREV_HASH=$(cat "$STATE_FILE")
  printf '%s' "$CUR_HASH" > "$STATE_FILE"

  STATUS="ok"; REASON=""
  if [ "$CTX_FULL" -eq 1 ]; then
    STATUS="STALLED"; REASON="100% контекста — нужен /clear или handover (контекст потерян при авто-компакте)"
  elif [ "$MODEL_ERR" -eq 1 ] && [ "$WORKING" -eq 0 ]; then
    STATUS="STALLED"; REASON="ошибка/недоступность модели (см. pane)"
  elif [ "$WORKING" -eq 1 ]; then
    STATUS="working"
  elif [ "$WAITING" -eq 1 ]; then
    STATUS="idle"   # норма: ждёт задачу
  else
    # не работает, не статусбар ожидания — подозрительно. Если ещё и не менялся 15 мин — залип.
    if [ -n "$PREV_HASH" ] && [ "$CUR_HASH" = "$PREV_HASH" ]; then
      STATUS="STALLED"; REASON="без активности 15+ мин, не в режиме ожидания (возможно ghost-input в ❯ / завис)"
    else
      STATUS="uncertain"
    fi
  fi

  echo "[$(ts)] win$W ${NAME[$W]}: $STATUS${REASON:+ — $REASON}" >> "$LOG"
  [ "$STATUS" = "STALLED" ] && STALLED_REPORT+="- окно $W (${NAME[$W]}): $REASON"$'\n'
done

if [ -n "$STALLED_REPORT" ]; then
  MSG="/tmp/company-monitor-alert.txt"
  {
    echo "[company-monitor → Маргарет, $(ts)] ⚠ Возможное залипание:"
    echo ""
    printf '%s' "$STALLED_REPORT"
    echo ""
    echo "Рутинный затык (ghost-Enter, idle при незакрытой задаче) — разрули сама."
    echo "Форс-мажор/отклонение (упал, 100% контекста, делает не то) — доложи Архитектору (Декстер)."
  } > "$MSG"
  tmux load-buffer "$MSG"
  tmux paste-buffer -t "$SESSION:$DISPATCHER_WINDOW" -p
  sleep 2
  tmux send-keys -t "$SESSION:$DISPATCHER_WINDOW" Enter
  echo "[$(ts)] ALERT отправлен Маргарет" >> "$LOG"
fi
exit 0
