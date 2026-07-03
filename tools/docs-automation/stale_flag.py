#!/usr/bin/env python3
"""stale_flag.py — project last_audit staleness into the MODULES/README catalog.

The README catalog table carries a "Last audit" column whose ⚠ markers are
maintained by hand today. This tool makes that column a projection of each
module's frontmatter `last_audit`:

    * date shown   = the module's own `last_audit` (DD.MM.YYYY)
    * flag         = ⚠ when (today - last_audit) > --stale-days, else ✅
    * trailing note = preserved (e.g. "stub")

DEFAULT IS DRY-RUN. It prints the diff and exits without touching the file.
Pass --write to apply. Writing modules/*.md is a human control-loop action
(P-M-B): a bot should run this in dry-run and hand the diff to a human, who
runs --write. The dry-run exits 1 when any row is out of date, so it can warn
in CI without mutating the vault.

Usage:
    python3 stale_flag.py [--readme PATH] [--modules DIR]
                          [--stale-days N] [--today YYYY-MM-DD] [--write]
"""
import datetime
import os
import re
import sys

DEFAULT_MODULES = os.environ.get(
    "DOCS_MODULES", "/home/buka/Obsidian/Claude-Vault/NVR-2026/MODULES"
)
STALE_DAYS_DEFAULT = 30

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DMY_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
FLAGS = ("⚠", "✅")


def is_audit_cell(cell):
    """An audit cell already carries a DD.MM.YYYY date or a ⚠/✅ flag. This
    distinguishes the module-catalog 'Last audit' column from other tables in
    the same README (e.g. the subsystem→modules map whose last column is a
    list of [[links]] and must NOT be touched)."""
    return bool(DMY_RE.search(cell)) or any(f in cell for f in FLAGS)


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def read_last_audit(modules_dir, link_target):
    """Return last_audit (datetime.date) for a [[link]] target, or None."""
    base = link_target.split("|", 1)[0].split("#", 1)[0].strip()
    base = os.path.basename(base)
    if not base.endswith(".md"):
        base += ".md"
    path = os.path.join(modules_dir, base)
    if not os.path.isfile(path):
        return None
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("last_audit:"):
            m = ISO_RE.search(line)
            if m:
                return datetime.date(int(m[1]), int(m[2]), int(m[3]))
        if line.strip() == "---" and not line.startswith("last_audit"):
            # cheap stop: leaving the frontmatter block (best-effort)
            pass
    return None


def build_cell(audit, today, stale_days, trailing, bold):
    age = (today - audit).days
    flag = "⚠" if age > stale_days else "✅"
    disp = audit.strftime("%d.%m.%Y")
    body = f"{disp} {flag}"
    if trailing:
        body = f"{body} {trailing}"
    return f"**{body}**" if bold else body


def extract_trailing(cell):
    """Strip date + flag from a cell, return any leftover note (e.g. 'stub')."""
    txt = cell.strip().strip("*").strip()
    txt = re.sub(r"\d{2}\.\d{2}\.\d{4}", "", txt)
    for f in FLAGS:
        txt = txt.replace(f, "")
    return txt.strip()


def process(readme_path, modules_dir, today, stale_days):
    lines = open(readme_path, encoding="utf-8", errors="replace").read().splitlines()
    changes = []  # (lineno, old, new)
    out = []
    for n, line in enumerate(lines, 1):
        m = WIKILINK_RE.search(line)
        if not (m and line.lstrip().startswith("|") and line.count("|") >= 3):
            out.append(line)
            continue
        audit = read_last_audit(modules_dir, m.group(1))
        if audit is None:
            out.append(line)  # external link / no last_audit — leave as-is
            continue
        cells = line.split("|")
        # find the audit column: the last cell carrying a date or flag. Rows
        # without one (e.g. subsystem-map rows ending in a [[link]] list) are
        # not catalog rows — leave them untouched.
        idx = -1
        for i in range(len(cells) - 1, -1, -1):
            if is_audit_cell(cells[i]):
                idx = i
                break
        if idx < 0:
            out.append(line)
            continue
        original = cells[idx]
        bold = "**" in original
        trailing = extract_trailing(original)
        lead = " " if original.startswith(" ") else ""
        tail = " " if original.endswith(" ") else ""
        new_cell = lead + build_cell(audit, today, stale_days, trailing, bold) + tail
        if new_cell != original:
            cells[idx] = new_cell
            new_line = "|".join(cells)
            changes.append((n, line, new_line))
            out.append(new_line)
        else:
            out.append(line)
    return out, changes


def main(argv):
    modules_dir = opt(argv, "--modules", DEFAULT_MODULES)
    readme = opt(argv, "--readme", os.path.join(modules_dir, "README.md"))
    stale_days = int(opt(argv, "--stale-days", STALE_DAYS_DEFAULT))
    today_s = opt(argv, "--today")
    write = "--write" in argv

    if today_s:
        y, mth, d = (int(x) for x in today_s.split("-"))
        today = datetime.date(y, mth, d)
    else:
        today = datetime.date.today()

    if not os.path.isfile(readme):
        print(f"ERROR: README not found: {readme}", file=sys.stderr)
        return 2

    out, changes = process(readme, modules_dir, today, stale_days)

    if not changes:
        print(f"OK — README audit flags already current "
              f"(today={today}, stale>{stale_days}d)")
        return 0

    print(f"{'APPLIED' if write else 'DRY-RUN'} — {len(changes)} row(s) "
          f"out of date (today={today}, stale>{stale_days}d):\n")
    for n, old, new in changes:
        print(f"  L{n}:")
        print(f"    - {old.strip()}")
        print(f"    + {new.strip()}")

    if write:
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        print(f"\nWrote {readme}")
        return 0

    print("\n(dry-run — pass --write to apply. Writing modules/*.md is a "
          "human action, P-M-B.)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
