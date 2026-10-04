"""Локальный адаптер запуска бота через subprocess (ADR-002).

Запускает Claude Code (`claude -p <brief>`) в каталоге репозитория, дожидается
завершения и возвращает результат. ОС-зависимость (поиск `claude`/`claude.cmd`)
локализована здесь; ядро остаётся OS-агностичным.

Режим разрешений: bypassPermissions. Это НЕ ослабление защиты, а следствие
того, где стоит граница: флаги разрешений Claude Code обходятся через
подключённые MCP, поэтому полагаться на них нельзя (playbook L53-доп10).
Граница — механическая и двухслойная:
  1) gate-clone без remote и без credential.helper (запушить нельзя);
  2) ОС-песочница scripts/sandbox-run.sh — хост read-only, запись только в
     гейт, cgroup-лимиты (playbook import-ai-ops B4).
Запрещена не работа с внешним миром, а бесконтрольная локальная запись.
Отключение песочницы: BOTS_SANDBOX=0 (только отладка).
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

# Обёртка ОС-песочницы: <repo>/scripts/sandbox-run.sh
_SANDBOX_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sandbox-run.sh"


@dataclass
class BotResult:
    exit_code: int
    output: str  # финальный текст бота (из JSON result) либо сырой вывод при сбое парсинга
    ok: bool  # True только если exit_code==0 И не is_error
    subtype: str | None = None  # "success" / "error_max_turns" / "error_during_execution" / ...
    cost_usd: float | None = None
    num_turns: int | None = None
    raw: str = ""  # сырой stdout (для отладки)
    model_requested: str | None = None  # модель из roles/models.json (или BOTS_MODEL)
    models_used: list | None = None  # фактические модели из modelUsage (без служебной haiku)


def _find_claude() -> str:
    """Кроссплатформенный поиск исполняемого файла Claude Code.

    На Windows ищем `claude.cmd`/`claude` (в т.ч. в %APPDATA%\\npm),
    на *nix — `claude` из PATH. Фолбэк — имя как есть, пусть subprocess решает.
    """
    override = os.environ.get("BOTS_CLAUDE_BIN", "").strip()
    if override:
        return override
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


def _sandbox_prefix(cwd: Path) -> list[str]:
    """Префикс команды для запуска бота в ОС-песочнице.

    Пустой список = запуск без песочницы. Так и должно быть на Windows
    (bwrap там нет; офисный узел границу держит только gate-clone) и при
    явном BOTS_SANDBOX=0. В остальных случаях отсутствие песочницы —
    не молчаливый фолбэк: печатаем предупреждение, чтобы это было видно.
    """
    if os.environ.get("BOTS_SANDBOX") == "0":
        return []
    if os.name == "nt":
        return []
    if not _SANDBOX_SCRIPT.is_file():
        print(f"Предупреждение: нет {_SANDBOX_SCRIPT} — бот пойдёт БЕЗ ОС-песочницы")
        return []
    if shutil.which("bwrap") is None:
        print("Предупреждение: нет bwrap — бот пойдёт БЕЗ ОС-песочницы "
              "(поставить: sudo apt install bubblewrap)")
        return []
    return [str(_SANDBOX_SCRIPT), str(cwd)]


_MODELS_FILE = Path(__file__).resolve().parents[2] / "roles" / "models.json"


def model_for_role(role: str | None) -> str | None:
    """Модель для роли: env BOTS_MODEL > roles/models.json[role] > _default.
    Таблица утверждена владельцем 03.10.2026 (AI-OPS MODEL-MATRIX). None = не передавать --model."""
    forced = os.environ.get("BOTS_MODEL", "").strip()
    if forced:
        return forced
    try:
        table = json.loads(_MODELS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    return table.get(role or "") or table.get("_default")


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
    cmd = _sandbox_prefix(cwd) + [
        claude, "-p", "--permission-mode", _PERMISSION_MODE, "--output-format", "json",
    ]
    model = model_for_role(os.environ.get("BOTS_ROLE"))
    if model:
        cmd += ["--model", model]
    print(f"модель: {model or 'по умолчанию CLI'} (роль {os.environ.get('BOTS_ROLE') or '?'})")

    popen_kwargs = dict(
        cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
    )
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    # Фоновые задачи в режиме -p запрещены (04.10.2026): новые модели/CLI уводят долгие команды (test:ui ~4 мин)
    # в фон и завершают ход «в ожидании уведомления» — в headless его нет, прогон обрывался без вердикта
    # (T2 #65/#66). Длинные команды — в переднем плане с увеличенными таймаутами Bash. Переопределяемо через env.
    child_env = dict(popen_kwargs.get("env") or os.environ)
    child_env.setdefault("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS", "1")
    child_env.setdefault("BASH_DEFAULT_TIMEOUT_MS", "900000")   # 15 мин
    child_env.setdefault("BASH_MAX_TIMEOUT_MS", "2400000")      # 40 мин
    popen_kwargs["env"] = child_env
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

    # Доказательство модели (AI-OPS: профиль/авторизация НЕ доказывают живую модель): служебная haiku
    # игнорируется; если запрошенной модели нет среди работавших — результат НЕ ok (fail-closed).
    used = [k for k in (data.get("modelUsage") or {}) if "haiku" not in k]
    if model and used and model not in used:
        ok = False
        subtype = "model_mismatch"
        result_text = (f"МОДЕЛЬ НЕ СОВПАЛА: запрошена {model}, работали {used}.\n" + (result_text or ""))
    print(f"модель фактически: {used or 'неизвестно (нет modelUsage)'}")

    return BotResult(
        exit_code=returncode, output=result_text, ok=ok, subtype=subtype,
        cost_usd=data.get("total_cost_usd"), num_turns=data.get("num_turns"), raw=raw,
        model_requested=model, models_used=used,
    )
