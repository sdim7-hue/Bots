"""Минимальный клиент GitHub REST API на стандартной библиотеке (urllib).

Чтение issues по метке + переходы статусов (метки) и комментарии — этого
достаточно для очереди и автоцикла. Никаких сторонних зависимостей (см. ADR-004).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

_API = "https://api.github.com"
_STATUS_PREFIX = "status:"


class GitHubError(RuntimeError):
    """Ошибка вызова GitHub API."""


class GitHubClient:
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self._token = token
        self._owner = owner
        self._repo = repo

    def _request(
        self,
        path: str,
        params: dict | None = None,
        method: str = "GET",
        data: dict | None = None,
    ) -> list | dict:
        url = f"{_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, method=method, data=body)
        req.add_header("Authorization", "Bearer " + self._token)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "bots-orchestrator")
        if body is not None:
            req.add_header("Content-Type", "application/json")
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

    def get_issue(self, issue_number: int) -> dict:
        """Одна issue по номеру (нужно для актуального списка меток)."""
        data = self._request(
            f"/repos/{self._owner}/{self._repo}/issues/{issue_number}"
        )
        if not isinstance(data, dict):
            raise GitHubError("Неожиданный ответ API (ожидался объект issue).")
        return data

    def set_status(self, issue_number: int, new_status: str) -> None:
        """Снимает прежнюю метку status:* и ставит status:<new_status>.

        Прочие метки (type:* и т.п.) сохраняются. Реализовано через PATCH с
        полным набором меток — GitHub заменяет список целиком.
        """
        issue = self.get_issue(issue_number)
        labels = [lbl["name"] for lbl in issue.get("labels", [])]
        kept = [l for l in labels if not l.startswith(_STATUS_PREFIX)]
        kept.append(f"{_STATUS_PREFIX}{new_status}")
        self._request(
            f"/repos/{self._owner}/{self._repo}/issues/{issue_number}",
            method="PATCH",
            data={"labels": kept},
        )

    def add_comment(self, issue_number: int, body: str) -> None:
        """Добавляет комментарий к issue."""
        self._request(
            f"/repos/{self._owner}/{self._repo}/issues/{issue_number}/comments",
            method="POST",
            data={"body": body},
        )
