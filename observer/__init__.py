"""Observer & Notifier — read-only observability over the Bots task board.

Stage 1 (ARCH-OBSERVABILITY): collect issue/task status from one or more
projects (GitHub/Forgejo), persist snapshots locally, detect attention-worthy
events (review / failed / needs:human) and notify the human via Telegram,
email or console. Serves a localhost dashboard.

Strictly read-only: this package NEVER mutates the board (no set_status,
no add_comment, no merge) and NEVER launches a bot. It only reads issues
through the orchestrator clients' read interface (list_issues_by_label).
"""

__version__ = "0.1.0"
