#!/bin/bash
# Песочница для прогона бота: ОС-граница записи поверх gate-clone.
# Usage: sandbox-run.sh <gate-dir> <команда...>
#
# Зачем (playbook import-ai-ops B4): brief, allowlist инструментов, git-worktree и
# проверка диффа ПОСЛЕ — полезны, но границы записи не создают: `--disallowedTools`
# обходится через подключённые MCP. Единственная надёжная граница — ядро.
# Запрещена не «работа с внешним миром», а БЕСКОНТРОЛЬНАЯ ЛОКАЛЬНАЯ ЗАПИСЬ:
# читать хост, ходить в сеть, клонировать репо — можно; писать — только в гейт.
#
# Что внутри:
#   - весь хост виден READ-ONLY; на запись только гейт, /tmp (tmpfs) и состояние CLI;
#   - свои namespace: pid/uts/ipc (mount — всегда); --die-with-parent (нет сирот);
#   - cgroup-лимиты через systemd --user scope: память, CPU, число задач.
#
# Сеть НЕ отрезается — без неё бот не дойдёт до API.
# Отключение: BOTS_SANDBOX=0 (для отладки; в платном прогоне не использовать).
set -uo pipefail

GATE="${1:?gate-dir}"; shift
[ $# -gt 0 ] || { echo "sandbox-run: нет команды" >&2; exit 2; }

MEM_MAX="${BOTS_MEM_MAX:-4G}"
CPU_QUOTA="${BOTS_CPU_QUOTA:-200%}"
TASKS_MAX="${BOTS_TASKS_MAX:-512}"

if [ "${BOTS_SANDBOX:-1}" = "0" ]; then
  echo "ВНИМАНИЕ: песочница отключена (BOTS_SANDBOX=0)" >&2
  exec "$@"
fi

command -v bwrap >/dev/null 2>&1 || {
  echo "sandbox-run: нет bwrap — граница записи не обеспечена, прогон отменён" >&2
  echo "  установить: sudo apt install bubblewrap" >&2
  exit 1
}

GATE_ABS=$(readlink -f "$GATE") || { echo "sandbox-run: не разрешился путь гейта" >&2; exit 1; }
[ -d "$GATE_ABS" ] || { echo "sandbox-run: гейт не каталог: $GATE_ABS" >&2; exit 1; }

# Пишем только туда, где это необходимо. Состояние CLI — иначе claude не стартует.
BINDS=(--bind "$GATE_ABS" "$GATE_ABS")
[ -d "$HOME/.claude" ] && BINDS+=(--bind "$HOME/.claude" "$HOME/.claude")
[ -f "$HOME/.claude.json" ] && BINDS+=(--bind "$HOME/.claude.json" "$HOME/.claude.json")
[ -d "$HOME/.cache/claude-cli-nodejs" ] && \
  BINDS+=(--bind "$HOME/.cache/claude-cli-nodejs" "$HOME/.cache/claude-cli-nodejs")

BWRAP=(bwrap
  --ro-bind / /
  --dev-bind /dev /dev
  --proc /proc
  --tmpfs /tmp
  "${BINDS[@]}"
  --chdir "$GATE_ABS"
  --unshare-pid --unshare-uts --unshare-ipc
  --die-with-parent
  --new-session
)

# cgroup-лимиты — гигиена ресурсов, не граница безопасности. Если шина systemd
# --user недоступна (неинтерактивный контекст), продолжаем без лимитов: ронять
# прогон из-за отсутствия лимита неправильно, граница-то в bwrap.
: "${XDG_RUNTIME_DIR:=/run/user/$(id -u)}"
export XDG_RUNTIME_DIR
: "${DBUS_SESSION_BUS_ADDRESS:=unix:path=$XDG_RUNTIME_DIR/bus}"
export DBUS_SESSION_BUS_ADDRESS

if systemctl --user is-system-running >/dev/null 2>&1; then
  exec systemd-run --user --scope --quiet --collect \
    -p "MemoryMax=$MEM_MAX" -p "CPUQuota=$CPU_QUOTA" -p "TasksMax=$TASKS_MAX" \
    -- "${BWRAP[@]}" "$@"
fi

echo "sandbox-run: шина systemd --user недоступна — без cgroup-лимитов (bwrap активен)" >&2
exec "${BWRAP[@]}" "$@"
