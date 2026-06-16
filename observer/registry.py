"""Реестр проектов под наблюдением.

Проекты грузятся из observer/projects.json. Каждая запись:
  {name, backend: github|forgejo, owner, repo, api_base?, cafile?}

Для каждого проекта строим read-only клиент очереди, переиспользуя клиентов
оркестратора (тот же интерфейс: list_issues_by_label / get_issue). Токен —
только из ENV, никогда не печатается и не хранится в git.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# projects.json лежит рядом с пакетом; путь переопределяется через ENV.
DEFAULT_PROJECTS_PATH = Path(
    os.environ.get("OBSERVER_PROJECTS", Path(__file__).parent / "projects.json")
)

_SUPPORTED_BACKENDS = ("github", "forgejo")


class RegistryError(RuntimeError):
    """Ошибка конфигурации реестра проектов."""


@dataclass(frozen=True)
class Project:
    name: str
    backend: str
    owner: str
    repo: str
    api_base: str | None = None
    cafile: str | None = None


def load_projects(path: Path | None = None) -> list[Project]:
    """Читает projects.json и возвращает список проектов (с валидацией)."""
    path = path or DEFAULT_PROJECTS_PATH
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"Файл проектов не найден: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Не удалось прочитать {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise RegistryError("projects.json должен содержать список проектов.")

    projects: list[Project] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise RegistryError("Каждый проект — это объект JSON.")
        backend = str(entry.get("backend", "")).strip().lower()
        if backend not in _SUPPORTED_BACKENDS:
            raise RegistryError(
                f"backend проекта {entry.get('name')!r} должен быть одним из "
                f"{_SUPPORTED_BACKENDS}, а не {backend!r}."
            )
        for field in ("name", "owner", "repo"):
            if not entry.get(field):
                raise RegistryError(f"У проекта не задано поле {field!r}: {entry}.")
        projects.append(
            Project(
                name=str(entry["name"]),
                backend=backend,
                owner=str(entry["owner"]),
                repo=str(entry["repo"]),
                api_base=entry.get("api_base") or None,
                cafile=entry.get("cafile") or None,
            )
        )
    if not projects:
        raise RegistryError("projects.json не содержит ни одного проекта.")
    return projects


def _token_for(backend: str) -> str:
    """Токен очереди из ENV по бэкенду (те же имена, что у оркестратора)."""
    if backend == "forgejo":
        names = ("BOTS_TOKEN", "FORGEJO_TOKEN")
    else:
        names = ("GITHUB_TOKEN", "GH_TOKEN")
    for name in names:
        token = os.environ.get(name)
        if token:
            return token
    raise RegistryError(
        f"Токен для backend={backend} не найден. Задай одну из переменных "
        f"окружения: {', '.join(names)}."
    )


def make_client(project: Project):
    """Создаёт read-only клиент очереди для проекта.

    Переиспользует клиентов оркестратора. Observer вызывает только методы
    чтения (list_issues_by_label / get_issue) — никаких мутаций.
    """
    token = _token_for(project.backend)
    if project.backend == "forgejo":
        from orchestrator.forgejo_client import ForgejoClient

        api_base = project.api_base or "http://127.0.0.1:3000/api/v1"
        return ForgejoClient(token, project.owner, project.repo, api_base,
                             cafile=project.cafile)
    from orchestrator.github_client import GitHubClient

    return GitHubClient(token, project.owner, project.repo)


def client_errors() -> tuple:
    """Кортеж исключений клиентов — для единого except в CLI/коллекторе."""
    from orchestrator.github_client import GitHubError
    from orchestrator.forgejo_client import ForgejoError

    return (GitHubError, ForgejoError)
