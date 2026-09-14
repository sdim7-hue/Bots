"""Предохранитель уведомлений: не даёт отправить владельцу машинный дамп.

Правило (playbook import-ai-ops B7): push-уведомление — человеческий язык о том,
что сдвинулось. Пути ФС, адреса, хэши, токены и стектрейсы в него не попадают:
техническая деталь живёт в системе и в дашборде, в сообщении — ссылка на событие.

ОТКАЗ означает «переформулируй», а НЕ «обойди фильтр». Поэтому проверка встроена
в канал-обёртку (channels.SafeChannel), а не в формирователь текста: обойти её,
собрав сообщение иначе, нельзя.
"""

from __future__ import annotations

import re

# (категория, регулярка). Порядок важен: секреты проверяются первыми.
_RULES: list[tuple[str, re.Pattern]] = [
    # Секреты и их имена.
    ("секрет: токен GitHub", re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})")),
    ("секрет: JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("секрет: приватный ключ", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("секрет: слово-маркер со значением",
     # Без ведущего \b: в BOTS_TOKEN подчёркивание — тоже \w, границы слова там нет.
     re.compile(r"[A-Za-z0-9_]*(?:token|password|passwd|secret|bearer|api[-_]?key|credential)s?\b\s*[:=]\s*\S+",
                re.IGNORECASE)),
    # Машинные детали.
    ("IP-адрес", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("хэш/длинная hex-строка", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
    ("абсолютный путь ФС", re.compile(r"(?:(?<=\s)|^)(?:/(?:home|etc|opt|srv|var|usr|mnt|root)/\S+|[A-Za-z]:\\\\?\S+)")),
    ("стектрейс", re.compile(r"Traceback \(most recent call last\)|^\s+File \".+\", line \d+",
                             re.MULTILINE)),
]


class UnsafeMessage(RuntimeError):
    """Сообщение не прошло предохранитель и НЕ отправлено."""


def violations(text: str) -> list[str]:
    """Категории нарушений в тексте. Сами найденные значения НЕ возвращаются.

    Возврат значения был бы дырой: оно попало бы в лог отказа, то есть туда же,
    куда мы его не хотели пускать.
    """
    return [name for name, pattern in _RULES if pattern.search(text or "")]


def assert_safe(*parts: str) -> None:
    """Бросает UnsafeMessage, если хоть одна часть сообщения небезопасна."""
    found: list[str] = []
    for part in parts:
        for name in violations(part):
            if name not in found:
                found.append(name)
    if found:
        raise UnsafeMessage(
            "сообщение не отправлено, требуется переформулировать; "
            "категории: " + ", ".join(found)
        )
