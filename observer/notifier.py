"""Детектор событий и диспетчер уведомлений.

Сравнивает новый снимок доски с предыдущим и формирует события:
  - status->review   (задача перешла в review);
  - status->failed   (задача перешла в failed);
  - needs:human      (на задаче появилась метка эскалации);
  - status->done     (информационное, опционально).

Дедуп — по (project, number, event_type, status): одно и то же состояние
не уведомляется дважды (журнал event в state.sqlite).

Каналы доставки выбираются по секретам в ENV (см. channels/).
"""

from __future__ import annotations

from dataclasses import dataclass

from .collector import TaskSnapshot

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

    def subject(self) -> str:
        kind = {
            "status:review": "на ревью",
            "status:failed": "упала",
            "needs:human": "нужен человек",
            "status:done": "завершена",
        }.get(self.event_type, self.event_type)
        return f"[{self.project}] #{self.number} {kind}: {self.title}"

    def body(self) -> str:
        lines = [f"Проект: {self.project}",
                 f"Задача: #{self.number} {self.title}",
                 f"Событие: {self.event_type}"]
        if self.status:
            lines.append(f"Статус: {self.status}")
        if self.url:
            lines.append(f"Ссылка: {self.url}")
        return "\n".join(lines)


def detect(prev: dict[tuple[str, int], TaskSnapshot],
           current: list[TaskSnapshot],
           include_done: bool = False) -> list[Event]:
    """События из сравнения предыдущего состояния с текущим.

    Первое появление задачи (нет в prev) трактуется как статус None ->
    текущий: новая задача в review/failed сразу считается событием.
    """
    events: list[Event] = []
    for snap in current:
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


def dispatch(events: list[Event], channels: list, store=None) -> int:
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
        subject, body = event.subject(), event.body()
        for channel in channels:
            try:
                channel.send(subject, body)
            except Exception as exc:  # noqa: BLE001 — канал не должен валить цикл
                print(f"Предупреждение: канал {channel.name} не доставил "
                      f"уведомление: {exc}")
        if store is not None:
            store.record_event(event.project, event.number, event.event_type,
                               event.status, event.title, event.url)
        sent += 1
    return sent
