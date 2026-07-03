#!/usr/bin/env bash
# check_all.sh — run the read-only docs checks (link + frontmatter + stale dry-run).
# Suitable for a vault pre-commit hook. Exits non-zero if ANY check fails.
# stale_flag runs in dry-run only here — it never writes (P-M-B: modules/*.md
# are a human control loop). Pass the vault root as $1 to override the default.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
VAULT="${1:-${DOCS_VAULT:-/home/buka/Obsidian/Claude-Vault}}"
MODULES="${DOCS_MODULES:-$VAULT/NVR-2026/MODULES}"

rc=0
echo "== link_checker (scope: MODULES, resolve: full vault) =="
python3 "$HERE/link_checker.py" "$VAULT" --scope "$MODULES" --quiet || rc=1
echo
echo "== frontmatter_validator =="
python3 "$HERE/frontmatter_validator.py" "$MODULES" || rc=1
echo
echo "== stale_flag (dry-run) =="
python3 "$HERE/stale_flag.py" --modules "$MODULES" || rc=1

echo
if [ "$rc" -ne 0 ]; then
  echo "docs checks: FAIL"
else
  echo "docs checks: OK"
fi
exit "$rc"
