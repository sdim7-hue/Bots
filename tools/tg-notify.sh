#!/bin/bash
# Helper для отправки уведомлений Илье в Telegram.
# Usage: tg-notify.sh "message text"
#        tg-notify.sh --level=alert "message"   # с эмодзи 🔴
#        tg-notify.sh --level=info  "message"   # с эмодзи ℹ️
#        tg-notify.sh --level=ok    "message"   # с эмодзи ✅
#        tg-notify.sh --level=warn  "message"   # с эмодзи 🟡
#
# Exit codes:
#   0 — Telegram confirmed delivery (response has "ok":true + message_id).
#   1 — config missing / bad args.
#   2 — delivery NOT confirmed after retry.
#
# Fix 2026-06-16 (PARK-TG-NOTIFY-CHUNKING/timeout half):
#   - Was: short default curl timeout, exit-28 false-fail on Telegram ack lag,
#     response body /dev/null'ed → script trusted exit code (lied).
#   - Now: 60s --max-time + 10s --connect-timeout, parse response body for
#     "ok":true + message_id, retry-once after 3s pause if first attempt
#     failed to confirm. Exit code reflects ACTUAL Telegram delivery, not curl
#     transport state.
#
# Chunking of >4096-char messages is NOT in this patch (separate
# PARK-TG-NOTIFY-CHUNKING patch); current callers don't approach the limit.

set -uo pipefail   # NOT -e — we MUST handle curl non-zero ourselves so
                   # exit-28 doesn't kill us before we inspect the response.

CONFIG="${HOME}/.config/teslatel-bot/.env"
[ -f "$CONFIG" ] || { echo "ERROR: $CONFIG not found" >&2; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG"

LEVEL="info"
if [[ "${1:-}" == --level=* ]]; then
    LEVEL="${1#--level=}"
    shift
fi

EMOJI=""
case "$LEVEL" in
    alert) EMOJI="🔴 " ;;
    info)  EMOJI="ℹ️ "  ;;
    ok)    EMOJI="✅ " ;;
    warn)  EMOJI="🟡 " ;;
esac

if [ "$#" -lt 1 ]; then
    echo "Usage: tg-notify.sh [--level=alert|info|ok|warn] 'message'" >&2
    exit 1
fi
MESSAGE="${EMOJI}$*"

# Confirmed delivery = response JSON contains "ok":true AND a message_id.
# Telegram API success body:
#   {"ok":true,"result":{"message_id":12345,"date":...,"chat":{...},"text":"..."}}
# Failure body:
#   {"ok":false,"error_code":...,"description":"..."}
delivery_confirmed() {
    local resp="$1"
    [[ "$resp" == *'"ok":true'* ]] && [[ "$resp" =~ \"message_id\":[[:space:]]*[0-9]+ ]]
}

send_once() {
    # Capture body to stdout, errors to stderr. --silent + --show-error keeps
    # output clean on success but surfaces real errors on failure.
    # --max-time 60: Telegram ack can lag 15-30s under load; 60s buffer
    # eliminates the spurious exit-28 false-fails.
    # --connect-timeout 10: fail fast if the host is unreachable, vs
    # waiting full 60s on a dead network.
    curl --silent --show-error \
        --connect-timeout 10 \
        --max-time 60 \
        "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT_ID}" \
        --data-urlencode "text=${MESSAGE}" \
        --data-urlencode "parse_mode=HTML"
}

RESP="$(send_once 2>&1)" || true
if delivery_confirmed "$RESP"; then
    exit 0
fi

# First attempt didn't confirm — could be transport timeout, transient 5xx,
# or Telegram rate-limit. Pause 3s (Telegram usually catches up by then) +
# retry once. NB: there's an inherent risk of a duplicate message if the
# first POST actually went through but the ack vanished — tolerated, because
# a stale "send failed" reading is more damaging than a rare duplicate.
sleep 3
RESP="$(send_once 2>&1)" || true
if delivery_confirmed "$RESP"; then
    exit 0
fi

echo "ERROR: tg-notify delivery NOT confirmed after 2 attempts" >&2
# Trim response to one line for legibility; never echo the bot token (it's not
# present in API responses anyway, but be safe — head -c 400 cap).
echo "  last response (trimmed): $(printf '%s' "$RESP" | tr '\n' ' ' | head -c 400)" >&2
exit 2
