"""Детектор событий и диспетчер уведомлений.

Сравнивает новый снимок доски с предыдущим и формирует события:
  - status->review   (задача перешла в review);
  - status->failed   (задача перешла в failed);
  - needs:human      (на задаче появилась метка эскалации);
  - status->done     (информационное, опционально).

Дедуп — по (project, number, event_type, status): одно и то же состояние
не уведомляется дважды (журнал event в state.sqlite).

Каналы доставки выбираются по секретам в ENV (см. channels/); каждый обёрнут
предохранителем (redact.py) — машинный дамп и секреты до владельца не доходят.

ЧТО НЕ уведомляем (playbook import-ai-ops B7): промежуточный прогресс, idle,
retry, неизменившиеся снимки, межботовые сообщения, логи, диффы, стектрейсы,
секреты. Также не уведомляем задачи с маркером `superseded` — решение по ним
перекрыто более поздним (bots.md L85), это не новость для владельца.
"""

from __future__ import annotations

from dataclasses import dataclass

from .collector import TaskSnapshot
from .message import event_id, format_event
from .redact import UnsafeMessage

# Переходы статуса, требующие внимания человека (supervisory mode).
_ATTENTION_STATUSES = ("review", "failed")
# done — информационное событие (по умолчанию выключено).
_INFO_STATUS = "done"


@dataclass
class Event:
    project: str
    number: int
    event_type: str          # 'status:review' | 'status:failed' | 'needs:human' | 'status:done'
    status: str | None
    title: str
    url: str | None

    def event_id(self) -> str:
        return event_id(self)

    def rendered(self, queue_remaining: int | None = None) -> tuple[str, str]:
        """Человеческая форма сообщения (см. message.py)."""
        return format_event(self, queue_remaining)


def detect(prev: dict[tuple[str, int], TaskSnapshot],
           current: list[TaskSnapshot],
           include_done: bool = False) -> list[Event]:
    """События из сравнения предыдущего состояния с текущим.

    Первое появление задачи (нет в prev) трактуется как статус None ->
    текущий: новая задача в review/failed сразу считается событием.
    """
    events: list[Event] = []
    for snap in current:
        # Перекрытые более поздним решением не уведомляем: для владельца это
        # не переход состояния, а протухший HOLD (bots.md L85).
        if getattr(snap, "superseded", False):
            continue
        before = prev.get(snap.key())
        prev_status = before.status if before else None
        prev_needs_human = before.needs_human if before else False

        if snap.status in _ATTENTION_STATUSES and snap.status != prev_status:
            events.append(Event(
                project=snap.project, number=snap.number,
                event_type=f"status:{snap.status}", status=snap.status,
                title=snap.title, url=snap.url,
            ))

        if include_done and snap.status == _INFO_STATUS and prev_status != _INFO_STATUS:
            events.append(Event(
                project=snap.project, number=snap.number,
                event_type=f"status:{_INFO_STATUS}", status=snap.status,
                title=snap.title, url=snap.url,
            ))

        if snap.needs_human and not prev_needs_human:
            events.append(Event(
                project=snap.project, number=snap.number,
                event_type="needs:human", status=snap.status,
                title=snap.title, url=snap.url,
            ))
    return events


def dispatch(events: list[Event], channels: list, store=None,
             queue_remaining: int | None = None) -> int:
    """Отправляет события по каналам с дедупликацией через journal событий.

    Если передан store — событие пропускается, если уже зафиксировано
    (project, number, event_type, status); после успешной отправки —
    записывается. Без store (dry-режим) дедуп не ведётся, store не пишется.

    Возвращает число фактически отправленных (новых) событий.
    """
    sent = 0
    for event in events:
        if store is not None and store.event_exists(
            event.project, event.number, event.event_type, event.status
        ):
            continue
        subject, body = event.rendered(queue_remaining)
        delivered = False
        for channel in channels:
            try:
                channel.send(subject, body)
                delivered = True
            except UnsafeMessage as exc:
                # Отказ предохранителя — дефект формата, а не сбой канала:
                # обходить его нельзя, событие остаётся неотправленным.
                print(f"ОТКАЗ предохранителя ({event.event_id()}): {exc}")
            except Exception as exc:  # noqa: BLE001 — канал не должен валить цикл
                print(f"Предупреждение: канал {channel.name} не доставил "
                      f"уведомление: {exc}")
        # Журналим только фактически доставленное: иначе дедуп «съест» событие,
        # которое владелец никогда не увидит.
        if store is not None and delivered:
            store.record_event(event.project, event.number, event.event_type,
                               event.status, event.title, event.url)
        if delivered:
            sent += 1
    return sent
