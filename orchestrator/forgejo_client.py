"""Минимальный клиент Forgejo/Gitea REST API на стандартной библиотеке (urllib).

Тот же интерфейс, что у GitHubClient (см. github_client.py): список issues по
метке, get_issue, set_status (метки), комментарии — этого достаточно для очереди
и автоцикла. Никаких сторонних зависимостей (ADR-004).

Отличия Gitea/Forgejo от GitHub:
  - метки на issue задаются СПИСКОМ ID, а не имён → резолвим имена в ID и ставим
    через PUT /issues/{n}/labels (заменяет весь набор);
  - PR отсекаются параметром type=issues;
  - заголовок авторизации: "token <...>".
TLS: для https с внутренним CA (Caddy) передать cafile (PEM) — будет ssl-контекст.
Токен НИКОГДА не печатается и не логируется.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

_STATUS_PREFIX = "status:"
_DEFAULT_LABEL_COLOR = "#ededed"


class ForgejoError(RuntimeError):
    """Ошибка вызова Forgejo API."""


class ForgejoClient:
    def __init__(self, token: str, owner: str, repo: str, api_base: str,
                 cafile: str | None = None) -> None:
        self._token = token
        self._owner = owner
        self._repo = repo
        self._api = api_base.rstrip("/")
        self._ctx = ssl.create_default_context(cafile=cafile) if cafile else None
        self._label_cache: dict[str, int] | None = None

    def _request(self, path: str, params: dict | None = None,
                 method: str = "GET", data: dict | None = None):
        url = self._api + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, method=method, data=body)
        req.add_header("Authorization", "token " + self._token)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "bots-orchestrator")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30, context=self._ctx) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            # Тело ошибки полезно; токен в него не попадает.
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise ForgejoError("Forgejo API %s: %s" % (exc.code, detail)) from exc
        except urllib.error.URLError as exc:
            raise ForgejoError("Сеть/TLS недоступны: %s" % (exc.reason,)) from exc

    def list_issues_by_label(self, label: str) -> list[dict]:
        """Открытые issues с указанной меткой (без PR)."""
        data = self._request(
            "/repos/%s/%s/issues" % (self._owner, self._repo),
            {"labels": label, "state": "open", "type": "issues", "limit": 50},
        )
        if not isinstance(data, list):
            raise ForgejoError("Неожиданный ответ API (ожидался список issues).")
        return data

    def get_issue(self, issue_number: int) -> dict:
        """Одна issue по номеру (нужно для актуального списка меток)."""
        data = self._request(
            "/repos/%s/%s/issues/%s" % (self._owner, self._repo, issue_number)
        )
        if not isinstance(data, dict):
            raise ForgejoError("Неожиданный ответ API (ожидался объект issue).")
        return data

    def _labels_map(self) -> dict[str, int]:
        """name -> id для меток репозитория (с кэшем)."""
        if self._label_cache is None:
            data = self._request(
                "/repos/%s/%s/labels" % (self._owner, self._repo), {"limit": 100}
            )
            if not isinstance(data, list):
                raise ForgejoError("Неожиданный ответ API (ожидался список меток).")
            self._label_cache = {lbl["name"]: lbl["id"] for lbl in data}
        return self._label_cache

    def _ensure_label(self, name: str) -> int:
        """Возвращает id метки, создавая её при отсутствии."""
        labels = self._labels_map()
        if name in labels:
            return labels[name]
        created = self._request(
            "/repos/%s/%s/labels" % (self._owner, self._repo),
            method="POST", data={"name": name, "color": _DEFAULT_LABEL_COLOR},
        )
        if not isinstance(created, dict) or "id" not in created:
            raise ForgejoError("Не удалось создать метку %s." % name)
        self._label_cache[name] = created["id"]
        return created["id"]

    def set_status(self, issue_number: int, new_status: str) -> None:
        """Снимает прежнюю метку status:* и ставит status:<new_status>.

        В Gitea метки на issue задаются списком ID (PUT .../labels заменяет весь
        набор). Прочие метки (type:* и т.п.) сохраняются.
        """
        issue = self.get_issue(issue_number)
        kept_ids = [
            lbl["id"] for lbl in issue.get("labels", [])
            if not lbl.get("name", "").startswith(_STATUS_PREFIX)
        ]
        status_id = self._ensure_label(_STATUS_PREFIX + new_status)
        self._request(
            "/repos/%s/%s/issues/%s/labels" % (self._owner, self._repo, issue_number),
            method="PUT", data={"labels": kept_ids + [status_id]},
        )

    def add_comment(self, issue_number: int, body: str) -> None:
        """Добавляет комментарий к issue."""
        self._request(
            "/repos/%s/%s/issues/%s/comments" % (self._owner, self._repo, issue_number),
            method="POST", data={"body": body},
        )
