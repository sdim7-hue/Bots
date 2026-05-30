"""Минимальный клиент GitHub REST API на стандартной библиотеке (urllib).

Только чтение issues по метке — этого достаточно для MVP очереди.
Никаких сторонних зависимостей (см. ADR-004).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

_API = "https://api.github.com"


class GitHubError(RuntimeError):
    """Ошибка вызова GitHub API."""


class GitHubClient:
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self._token = token
        self._owner = owner
        self._repo = repo

    def _request(self, path: str, params: dict | None = None) -> list | dict:
        url = f"{_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", "Bearer " + self._token)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "bots-orchestrator")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Тело ошибки полезно, но токен в него не попадает.
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise GitHubError(f"GitHub API {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"Сеть недоступна: {exc.reason}") from exc

    def list_issues_by_label(self, label: str) -> list[dict]:
        """Открытые issues с указанной меткой (без PR)."""
        data = self._request(
            f"/repos/{self._owner}/{self._repo}/issues",
            {"labels": label, "state": "open", "per_page": 100},
        )
        if not isinstance(data, list):
            raise GitHubError("Неожиданный ответ API (ожидался список issues).")
        # GitHub возвращает PR в выдаче issues — отфильтровываем.
        return [item for item in data if "pull_request" not in item]
