#!/bin/bash
# Pre-flight перед ЛЮБЫМ платным прогоном бота (playbook: L68 + import-ai-ops B6/A4).
# Usage: preflight.sh <repo> <role>
# Правило: любой FAIL останавливает прогон ДО создания процессов — частичного
# запуска не бывает. Повторный вызов идемпотентен (ничего не меняет, кроме fetch).
#
# Проверяет по порядку (дешёвое раньше платного):
#   1 роль существует        5 доска Forgejo отвечает
#   2 окружение ботов        6 нет чужого живого прогона на этом гейте
#   3 канонический клон      7 хватает места на диске
#   4 граница гейта          8 CLI Claude реально авторизован (последним)
set -uo pipefail
REPO="${1:?repo}"; ROLE="${2:?role}"
BOTS_DIR="${BOTS_HOME:-$HOME/work/Bots}"
SRC="$HOME/work/$REPO"
GATE="$HOME/work/gates/$REPO"
MIN_FREE_MB="${BOTS_MIN_FREE_MB:-1024}"
PING_TIMEOUT="${BOTS_PING_TIMEOUT:-90}"

fails=0; warns=0
ok()   { printf '  OK    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*"; warns=$((warns+1)); }
fail() { printf '  FAIL  %s\n' "$*"; fails=$((fails+1)); }

echo "pre-flight: repo=$REPO role=$ROLE node=$(hostname)"

# 1. роль
if [ -f "$BOTS_DIR/roles/$ROLE.md" ]; then ok "роль $ROLE найдена"
else fail "нет роли $ROLE в $BOTS_DIR/roles/"; fi

# 2. окружение
if [ -f "$HOME/.bots/env" ]; then
  ok "~/.bots/env есть"
  perm=$(stat -c %a "$HOME/.bots/env")
  [ "$perm" = "600" ] || warn "~/.bots/env права $perm (ожидалось 600)"
  # shellcheck disable=SC1091
  . "$HOME/.bots/env"
  [ -n "${BOTS_TOKEN:-${FORGEJO_TOKEN:-}}" ] || fail "в ~/.bots/env нет BOTS_TOKEN/FORGEJO_TOKEN"
else fail "нет ~/.bots/env"; fi

# 3. канонический клон: существует, состояние зафиксировано, base = точный SHA
if [ -d "$SRC/.git" ]; then
  dirty=$(git -C "$SRC" status --porcelain 2>/dev/null | wc -l)
  [ "$dirty" -eq 0 ] || warn "в $SRC $dirty неучтённых изменений (сохраняются, не трогаем)"
  if git -C "$SRC" remote get-url origin >/dev/null 2>&1; then
    git -C "$SRC" fetch -q origin 2>/dev/null || warn "fetch origin не прошёл (offline?)"
    behind=$(git -C "$SRC" rev-list --count HEAD..@{u} 2>/dev/null || echo 0)
    [ "${behind:-0}" -eq 0 ] || warn "$SRC отстаёт от origin на $behind коммит(ов)"
  fi
  BASE_SHA=$(git -C "$SRC" rev-parse HEAD)
  [ ${#BASE_SHA} -eq 40 ] && ok "base $BASE_SHA" || fail "не разрешился точный SHA"
else fail "нет локального клона $SRC"; fi

# 4. граница гейта: бот не должен иметь возможности запушить
if [ -d "$GATE/.git" ]; then
  if git -C "$GATE" remote | grep -q .; then
    fail "в гейте $GATE остался remote — граница записи не доказана"
  else ok "гейт без remote"; fi
  helper=$(git -C "$GATE" config --local --get credential.helper || echo "")
  [ -z "$helper" ] && ok "credential.helper пуст" || fail "в гейте credential.helper='$helper'"
else ok "гейт ещё не создан (будет создан без origin)"; fi

# 5. доска
if [ -d "$BOTS_DIR" ]; then
  if BOTS_REPO="$REPO" PYTHONPATH="$BOTS_DIR" timeout 60 python3 -m orchestrator list >/dev/null 2>&1
  then ok "доска $REPO отвечает"
  else fail "orchestrator list не прошёл (токен/сеть/CA)"; fi
fi

# 6. чужой живой прогон на этом гейте (по PID из локфайла, НЕ pgrep -f по пути — L)
LOCK="$GATE/.bot-run.lock"
if [ -f "$LOCK" ]; then
  pid=$(cat "$LOCK" 2>/dev/null || echo "")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    fail "на гейте уже идёт прогон (PID $pid) — параллельный запуск запрещён"
  else
    warn "протухший локфайл (PID ${pid:-?} мёртв) — будет перезаписан"
  fi
else ok "конфликта прогонов нет"; fi

# 7. место
free_mb=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
if [ "${free_mb:-0}" -ge "$MIN_FREE_MB" ]; then ok "свободно ${free_mb} МБ"
else fail "мало места: ${free_mb} МБ < ${MIN_FREE_MB} МБ"; fi

# 8. CLI Claude действительно авторизован (L68: orch list это НЕ доказывает)
if command -v claude >/dev/null 2>&1; then
  if timeout "$PING_TIMEOUT" claude -p "ping" >/dev/null 2>&1
  then ok "claude -p ping прошёл"
  else fail "claude -p ping не прошёл — OAuth истёк, нужен /login (или ANTHROPIC_API_KEY)"; fi
else fail "бинарь claude не найден в PATH"; fi

# 9. ОС-песочница: граница записи ДОКАЗЫВАЕТСЯ пробой, а не наличием bwrap.
#    Проверяется до запуска модели (import-ai-ops B4): запись в гейт разрешена,
#    запись наружу и через symlink-побег — запрещена.
if [ "${BOTS_SANDBOX:-1}" = "0" ]; then
  warn "песочница отключена (BOTS_SANDBOX=0) — граница только gate-clone"
elif ! command -v bwrap >/dev/null 2>&1; then
  fail "нет bwrap — ОС-граница записи отсутствует (sudo apt install bubblewrap)"
elif [ ! -x "$BOTS_DIR/scripts/sandbox-run.sh" ]; then
  fail "нет исполняемого $BOTS_DIR/scripts/sandbox-run.sh"
else
  probe_gate="${GATE:-$HOME/work/gates/$REPO}"
  mkdir -p "$probe_gate"
  # symlink-побег: ссылка изнутри гейта наружу не должна давать запись
  ln -sfn "$HOME" "$probe_gate/.pf-escape" 2>/dev/null
  probe=$("$BOTS_DIR/scripts/sandbox-run.sh" "$probe_gate" /bin/sh -c '
    touch .pf-probe 2>/dev/null && echo IN=ok || echo IN=denied
    touch "$HOME/.pf-outside" 2>/dev/null && echo OUT=ok || echo OUT=denied
    touch .pf-escape/.pf-via-link 2>/dev/null && echo LINK=ok || echo LINK=denied
  ' 2>/dev/null)
  rm -f "$probe_gate/.pf-probe" "$probe_gate/.pf-escape" "$HOME/.pf-outside" 2>/dev/null
  case "$probe" in
    *IN=ok*)   : ;;
    *) fail "песочница не даёт писать в гейт — бот не сможет работать" ;;
  esac
  case "$probe" in
    *OUT=ok*)  fail "ПРОБОЙ: из песочницы доступна запись в HOME" ;;
    *) : ;;
  esac
  case "$probe" in
    *LINK=ok*) fail "ПРОБОЙ: symlink из гейта даёт запись наружу" ;;
    *) : ;;
  esac
  case "$probe" in
    *IN=ok*OUT=denied*LINK=denied*) ok "граница записи доказана пробой (в гейт можно, наружу и через symlink нельзя)" ;;
    *) : ;;
  esac
fi

echo "pre-flight: FAIL=$fails WARN=$warns"
[ "$fails" -eq 0 ] || { echo "прогон НЕ запускается"; exit 1; }
exit 0
