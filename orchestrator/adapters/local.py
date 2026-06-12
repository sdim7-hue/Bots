"""Локальный адаптер запуска бота через subprocess (ADR-002).

Запускает Claude Code (`claude -p <brief>`) в каталоге репозитория, дожидается
завершения и возвращает результат. ОС-зависимость (поиск `claude`/`claude.cmd`)
локализована здесь; ядро остаётся OS-агностичным.

Режим разрешений: acceptEdits — бот может читать и создавать/править файлы,
но shell (Bash) и прочие side-effect инструменты остаются под запретом
(headless без TTY их не подтвердит). Осознанный least-privilege старт;
расширение прав (scoped Bash и т.п.) — отдельным решением (см. L52).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Режим разрешений Claude Code для headless-бота (см. docstring модуля).
_PERMISSION_MODE = "acceptEdits"


@dataclass
class BotResult:
    exit_code: int
    output: str  # финальный текст бота (из JSON result) либо сырой вывод при сбое парсинга
    ok: bool  # True только если exit_code==0 И не is_error
    subtype: str | None = None  # "success" / "error_max_turns" / "error_during_execution" / ...
    cost_usd: float | None = None
    num_turns: int | None = None
    raw: str = ""  # сырой stdout (для отладки)


def _find_claude() -> str:
    """Кроссплатформенный поиск исполняемого файла Claude Code.

    На Windows ищем `claude.cmd`/`claude` (в т.ч. в %APPDATA%\\npm),
    на *nix — `claude` из PATH. Фолбэк — имя как есть, пусть subprocess решает.
    """
    if os.name == "nt":
        candidates = ("claude.cmd", "claude.exe", "claude")
    else:
        candidates = ("claude",)

    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            for name in ("claude.cmd", "claude.exe"):
                candidate = Path(appdata) / "npm" / name
                if candidate.is_file():
                    return str(candidate)

    return candidates[0]


def _parse_result(raw: str) -> dict:
    """Разбирает JSON-вывод `claude -p --output-format json`.

    Возвращает dict результата либо пустой dict, если разобрать не удалось.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def run_bot(brief: str, cwd: Path, timeout: int) -> BotResult:
    """Запускает Claude Code с брифом в каталоге `cwd` и снимает результат.

    Бот стартует в режиме разрешений acceptEdits (правка файлов разрешена,
    shell — нет) и с `--output-format json`, чтобы судить об успехе по
    структурному полю is_error, а не только по коду возврата (см. L52).
    stdin — из пустого (DEVNULL). По таймауту — понятная ошибка.
    """
    claude = _find_claude()
    cmd = [
        claude,
        "-p", brief,
        "--permission-mode", _PERMISSION_MODE,
        "--output-format", "json",
    ]

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.output or ""
        raise TimeoutError(
            f"Claude Code не завершился за {timeout} с (timeout). "
            f"Частичный вывод:\n{partial}"
        ) from exc

    raw = completed.stdout or ""
    data = _parse_result(raw)

    is_error = data.get("is_error")
    result_text = data.get("result")
    if not result_text:
        # парс не удался или поля нет — показываем сырой вывод (+ stderr, если был)
        result_text = raw
        stderr = completed.stderr or ""
        if stderr.strip():
            result_text = (result_text + "\n[stderr]\n" + stderr).strip()

    ok = (completed.returncode == 0) and (is_error is not True)

    return BotResult(
        exit_code=completed.returncode,
        output=result_text,
        ok=ok,
        subtype=data.get("subtype"),
        cost_usd=data.get("total_cost_usd"),
        num_turns=data.get("num_turns"),
        raw=raw,
    )
