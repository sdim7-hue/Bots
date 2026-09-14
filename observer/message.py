"""Человеческий формат уведомления владельцу.

Правило (playbook import-ai-ops B7): одно дедуплицированное сообщение на
значимый переход состояния, на человеческом языке. Внутренний номер задачи не
может быть заголовком или единственным содержанием — владелец не обязан помнить
внутреннюю нумерацию. Техническая деталь живёт в дашборде, в сообщении —
идентификатор события для сверки.

Форма:
    [проект · поток] что сдвинулось

    Осталось в очереди: N
    Сейчас: ...
    Нужно от владельца: ...
    Техническая ссылка: <event_id>
"""

from __future__ import annotations

# Поток (человеческое имя события), «что сдвинулось», «сейчас» и «что нужно».
_SHAPES: dict[str, dict[str, str]] = {
    "status:review": {
        "stream": "ревью",
        "moved": "бот закончил работу, результат ждёт проверки",
        "now": "задача на ревью, дальше нужен вердикт",
        "need": "посмотреть результат и решить — принять или вернуть на доработку",
    },
    "status:failed": {
        "stream": "сбой",
        "moved": "прогон не удался",
        "now": "задача остановлена, сама не возобновится",
        "need": "решить, чинить и перезапускать или снимать задачу",
    },
    "needs:human": {
        "stream": "нужен человек",
        "moved": "работа упёрлась в решение, которое бот принять не может",
        "now": "задача ждёт, ничего не тратится",
        "need": "дать недостающие данные или решение",
    },
    "status:done": {
        "stream": "закрыто",
        "moved": "задача завершена и закрыта по чеклисту",
        "now": "работа принята",
        "need": "ничего",
    },
}


def event_id(event) -> str:
    """Стабильный идентификатор события для сверки с дашбордом и журналом."""
    kind = event.event_type.replace(":", "-")
    return f"ev-{event.project}-{event.number}-{kind}"


def format_event(event, queue_remaining: int | None = None) -> tuple[str, str]:
    """(subject, body) в человеческой форме. Заголовок — НЕ номер задачи."""
    shape = _SHAPES.get(event.event_type)
    if shape is None:
        shape = {
            "stream": event.event_type,
            "moved": "состояние задачи изменилось",
            "now": "см. дашборд",
            "need": "посмотреть",
        }

    title = (event.title or "").strip() or "задача без названия"
    subject = f"[{event.project} · {shape['stream']}] {title}"

    lines = [shape["moved"].capitalize() + "."]
    if queue_remaining is not None:
        lines.append(f"Осталось в очереди: {queue_remaining}")
    lines.append(f"Сейчас: {shape['now']}")
    if shape["need"] != "ничего":
        lines.append(f"Нужно от владельца: {shape['need']}")
    lines.append(f"Техническая ссылка: {event_id(event)}")
    return subject, "\n".join(lines)
