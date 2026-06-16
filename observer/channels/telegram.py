"""Telegram-канал: отправка сообщения через Bot API (urllib, без зависимостей).

Токен бота НИКОГДА не печатается и не логируется.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_API = "https://api.telegram.org"


class TelegramError(RuntimeError):
    """Ошибка отправки в Telegram."""


class TelegramChannel:
    name = "telegram"

    def __init__(self, token: str, chat_id: str, timeout: int = 15) -> None:
        self._token = token
        self._chat_id = chat_id
        self._timeout = timeout

    def send(self, subject: str, body: str) -> None:
        text = subject if not body else f"{subject}\n\n{body}"
        payload = json.dumps({
            "chat_id": self._chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }).encode("utf-8")
        url = f"{_API}/bot{self._token}/sendMessage"
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "bots-observer")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            # Тело ошибки полезно; токен в URL, поэтому его в текст не включаем.
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise TelegramError(f"Telegram API {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise TelegramError(f"Сеть недоступна: {exc.reason}") from exc
