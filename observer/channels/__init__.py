"""Каналы доставки уведомлений.

Активные каналы выбираются по наличию секретов в ENV:
  - telegram — если заданы TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID;
  - email    — если заданы SMTP_HOST и MAIL_TO;
  - console  — всегда доступен (для тестов без секретов).

Все каналы реализуют один интерфейс:
  .name -> str
  .send(subject: str, body: str) -> None
"""

from __future__ import annotations

import os

from ..redact import UnsafeMessage, assert_safe
from .console import ConsoleChannel
from .email import EmailChannel
from .telegram import TelegramChannel


class SafeChannel:
    """Обёртка: не пропускает машинный дамп/секрет в уведомление владельцу.

    Предохранитель стоит ЗДЕСЬ, а не в формирователе текста: собрать сообщение
    другим путём и обойти проверку нельзя. Отказ означает «переформулируй».
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    def send(self, subject: str, body: str) -> None:
        assert_safe(subject, body)
        self._inner.send(subject, body)


def active_channels(force_console: bool = False) -> list:
    """Собирает список активных каналов по секретам в ENV.

    force_console=True добавляет console независимо от прочих каналов
    (используется для notify-dry).
    """
    channels: list = []

    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        channels.append(
            TelegramChannel(
                token=os.environ["TELEGRAM_BOT_TOKEN"],
                chat_id=os.environ["TELEGRAM_CHAT_ID"],
            )
        )

    if os.environ.get("SMTP_HOST") and os.environ.get("MAIL_TO"):
        channels.append(
            EmailChannel(
                host=os.environ["SMTP_HOST"],
                port=int(os.environ.get("SMTP_PORT", "587")),
                user=os.environ.get("SMTP_USER"),
                password=os.environ.get("SMTP_PASS"),
                mail_to=os.environ["MAIL_TO"],
            )
        )

    if force_console or not channels:
        channels.append(ConsoleChannel())

    # Каждый канал — только через предохранитель.
    return [SafeChannel(ch) for ch in channels]


__all__ = [
    "SafeChannel",
    "UnsafeMessage",
    "ConsoleChannel",
    "EmailChannel",
    "TelegramChannel",
    "active_channels",
]
