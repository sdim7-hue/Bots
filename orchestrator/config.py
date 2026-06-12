"""Конфигурация оркестратора.

Бэкенд очереди задач (переменная окружения BOTS_BACKEND):
  - "github" (по умолчанию) — issues/labels на GitHub;
  - "forgejo" — issues/labels на self-hosted Forgejo (Gitea API).

Токен НИКОГДА не печатается и не логируется (см. CLAUDE.md, playbook).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Бэкенд очереди.
BACKEND = os.environ.get("BOTS_BACKEND", "github").strip().lower()

# Репозиторий-цель. Дефолт владельца зависит от бэкенда.
_DEFAULT_OWNER = "dimir" if BACKEND == "forgejo" else "sdim7-hue"
OWNER = os.environ.get("BOTS_OWNER", _DEFAULT_OWNER)
REPO = os.environ.get("BOTS_REPO", "Bots")

# Базовый URL API (без хвостового слэша).
_DEFAULT_API = (
    "http://127.0.0.1:3000/api/v1" if BACKEND == "forgejo" else "https://api.github.com"
)
API_BASE = os.environ.get("BOTS_API_BASE", _DEFAULT_API).rstrip("/")

# Корневой CA (PEM) для TLS к Forgejo по https. Для http/localhost не нужен.
CAFILE = os.environ.get("BOTS_CAFILE") or None

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
    """Возвращает токен очереди или бросает RuntimeError с понятным сообщением."""
    if BACKEND == "forgejo":
        for var in ("BOTS_TOKEN", "FORGEJO_TOKEN"):
            token = os.environ.get(var)
            if token:
                return token
        raise RuntimeError(
            "Forgejo-токен не найден. Задай переменную окружения BOTS_TOKEN "
            "(или FORGEJO_TOKEN)."
        )

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


def make_client():
    """Создаёт клиент очереди по выбранному бэкенду (единый интерфейс)."""
    token = get_token()
    if BACKEND == "forgejo":
        from .forgejo_client import ForgejoClient
        return ForgejoClient(token, OWNER, REPO, API_BASE, cafile=CAFILE)
    from .github_client import GitHubClient
    return GitHubClient(token, OWNER, REPO)


def client_errors() -> tuple:
    """Кортеж исключений клиентов — для единого except в CLI."""
    from .github_client import GitHubError
    from .forgejo_client import ForgejoError
    return (GitHubError, ForgejoError)
