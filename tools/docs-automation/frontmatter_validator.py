#!/usr/bin/env python3
"""frontmatter_validator.py — required-field check for MODULES/*.md frontmatter.

Every module doc must carry a YAML frontmatter block with the fields the team
relies on for the modules catalog. Required by default: type, status, updated.
(`last_audit` is recommended and surfaced as a warning when absent, because
stale_flag.py needs it — but it is not hard-required.)

No PyYAML dependency: the frontmatter is flat `key: value`, parsed line by line.

Usage:
    python3 frontmatter_validator.py [MODULES_DIR] [--require k1,k2,...]

    MODULES_DIR   directory of module .md files
                  (default: $DOCS_MODULES or the NVR Claude-Vault MODULES dir)
    --require     comma-separated override of the required field list

Exit code: 0 when every file passes, 1 when any file is missing a required
field (gate a pre-commit hook with it).
"""
import os
import sys

DEFAULT_MODULES = os.environ.get(
    "DOCS_MODULES", "/home/buka/Obsidian/Claude-Vault/NVR-2026/MODULES"
)
REQUIRED_DEFAULT = ("type", "status", "updated")
RECOMMENDED = ("last_audit",)
SKIP_FILE_SUFFIXES = (".local.md",)


def parse_frontmatter(text):
    """Return dict of top-level frontmatter keys, or None if no block present."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        # only top-level "key: value" pairs (ignore nested/list lines)
        if line[:1].isspace() or line.lstrip().startswith("-"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    # no closing fence -> treat as malformed (no frontmatter)
    return None


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    required = list(REQUIRED_DEFAULT)
    for a in argv[1:]:
        if a.startswith("--require"):
            _, _, val = a.partition("=")
            if not val and "--require" in argv:
                idx = argv.index("--require")
                if idx + 1 < len(argv):
                    val = argv[idx + 1]
            if val:
                required = [k.strip() for k in val.split(",") if k.strip()]

    modules = args[0] if args and not args[0].startswith("--") else DEFAULT_MODULES
    if not os.path.isdir(modules):
        print(f"ERROR: modules dir not found: {modules}", file=sys.stderr)
        return 2

    failures = []   # (file, [missing])
    warnings = []   # (file, [missing recommended])
    checked = 0

    for name in sorted(os.listdir(modules)):
        if not name.endswith(".md") or name.endswith(SKIP_FILE_SUFFIXES):
            continue
        path = os.path.join(modules, name)
        if not os.path.isfile(path):
            continue
        checked += 1
        text = open(path, encoding="utf-8", errors="replace").read()
        fm = parse_frontmatter(text)
        if fm is None:
            failures.append((name, ["<no frontmatter block>"]))
            continue
        missing = [k for k in required if not fm.get(k)]
        if missing:
            failures.append((name, missing))
        missing_rec = [k for k in RECOMMENDED if not fm.get(k)]
        if missing_rec:
            warnings.append((name, missing_rec))

    if warnings:
        print("WARNINGS (recommended fields missing):")
        for name, miss in warnings:
            print(f"  {name}: missing {', '.join(miss)}")
        print()

    if failures:
        print(f"FRONTMATTER VALIDATION FAILED ({len(failures)}/{checked} files):")
        for name, miss in failures:
            print(f"  {name}: missing {', '.join(miss)}")
        print(f"\nrequired fields: {', '.join(required)}")
        return 1

    print(f"OK — all {checked} module files have required fields "
          f"({', '.join(required)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
