"""Email-канал: отправка через SMTP (стандартный smtplib).

Пароль SMTP НИКОГДА не печатается и не логируется.

Три правила, каждое — следствие конкретного дефекта:
  1. Порт 465 — это implicit TLS (SMTPS), а не STARTTLS: `smtplib.SMTP` там
     не работает, нужен `SMTP_SSL`. Выбирается по порту либо по SMTP_SSL=1.
  2. **Пароль не уходит по нешифрованному каналу.** Прежняя версия при провале
     STARTTLS «продолжала без шифрования» и тут же делала login — то есть
     отправляла креды открытым текстом. Теперь: нет TLS и есть пароль -> отказ.
  3. Успех = сервер принял ВСЕХ получателей. `send_message` возвращает словарь
     отклонённых; пустой словарь — это подтверждение, а отсутствие исключения
     само по себе ничего не доказывает (тот же класс, что message_id у Telegram).
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

# Порты с implicit TLS.
_SSL_PORTS = (465, 8465)


class EmailError(RuntimeError):
    """Ошибка отправки письма."""


class EmailChannel:
    name = "email"

    def __init__(self, host: str, port: int, mail_to: str,
                 user: str | None = None, password: str | None = None,
                 timeout: int = 30) -> None:
        self._host = host
        self._port = port
        self._mail_to = mail_to
        self._user = user
        self._password = password
        self._timeout = timeout
        self._implicit_ssl = (port in _SSL_PORTS
                              or os.environ.get("SMTP_SSL", "").strip() in ("1", "true", "yes"))

    def _connect(self):
        if self._implicit_ssl:
            return smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout)
        return smtplib.SMTP(self._host, self._port, timeout=self._timeout)

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._user or f"observer@{self._host}"
        msg["To"] = self._mail_to
        msg.set_content(body or subject)

        try:
            with self._connect() as smtp:
                secure = self._implicit_ssl
                if not secure:
                    try:
                        smtp.starttls()
                        secure = True
                    except smtplib.SMTPException:
                        secure = False
                if self._password and not secure:
                    raise EmailError(
                        "STARTTLS недоступен, а задан пароль — отправка отменена: "
                        "передавать креды открытым текстом нельзя "
                        "(используй порт 465 или SMTP_SSL=1)")
                if self._user and self._password:
                    smtp.login(self._user, self._password)
                refused = smtp.send_message(msg)
        except EmailError:
            raise
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailError(f"SMTP ошибка: {exc}") from exc

        if refused:
            raise EmailError("сервер отклонил получателей: " + ", ".join(refused))
