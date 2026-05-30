"""Локальный адаптер запуска бота через subprocess (ADR-002).

Запускает Claude Code (`claude -p <brief>`) в каталоге репозитория, дожидается
завершения и возвращает результат. ОС-зависимость (поиск `claude`/`claude.cmd`)
локализована здесь; ядро остаётся OS-агностичным.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BotResult:
    exit_code: int
    output: str  # объединённые stdout+stderr
    ok: bool


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

    # Фолбэк для Windows: глобальные npm-бины в %APPDATA%\npm.
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            for name in ("claude.cmd", "claude.exe"):
                candidate = Path(appdata) / "npm" / name
                if candidate.is_file():
                    return str(candidate)

    # Последний фолбэк — имя как есть; ошибку поднимет subprocess.
    return candidates[0]


def run_bot(brief: str, cwd: Path, timeout: int) -> BotResult:
    """Запускает Claude Code с брифом в каталоге `cwd` и снимает результат.

    stdin перенаправлен из пустого (DEVNULL), чтобы не было предупреждения про
    stdin. stdout+stderr захватываются (UTF-8). По таймауту — понятная ошибка.
    """
    claude = _find_claude()
    cmd = [claude, "-p", brief]

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
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

    return BotResult(
        exit_code=completed.returncode,
        output=completed.stdout or "",
        ok=completed.returncode == 0,
    )
