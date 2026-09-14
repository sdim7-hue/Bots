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
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            # Тело ошибки полезно; токен в URL, поэтому его в текст не включаем.
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise TelegramError(f"Telegram API {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise TelegramError(f"Сеть недоступна: {exc.reason}") from exc

        # Успех доставки = ответ API с message_id. HTTP 200 сам по себе его не
        # доказывает: Telegram отдаёт ok=false с кодом 200 (например, бот
        # заблокирован получателем). Без message_id считаем НЕ доставленным.
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise TelegramError("ответ Telegram не разобран как JSON") from exc
        if not data.get("ok") or "message_id" not in (data.get("result") or {}):
            desc = str(data.get("description", "message_id отсутствует"))[:200]
            raise TelegramError(f"Telegram не подтвердил доставку: {desc}")
