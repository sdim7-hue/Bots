#!/bin/bash
# session-cleanup.sh — безопасная утилизация плацдарма при закрытии сессии Digital Company.
# Удаляет ТОЛЬКО worktree замёрженных веток БЕЗ uncommitted/unmerged. Чистит tmp/.
# НИКОГДА не трогает vault / code-repos / .git / worktree с несохранённой работой.
# Создан 2026-06-28 (closure-fix Декстера). Owner: DevOps (Линус); координирует Архитектор (R-DC-14).
# Использование: session-cleanup.sh [--dry-run]
set -uo pipefail
DC="${DC_DIR:-$HOME/digital-company}"
DRYRUN="${1:-}"
say(){ echo "[cleanup] $*"; }

[ -d "$DC" ] || { echo "[cleanup] нет каталога $DC"; exit 1; }
cd "$DC" || exit 1

echo "=== du ДО ==="
du -sh "$DC/worktrees" "$DC/tmp" 2>/dev/null || true

# 1) worktrees: только замёрженные + без несохранённого
if git -C "$DC" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$DC" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}' | while read -r WT; do
    [ "$WT" = "$DC" ] && continue
    case "$WT" in "$DC/worktrees/"*) ;; *) continue ;; esac
    BR=$(git -C "$WT" rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [ -n "$(git -C "$WT" status --porcelain 2>/dev/null)" ]; then
      say "SKIP $WT — есть uncommitted"; continue
    fi
    MERGED=""
    for BASE in master main; do
      git -C "$DC" rev-parse --verify "$BASE" >/dev/null 2>&1 || continue
      git -C "$DC" branch --merged "$BASE" 2>/dev/null | grep -qw "$BR" && MERGED=1
    done
    [ -z "$MERGED" ] && { say "SKIP $WT (ветка $BR не замёржена)"; continue; }
    if [ "$DRYRUN" = "--dry-run" ]; then
      say "DRY: удалил бы $WT (merged $BR)"
    else
      git -C "$DC" worktree remove "$WT" 2>/dev/null && say "removed $WT ($BR)" || say "FAIL remove $WT"
    fi
  done
  [ "$DRYRUN" = "--dry-run" ] || git -C "$DC" worktree prune 2>/dev/null
fi

# 2) tmp/ — очистить содержимое (каталог сохраняем)
if [ -d "$DC/tmp" ]; then
  if [ "$DRYRUN" = "--dry-run" ]; then
    say "DRY: очистил бы $DC/tmp ($(du -sh "$DC/tmp" 2>/dev/null | cut -f1))"
  else
    find "$DC/tmp" -mindepth 1 -delete 2>/dev/null && say "tmp/ очищен" || say "tmp/ — нечего чистить"
  fi
fi

echo "=== du ПОСЛЕ ==="
du -sh "$DC/worktrees" "$DC/tmp" 2>/dev/null || true
