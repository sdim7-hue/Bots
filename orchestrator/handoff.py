"""Передача работы по ХЭШУ ДИФФА, а не по имени ветки.

Зачем (playbook import-ai-ops B3). Бот работает в гейте без remote — запушить он
не может, и это правильно. Но дальше работу надо перенести в канонический клон, и
здесь легко потерять то самое свойство, ради которого гейт существует: если
вливать «ветку бота» или «последнее состояние гейта», то проверяли одно, а влили
другое — между ревью и вливанием состояние могло измениться.

Контракт:
  handoff   — снимает ОГРАНИЧЕННЫЙ патч гейта относительно точного base SHA,
              кладёт его в состояние прогона, считает sha256 и пишет событие,
              ТРЕБУЮЩЕЕ ACK. Ревьюер смотрит именно этот файл.
  integrate — переносит ИМЕННО ЭТОТ патч и только после ACK, сверив sha256.
              Ни ветка, ни «текущий гейт» источником не являются. Идемпотентно.

Патч применяется на ветку от base SHA, а НЕ на текущий main: так результат
воспроизводим и не зависит от того, что накопилось в main после начала работы.
Пуш не делается — это решение владельца.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

# Предел размера патча: передача работы, а не переезд репозитория.
MAX_PATCH_BYTES = 1024 * 1024

# Служебное, что кладёт раннер/сборка: в патч не попадает.
EXCLUDES = ("CLAUDE.local.md", "node_modules", ".bot-run.lock")


class HandoffError(RuntimeError):
    """Передача не состоялась. Частичного результата не бывает."""


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise HandoffError(f"git {' '.join(args)}: {(proc.stderr or proc.stdout).strip()[:300]}")
    return proc.stdout


def _git_bytes(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if proc.returncode != 0:
        raise HandoffError(f"git {' '.join(args)}: {proc.stderr.decode('utf-8','replace')[:300]}")
    return proc.stdout


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_patch(gate: Path, base_sha: str, out_path: Path) -> tuple[int, str, int]:
    """Патч гейта относительно base_sha. Возвращает (байт, sha256, файлов).

    Новые файлы включаются через intent-to-add: без этого созданное ботом в
    диффе не появится, и передача молча потеряет основную часть работы.
    """
    if len(base_sha) != 40:
        raise HandoffError("base_sha должен быть точным 40-символьным SHA")
    if _git(gate, "cat-file", "-t", base_sha).strip() != "commit":
        raise HandoffError(f"base {base_sha[:12]} не найден в гейте")

    _git(gate, "add", "-A", "-N", ".", check=False)
    spec = ["--", "."] + [f":(exclude){e}" for e in EXCLUDES]
    patch = _git_bytes(gate, "diff", "--binary", "--no-color", base_sha, *spec)
    if not patch.strip():
        raise HandoffError("патч пустой — передавать нечего")
    if len(patch) > MAX_PATCH_BYTES:
        raise HandoffError(
            f"патч {len(patch)} байт больше предела {MAX_PATCH_BYTES}: "
            "передача работы, а не переезд репозитория")

    names = _git(gate, "diff", "--name-only", base_sha, *spec).split()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(patch)
    return len(patch), sha256_of(out_path), len(names)


def apply_patch(src: Path, base_sha: str, patch: Path, branch: str,
                message: str) -> str:
    """Применяет патч на новую ветку от base_sha. Возвращает SHA коммита.

    Идемпотентно: если ветка уже есть, её HEAD возвращается как есть, повторно
    ничего не применяется.
    """
    if _git(src, "status", "--porcelain").strip():
        raise HandoffError(f"в {src} есть неучтённые изменения — сначала разберись с ними")

    existing = subprocess.run(["git", "-C", str(src), "rev-parse", "--verify", branch],
                              capture_output=True, text=True)
    if existing.returncode == 0:
        return existing.stdout.strip()

    current = _git(src, "rev-parse", "--abbrev-ref", "HEAD").strip()
    _git(src, "checkout", "-q", "-b", branch, base_sha)
    try:
        proc = subprocess.run(["git", "-C", str(src), "apply", "--index", "--whitespace=nowarn",
                               str(patch)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise HandoffError("патч не применился на base: "
                               + (proc.stderr or proc.stdout).strip()[:300])
        _git(src, "commit", "-q", "-m", message)
        return _git(src, "rev-parse", "HEAD").strip()
    except HandoffError:
        _git(src, "checkout", "-q", "--force", current, check=False)
        _git(src, "branch", "-D", branch, check=False)
        raise
    finally:
        _git(src, "checkout", "-q", current, check=False)
