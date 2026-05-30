"""Конфигурация оркестратора.

Источник токена (по приоритету):
  1. Переменная окружения GITHUB_TOKEN или GH_TOKEN (чистый OS-агностичный путь).
  2. Конфиг Claude Desktop (claude_desktop_config.json) — best-effort по платформам.

Токен НИКОГДА не печатается и не логируется (см. CLAUDE.md, L11 playbook).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Репозиторий-цель. Переопределяется через env, дефолт — наш проект.
OWNER = os.environ.get("BOTS_OWNER", "sdim7-hue")
REPO = os.environ.get("BOTS_REPO", "Bots")

# Локальное состояние (SQLite). В .gitignore (*.db).
STATE_DB = Path(os.environ.get("BOTS_STATE_DB", Path.home() / ".bots" / "state.db"))

_TOKEN_PREFIXES = ("ghp_", "github_pat_")


def _claude_config_paths() -> list[Path]:
    """Возможные пути к claude_desktop_config.json по платформам."""
    home = Path.home()
    paths: list[Path] = []
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
    elif sys.platform == "darwin":
        paths.append(home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    else:  # Linux и прочее
        paths.append(home / ".config" / "Claude" / "claude_desktop_config.json")
    return paths


def _find_token_in_obj(obj) -> str | None:
    """Рекурсивно ищет строку, похожую на GitHub-токен."""
    if isinstance(obj, dict):
        for value in obj.values():
            found = _find_token_in_obj(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_token_in_obj(item)
            if found:
                return found
    elif isinstance(obj, str) and obj.startswith(_TOKEN_PREFIXES):
        return obj
    return None


def get_token() -> str:
    """Возвращает GitHub-токен или бросает RuntimeError с понятным сообщением."""
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(var)
        if token:
            return token

    for cfg_path in _claude_config_paths():
        if not cfg_path.is_file():
            continue
        try:
            with cfg_path.open(encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        token = _find_token_in_obj(data)
        if token:
            return token

    raise RuntimeError(
        "GitHub-токен не найден. Задай переменную окружения GITHUB_TOKEN "
        "или убедись, что github-MCP настроен в claude_desktop_config.json."
    )
