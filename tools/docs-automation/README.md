# docs-automation

Stdlib-only docs-hygiene tools for the Obsidian Claude-Vault. No external
dependencies (`lychee` is not installed on this host, so the link checker uses
a built-in scanner). Python 3 + bash only.

| Tool | What it does | Writes? |
|---|---|---|
| `link_checker.py` | Finds broken `[[wikilinks]]` / `![[embeds]]` across the vault | no (read-only) |
| `frontmatter_validator.py` | Checks `MODULES/*.md` carry required frontmatter (`type`, `status`, `updated`) | no (read-only) |
| `stale_flag.py` | Projects each module's `last_audit` into the `MODULES/README.md` audit column (⚠ / ✅) | **only with `--write`** |
| `check_all.sh` | Runs all three read-only (stale in dry-run) — pre-commit friendly | no |

All scripts default to the NVR vault but accept overrides via argument or the
`DOCS_VAULT` / `DOCS_MODULES` environment variables. `*.local.md` (secrets)
files are always skipped.

---

## link_checker.py

```bash
python3 link_checker.py [VAULT_DIR] [--scope SUBDIR] [--quiet]
```

- Extracts every wikilink and resolves it the way Obsidian does — by basename,
  basename-with-extension, or vault-relative path.
- **Targets always resolve against the whole vault**, so a relative link like
  `[[../reports/foo]]` from a `MODULES/` file is not false-flagged.
- `--scope DIR` narrows *which files are scanned* (e.g. only `MODULES/`) while
  keeping full-vault resolution.
- Fenced code blocks and inline `code` spans are stripped before scanning, so
  example links (`[[wikilinks]]`, `[[...]]`) inside docs are ignored.
- Exit `0` if every link resolves, `1` if any are broken.

```bash
# whole vault
python3 link_checker.py
# only MODULES files, resolved against the full vault
python3 link_checker.py /home/buka/Obsidian/Claude-Vault \
        --scope /home/buka/Obsidian/Claude-Vault/NVR-2026/MODULES
```

## frontmatter_validator.py

```bash
python3 frontmatter_validator.py [MODULES_DIR] [--require type,status,updated]
```

- Every `MODULES/*.md` must have a YAML frontmatter block containing the
  required fields (default `type`, `status`, `updated`).
- `last_audit` is **recommended** — reported as a warning (not a failure) when
  missing, because `stale_flag.py` needs it.
- `--require k1,k2,...` overrides the required set.
- Exit `0` if all pass, `1` if any file is missing a required field.

## stale_flag.py

```bash
python3 stale_flag.py [--readme PATH] [--modules DIR] \
        [--stale-days N] [--today YYYY-MM-DD] [--write]
```

Rewrites the `MODULES/README.md` "Last audit" column to be a projection of each
module's frontmatter `last_audit`:

- date shown = the module's `last_audit`, formatted `DD.MM.YYYY`
- flag = `⚠` when `today - last_audit > --stale-days` (default 30), else `✅`
- any trailing note in the cell (e.g. `stub`) is preserved
- rows whose `[[link]]` has no module file / no `last_audit` are left untouched

**Default is dry-run** — it prints the diff and exits `1` if anything is out of
date, without modifying the file. Pass `--write` to apply.

> ⚠ **P-M-B:** `modules/*.md` are a human control loop — bots do not write them.
> Run `stale_flag.py` in dry-run, hand the diff to a human, and let *them* run
> `--write`. The default enforces this.

```bash
# show what would change (safe)
python3 stale_flag.py
# pin the reference date (deterministic, for tests / CI)
python3 stale_flag.py --today 2026-05-31
# apply — human action only
python3 stale_flag.py --write
```

## check_all.sh

```bash
./check_all.sh [VAULT_DIR]
```

Runs `link_checker` (MODULES scope), `frontmatter_validator`, and `stale_flag`
(dry-run). Non-zero exit if any check fails. Drop-in for a vault pre-commit
hook:

```bash
# .git/hooks/pre-commit in the vault repo
exec /home/buka/digital-company/tools/docs-automation/check_all.sh
```
