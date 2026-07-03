#!/usr/bin/env python3
"""link_checker.py — broken wikilink finder for the Obsidian vault.

lychee is not installed on this host, so this is the built-in fallback the
brief calls for: a stdlib-only scan that extracts every `[[wikilink]]` /
`![[embed]]` and reports the ones whose target does not resolve to a file in
the vault (Obsidian's default basename resolution).

Usage:
    python3 link_checker.py [VAULT_DIR] [--scope SUBDIR] [--quiet]

    VAULT_DIR     vault root (default: $DOCS_VAULT or the NVR Claude-Vault).
                  Link targets always resolve against the WHOLE vault, so
                  cross-folder relative links are not false-flagged.
    --scope DIR   only scan files under this subtree (still resolved against
                  the full vault). Default: scan the whole vault.
    --quiet       only print broken links + summary (suppress the "OK" header)

Exit code: 0 when every link resolves, 1 when at least one is broken
(so it can gate a pre-commit hook).
"""
import os
import re
import sys

DEFAULT_VAULT = os.environ.get(
    "DOCS_VAULT", "/home/buka/Obsidian/Claude-Vault"
)

# [[target]] / [[target|alias]] / [[target#heading]] / ![[embed]]
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")

# fenced code blocks (``` or ~~~) and inline `code` spans hold example
# links like [[wikilinks]] / [[...]] that are not real targets — strip them
# before scanning so they don't show up as false "broken" links.
FENCED_RE = re.compile(r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code(text):
    text = FENCED_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text

# directories that are never link targets and should not be scanned
SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
# secrets must never be read/echoed (defense-in-depth, RAG-exclude lessons)
SKIP_FILE_SUFFIXES = (".local.md",)


def iter_markdown(scope):
    for root, dirs, files in os.walk(scope):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".md"):
                continue
            if name.endswith(SKIP_FILE_SUFFIXES):
                continue
            yield os.path.join(root, name)


def build_target_index(vault):
    """Map every resolvable name -> source path, the way Obsidian resolves:
    by basename-without-extension, by basename-with-extension, and by
    vault-relative path (with and without extension)."""
    index = set()
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, vault)
            stem, _ext = os.path.splitext(name)
            index.add(name)                        # ADMIN-PANEL.md
            index.add(stem)                        # ADMIN-PANEL
            index.add(rel)                         # NVR-2026/MODULES/ADMIN-PANEL.md
            index.add(os.path.splitext(rel)[0])    # NVR-2026/MODULES/ADMIN-PANEL
    return index


def normalize_target(raw):
    """Strip alias (`|...`) and heading/block (`#...`, `^...`) from a link body,
    returning the file portion. Returns '' for pure intra-doc links."""
    # inside a markdown table the alias pipe is escaped as `\|`
    target = raw.replace("\\|", "|").split("|", 1)[0].strip()
    # heading/block anchors point inside a doc, not at a different file
    target = re.split(r"[#^]", target, 1)[0].strip()
    return target


def resolve(target, index, vault):
    """True if a wikilink target resolves to a real file."""
    if not target:
        return True  # [[#heading]] — intra-document, always valid here
    candidates = {target, target + ".md"}
    # normalize any ./ or ../ path components
    norm = os.path.normpath(target)
    candidates.add(norm)
    candidates.add(norm + ".md")
    candidates.add(os.path.basename(target))
    candidates.add(os.path.basename(target) + ".md")
    return any(c in index for c in candidates)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    quiet = "--quiet" in argv
    vault = args[0] if args else DEFAULT_VAULT
    scope = vault
    if "--scope" in argv:
        i = argv.index("--scope")
        if i + 1 < len(argv):
            scope = argv[i + 1]

    if not os.path.isdir(vault):
        print(f"ERROR: vault dir not found: {vault}", file=sys.stderr)
        return 2
    if not os.path.isdir(scope):
        print(f"ERROR: scope dir not found: {scope}", file=sys.stderr)
        return 2

    index = build_target_index(vault)   # always full-vault resolution
    broken = []  # (source_rel, link_raw)
    total = 0

    for path in iter_markdown(scope):
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError as e:
            print(f"WARN: cannot read {path}: {e}", file=sys.stderr)
            continue
        for m in WIKILINK_RE.finditer(strip_code(text)):
            total += 1
            target = normalize_target(m.group(1))
            if not resolve(target, index, vault):
                broken.append((os.path.relpath(path, vault), m.group(1)))

    if broken:
        print(f"BROKEN WIKILINKS: {len(broken)} of {total} checked\n")
        for src, raw in broken:
            print(f"  {src}: [[{raw}]]")
        print(f"\n{len(broken)} broken / {total} total")
        return 1

    if not quiet:
        print(f"OK — all {total} wikilinks resolve ({vault})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
