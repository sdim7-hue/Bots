"""CLI оркестратора.

  python -m orchestrator list      — показать очередь задач со статусом queued.
  python -m orchestrator run-bot   — вручную запустить бота с брифом (проверка адаптера).
  python -m orchestrator run-next  — взять старейшую queued, прогнать бота, двинуть статус.
  python -m orchestrator supersede  — пометить задачу перекрытой более поздним решением.
  python -m orchestrator closeout   — проверить чеклист закрытия и (по --confirm) поставить done.
  python -m orchestrator runs       — прогоны, состояние которых сохранено.
  python -m orchestrator events     — журнал событий прогона.
  python -m orchestrator ack        — подтвердить событие, ждущее ACK.

Бэкенд очереди (GitHub/Forgejo) и токен — см. config.py. Токен не печатается.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import config
from .adapters.local import run_bot
from .core import SUPERSEDED_LABEL, StateStore, Task
from .runstate import ManifestError, RunState, latest_runs, make_run_id

# Дефолтный таймаут ручного запуска бота, секунды.
_RUN_BOT_TIMEOUT = int(os.environ.get("BOTS_BOT_TIMEOUT", "2400"))

# Максимальная длина вывода бота, попадающего в комментарий issue.
_COMMENT_OUTPUT_LIMIT = 1500

# Что в гейте кладёт сам раннер/сборка — при closeout не считается «неубранным».
_GATE_EXPECTED = {"CLAUDE.local.md", "node_modules", ".bot-run.lock"}


def cmd_list() -> int:
    try:
        client = config.make_client()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    try:
        issues = client.list_issues_by_label("status:queued")
    except config.client_errors() as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    store = StateStore(config.STATE_DB)
    tasks = [Task.from_issue(issue) for issue in issues]
    for task in tasks:
        store.upsert(task)
    store.close()

    header = f"Очередь queued ({config.OWNER}/{config.REPO}): {len(tasks)} задач"
    print(header)
    print("-" * len(header))
    for task in sorted(tasks, key=lambda t: t.number):
        type_part = f" [{task.type}]" if task.type else ""
        mark = "  (superseded — не берётся)" if task.superseded else ""
        print(f"  #{task.number}{type_part} {task.title}{mark}")
    return 0


def cmd_run_bot(message: str | None, file: str | None, timeout: int) -> int:
    if file:
        try:
            brief = Path(file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Ошибка: не удалось прочитать файл брифа: {exc}", file=sys.stderr)
            return 2
    elif message is not None:
        brief = message
    else:
        print("Ошибка: укажи --message или --file", file=sys.stderr)
        return 2

    checkout = Path(config.CHECKOUT) if config.CHECKOUT else Path.cwd()
    # Ручной прогон — тоже прогон: манифест и журнал ведутся так же.
    run = _open_run(os.environ.get("BOTS_ROLE", "manual"), checkout)
    if run is not None:
        run.record("run-started", sender="operator",
                   summary="ручной запуск (run-bot)", dedupe_key="start")
        print(f"Состояние прогона: {run.dir}")

    try:
        result = run_bot(brief, cwd=checkout, timeout=timeout)
    except TimeoutError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        if run is not None:
            run.record("bot-result", sender="bot", severity="warning",
                       summary="таймаут при ручном запуске", dedupe_key="timeout")
            run.close()
        return 1

    if run is not None:
        log_ref = _save_bot_log(run, result)
        run.record("bot-result", sender="bot",
                   severity="info" if result.ok else "warning",
                   summary=(f"ok={result.ok} subtype={result.subtype} "
                            f"cost={result.cost_usd} turns={result.num_turns}"),
                   payload_ref=log_ref, dedupe_key="result")
        run.record("run-finished", sender="orchestrator",
                   summary=f"ручной прогон завершён, ok={result.ok}",
                   dedupe_key="finish")
        run.close()

    print(result.output, end="" if result.output.endswith("\n") else "\n")
    print(f"exit_code={result.exit_code} ok={result.ok} subtype={result.subtype}")
    return 0 if result.ok else 1


def _bot_comment(new_status: str, result) -> str:
    """Формирует комментарий с итогом бота для ревью (см. L52)."""
    out = (result.output or "").strip()
    if len(out) > _COMMENT_OUTPUT_LIMIT:
        out = out[:_COMMENT_OUTPUT_LIMIT] + "\n…(вывод обрезан)"
    meta = f"exit_code={result.exit_code}, ok={result.ok}"
    if result.subtype:
        meta += f", subtype={result.subtype}"
    if result.cost_usd is not None:
        meta += f", cost=${result.cost_usd:.4f}"
    if result.num_turns is not None:
        meta += f", turns={result.num_turns}"
    return (
        f"Автоцикл оркестратора → status:{new_status} ({meta}).\n\n"
        f"Вывод бота:\n\n{out or '(пусто)'}"
    )


def _finalize(client, store, task, new_status, result, note) -> None:
    """Фиксирует итог: меняет статус, обновляет SQLite, пишет комментарий.

    Сбои API на этом этапе не валят процесс — бот уже отработал; ошибки лишь
    предупреждаем, итог в любом случае пишем в локальное состояние.
    """
    try:
        client.set_status(task.number, new_status)
    except config.client_errors() as exc:
        print(f"Предупреждение: не удалось сменить статус на {new_status}: {exc}",
              file=sys.stderr)
    else:
        task.status = new_status
    store.upsert(task)

    if result is not None:
        comment = _bot_comment(new_status, result)
    else:
        comment = f"Автоцикл оркестратора: {note} → status:{new_status}."
    try:
        client.add_comment(task.number, comment)
    except config.client_errors() as exc:
        print(f"Предупреждение: не удалось добавить комментарий: {exc}",
              file=sys.stderr)


def _refresh_checkout() -> None:
    """Reset the isolated bot checkout to pristine main before a run (avoid drift).
    Checkout has NO push remote; base is a read-only URL/path fetched one-shot from
    BOTS_CHECKOUT_BASE. Best-effort."""
    co = config.CHECKOUT
    base = config.CHECKOUT_BASE
    if not co or not base:
        return
    for git_args in (["fetch", base, "main"], ["reset", "--hard", "FETCH_HEAD"], ["clean", "-fd"]):
        try:
            subprocess.run(["git", "-C", co] + git_args, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        except Exception:
            pass


def cmd_run_next(timeout: int) -> int:
    try:
        client = config.make_client()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    store = StateStore(config.STATE_DB)
    try:
        try:
            issues = client.list_issues_by_label("status:queued")
        except config.client_errors() as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1

        if not issues:
            print("Очередь queued пуста — нечего запускать.")
            return 0

        # Перекрытые более поздним решением не берём: промежуточный HOLD не
        # должен снова притягиваться как активная работа при холодном старте.
        fresh = [it for it in issues if not Task.from_issue(it).superseded]
        skipped = len(issues) - len(fresh)
        if skipped:
            print(f"Пропущено superseded: {skipped}")
        if not fresh:
            print("В очереди только superseded задачи — нечего запускать.")
            return 0

        # Старейшая задача — с наименьшим номером issue.
        issue = min(fresh, key=lambda it: it["number"])
        task = Task.from_issue(issue)
        print(f"Беру #{task.number}: {task.title}")

        checkout = Path(config.CHECKOUT) if config.CHECKOUT else Path.cwd()
        run = _open_run(os.environ.get("BOTS_ROLE", "unknown"), checkout)
        if run is not None:
            # СНАЧАЛА ЗАПИСЬ, ПОТОМ СИГНАЛ: событие ложится в журнал до того,
            # как мы что-то меняем на доске.
            run.record("run-started", sender="orchestrator",
                       summary=f"#{task.number} {task.title}",
                       dedupe_key=f"start-{task.number}")
            run.record("status-changed", sender="orchestrator",
                       summary=f"#{task.number}: queued -> in-progress",
                       dedupe_key=f"inprogress-{task.number}")
            print(f"Состояние прогона: {run.dir}")

        # queued -> in-progress
        try:
            client.set_status(task.number, "in-progress")
        except config.client_errors() as exc:
            print(f"Ошибка смены статуса на in-progress: {exc}", file=sys.stderr)
            return 1
        task.status = "in-progress"
        store.upsert(task)

        _refresh_checkout()

        # Бриф — тело issue как есть (фолбэк на заголовок, если тело пустое).
        brief = issue.get("body") or task.title

        try:
            result = run_bot(brief, cwd=(Path(config.CHECKOUT) if config.CHECKOUT else Path.cwd()), timeout=timeout)
        except TimeoutError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            if run is not None:
                run.record("bot-result", sender="bot", severity="warning",
                           summary="таймаут: бот не завершился за отведённое время",
                           dedupe_key=f"timeout-{task.number}")
            _finalize(client, store, task, new_status="failed", result=None,
                      note="бот не завершился за отведённое время (timeout)")
            return 1

        new_status = "review" if result.ok else "failed"
        if run is not None:
            log_ref = _save_bot_log(run, result)
            run.record("bot-result", sender="bot",
                       severity="info" if result.ok else "warning",
                       summary=(f"ok={result.ok} subtype={result.subtype} "
                                f"cost={result.cost_usd} turns={result.num_turns}"),
                       payload_ref=log_ref,
                       dedupe_key=f"result-{task.number}")
            run.record("status-changed", sender="orchestrator",
                       summary=f"#{task.number}: in-progress -> {new_status}",
                       dedupe_key=f"{new_status}-{task.number}")
        _finalize(client, store, task, new_status=new_status, result=result, note=None)
        extra = f", subtype={result.subtype}" if result.subtype else ""
        cost = f", cost=${result.cost_usd:.4f}" if result.cost_usd is not None else ""
        print(f"#{task.number}: exit_code={result.exit_code} ok={result.ok} "
              f"→ status:{new_status}{extra}{cost}")
        if run is not None:
            run.record("run-finished", sender="orchestrator",
                       summary=f"#{task.number} -> status:{new_status}",
                       dedupe_key=f"finish-{task.number}")
            pending = run.pending_ack()
            if pending:
                print(f"⚠ Ждут подтверждения (ACK) событий: {len(pending)} — "
                      f"прогон не считается закрытым")
            run.close()
        return 0 if result.ok else 1
    finally:
        store.close()


def _open_run(role: str, checkout: Path) -> RunState | None:
    """Готовит каталог состояния прогона и манифест. None — если не удалось.

    Сбой здесь НЕ валит прогон: состояние — это наблюдаемость, а не условие
    работы. Но и молча не теряется — предупреждение печатается.
    """
    try:
        run_id = os.environ.get("BOTS_RUN_ID") or make_run_id(config.REPO, role)
        run = RunState(run_id)
        code, head = _git(checkout, "rev-parse", "HEAD")
        run.write_manifest(
            repo=config.REPO, role=role, node=os.uname().nodename if hasattr(os, "uname") else "",
            base_sha=head.strip() if code == 0 else "",
            checkout=str(checkout), backend=config.BACKEND,
        )
        return run
    except (ManifestError, OSError, Exception) as exc:  # noqa: BLE001
        print(f"Предупреждение: состояние прогона не создано: {exc}", file=sys.stderr)
        return None


def _save_bot_log(run: RunState | None, result) -> str | None:
    """Сырой вывод бота — в каталог прогона; в событие идёт только ссылка."""
    if run is None or result is None:
        return None
    try:
        path = run.dir / "bot.log"
        path.write_text(result.raw or result.output or "", encoding="utf-8")
        return str(path.name)
    except OSError:
        return None


def _git(repo: Path, *args: str) -> tuple[int, str]:
    """Запускает git в указанном репозитории. Возвращает (код, вывод)."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def cmd_supersede(number: int, by: str) -> int:
    """Помечает задачу перекрытой более поздним решением.

    Метка `superseded` живёт параллельно статусу; ссылка на то, ЧЕМ перекрыто,
    обязательна и пишется комментарием — метка значение нести не может.
    """
    by = (by or "").strip()
    if not by:
        print("Ошибка: --by обязателен (issue, коммит или вердикт)", file=sys.stderr)
        return 2
    try:
        client = config.make_client()
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    try:
        client.add_label(number, SUPERSEDED_LABEL)
        client.add_comment(number, f"superseded-by: {by}")
    except config.client_errors() as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    print(f"#{number}: помечена superseded, superseded-by: {by}")
    return 0


def cmd_closeout(number: int, artifact: str, confirm: bool) -> int:
    """Чеклист закрытия задачи. Без --confirm ничего не меняет.

    Проверяет механически то, что можно проверить, и НЕ ставит done при любом
    FAIL. Это ворота, а не отчёт: «done» означает, что чеклист пройден.
    """
    src = Path.home() / "work" / config.REPO
    gate = Path.home() / "work" / "gates" / config.REPO
    fails: list[str] = []
    lines: list[str] = []

    def ok(msg: str) -> None:
        print(f"  OK    {msg}"); lines.append(f"- OK: {msg}")

    def bad(msg: str) -> None:
        print(f"  FAIL  {msg}"); lines.append(f"- FAIL: {msg}"); fails.append(msg)

    print(f"closeout #{number} ({config.OWNER}/{config.REPO})")

    # 1. артефакт — точный 40-символьный SHA, существующий в каноническом клоне
    art = (artifact or "").strip()
    if len(art) != 40 or not all(c in "0123456789abcdef" for c in art.lower()):
        bad("артефакт не точный 40-символьный SHA")
        art = ""
    elif not src.joinpath(".git").exists():
        bad(f"нет канонического клона {src}")
        art = ""
    elif _git(src, "cat-file", "-e", art + "^{commit}")[0] != 0:
        bad(f"коммит {art[:12]} не найден в {src}")
        art = ""
    else:
        ok(f"артефакт {art}")

    # 2. артефакт доступен в remote — принятое не должно жить только локально
    if art:
        if _git(src, "fetch", "-q", "origin")[0] != 0:
            bad("не удалось fetch origin — доступность в remote не доказана")
        elif _git(src, "merge-base", "--is-ancestor", art, "origin/main")[0] == 0:
            ok("артефакт присутствует в origin/main")
        else:
            bad("артефакт НЕ в origin/main (принятое не опубликовано)")

    # 3. гейт убран: нет незакоммиченного и нет залипшего локфайла.
    # Служебное, что кладёт сам раннер, неубранным НЕ считается.
    if gate.joinpath(".git").exists():
        code, out = _git(gate, "status", "--porcelain")
        if code != 0:
            bad(f"не читается состояние гейта: {out[:80]}")
        else:
            leftovers = [
                ln for ln in out.splitlines()
                if ln[3:].strip().strip("/") not in _GATE_EXPECTED
            ]
            if leftovers:
                names = ", ".join(ln[3:].strip() for ln in leftovers[:5])
                bad(f"в гейте {len(leftovers)} неубранных артефактов: {names}")
            else:
                ok("гейт чист (кроме служебного)")
        lock = gate / ".bot-run.lock"
        if lock.exists():
            pid = lock.read_text().strip()
            alive = False
            try:
                os.kill(int(pid), 0); alive = True
            except (ValueError, ProcessLookupError):
                alive = False
            except PermissionError:
                alive = True
            if alive:
                bad(f"на гейте идёт прогон (PID {pid}) — закрывать нельзя")
            else:
                bad(f"залипший локфайл (PID {pid} мёртв) — убрать перед закрытием")
        else:
            ok("прогонов на гейте нет")
    else:
        ok("гейта нет (нечего убирать)")

    # 4. статус и маркеры самой задачи
    try:
        client = config.make_client()
        issue = client.get_issue(number)
    except (RuntimeError, *config.client_errors()) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    task = Task.from_issue(issue)
    if task.status in ("review", "tested"):
        ok(f"статус status:{task.status} — закрытие уместно")
    elif task.status == "done":
        bad("задача уже status:done")
    else:
        bad(f"статус status:{task.status} — работа не доведена до ревью/тестов")
    if task.superseded:
        bad("на задаче маркер superseded — закрывать как done нельзя")
    else:
        ok("маркера superseded нет")

    print(f"closeout: FAIL={len(fails)}")
    if fails:
        print("done НЕ ставится")
        return 1
    if not confirm:
        print("чеклист пройден; для закрытия повторить с --confirm")
        return 0

    body = (
        f"Closeout #{number}.\n\n"
        f"Канонический артефакт: `{art}`\n\n"
        "Чеклист:\n" + "\n".join(lines) +
        "\n\nПринятые изменения доступны в remote; временные артефакты гейта убраны."
    )
    try:
        client.set_status(number, "done")
        client.add_comment(number, body)
    except config.client_errors() as exc:
        print(f"Ошибка при закрытии: {exc}", file=sys.stderr)
        return 1
    print(f"#{number} → status:done (артефакт {art[:12]})")
    return 0


def cmd_runs(limit: int) -> int:
    runs = latest_runs(limit)
    if not runs:
        print("Сохранённых прогонов нет.")
        return 0
    print(f"Прогоны (новые сверху), всего показано {len(runs)}:")
    for run_id in runs:
        print(f"  {run_id}")
    return 0


def cmd_events(run_id: str) -> int:
    try:
        run = RunState(run_id)
    except OSError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    events = run.events()
    manifest = run.manifest()
    if manifest:
        print(f"{run_id}: repo={manifest.get('repo')} role={manifest.get('role')} "
              f"base={str(manifest.get('base_sha'))[:12]}")
    if not events:
        print("  событий нет")
    for e in events:
        ack = ""
        if e["requires_ack"]:
            ack = f"  [ACK {e['state']}" + (f" by {e['ack_by']}" if e["ack_by"] else " ЖДЁТ") + "]"
        print(f"  {e['created_at']}  {e['kind']:<14} {e['severity']:<8} "
              f"{e['event_id']}{ack}\n      {e['summary']}")
    run.close()
    return 0


def cmd_ack(run_id: str, event_id: str, by: str) -> int:
    """ACK = «получил и принял ответственность», не «согласен» и не «готово»."""
    try:
        run = RunState(run_id)
    except OSError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    done = run.ack(event_id, by)
    run.close()
    if done:
        print(f"{event_id}: ACK от {by}")
        return 0
    print(f"{event_id}: ACK не поставлен (нет события или оно уже подтверждено)",
          file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="orchestrator", description="Bots orchestrator")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="показать очередь queued")

    p_run = sub.add_parser("run-bot", help="вручную запустить бота с брифом (проверка адаптера)")
    src = p_run.add_mutually_exclusive_group()
    src.add_argument("--message", help="бриф текстом")
    src.add_argument("--file", help="прочитать бриф из файла")
    p_run.add_argument(
        "--timeout", type=int, default=_RUN_BOT_TIMEOUT,
        help=f"таймаут запуска, секунды (по умолчанию {_RUN_BOT_TIMEOUT})",
    )

    p_next = sub.add_parser(
        "run-next",
        help="взять старейшую queued, прогнать бота, двинуть статус (in-progress→review/failed)",
    )
    p_next.add_argument(
        "--timeout", type=int, default=_RUN_BOT_TIMEOUT,
        help=f"таймаут запуска бота, секунды (по умолчанию {_RUN_BOT_TIMEOUT})",
    )

    p_sup = sub.add_parser("supersede", help="пометить задачу перекрытой более поздним решением")
    p_sup.add_argument("number", type=int, help="номер issue")
    p_sup.add_argument("--by", required=True,
                       help="чем перекрыто: issue, коммит или вердикт (обязательно)")

    p_clo = sub.add_parser("closeout", help="чеклист закрытия; без --confirm ничего не меняет")
    p_clo.add_argument("number", type=int, help="номер issue")
    p_clo.add_argument("--artifact", required=True,
                       help="канонический артефакт — точный 40-символьный SHA")
    p_clo.add_argument("--confirm", action="store_true",
                       help="при пройденном чеклисте поставить status:done")

    p_runs = sub.add_parser("runs", help="прогоны с сохранённым состоянием")
    p_runs.add_argument("--limit", type=int, default=10)

    p_ev = sub.add_parser("events", help="журнал событий прогона")
    p_ev.add_argument("run_id")

    p_ack = sub.add_parser("ack", help="подтвердить событие (получил и принял ответственность)")
    p_ack.add_argument("run_id")
    p_ack.add_argument("event_id")
    p_ack.add_argument("--by", required=True, help="кто подтверждает")

    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list()
    if args.command == "run-bot":
        return cmd_run_bot(args.message, args.file, args.timeout)
    if args.command == "run-next":
        return cmd_run_next(args.timeout)
    if args.command == "supersede":
        return cmd_supersede(args.number, args.by)
    if args.command == "closeout":
        return cmd_closeout(args.number, args.artifact, args.confirm)
    if args.command == "runs":
        return cmd_runs(args.limit)
    if args.command == "events":
        return cmd_events(args.run_id)
    if args.command == "ack":
        return cmd_ack(args.run_id, args.event_id, args.by)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
