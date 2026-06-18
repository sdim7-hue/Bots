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
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Режим разрешений Claude Code для headless-бота (см. docstring модуля).
_PERMISSION_MODE = "bypassPermissions"


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


def _kill_tree(pid: int) -> None:
    """Best-effort kill of the bot process tree. Claude Code spawns helper processes
    that otherwise linger and eventually hang the windows-cli bridge."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def run_bot(brief: str, cwd: Path, timeout: int) -> BotResult:
    """Run Claude Code with the brief on STDIN in cwd and collect the result.

    Brief goes on stdin (a long/multiline brief as a CLI arg breaks claude.cmd
    arg-forwarding and silently drops trailing flags like --permission-mode). On
    completion or timeout the whole child process tree is killed so helper processes
    do not pile up. Success is judged by the JSON subtype, not the exit code (a long
    successful run can still exit nonzero)."""
    claude = _find_claude()
    cmd = [claude, "-p", "--permission-mode", _PERMISSION_MODE, "--output-format", "json"]

    popen_kwargs = dict(
        cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
    )
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)
    timed_out = False
    try:
        out, err = proc.communicate(input=brief, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc.pid)
        try:
            out, err = proc.communicate(timeout=30)
        except Exception:
            out, err = "", ""
    finally:
        _kill_tree(proc.pid)

    if timed_out:
        raise TimeoutError(
            f"Claude Code did not finish within {timeout}s (timeout). Partial output:\n{out or ''}"
        )

    returncode = proc.returncode
    raw = out or ""
    data = _parse_result(raw)

    is_error = data.get("is_error")
    result_text = data.get("result")
    if not result_text:
        result_text = raw
        stderr = err or ""
        if stderr.strip():
            result_text = (result_text + "\n[stderr]\n" + stderr).strip()

    subtype = data.get("subtype")
    if subtype is not None:
        ok = (subtype == "success") and (is_error is not True)
    else:
        ok = (returncode == 0) and (is_error is not True)

    return BotResult(
        exit_code=returncode, output=result_text, ok=ok, subtype=subtype,
        cost_usd=data.get("total_cost_usd"), num_turns=data.get("num_turns"), raw=raw,
    )
