"""Email-канал: отправка через SMTP (стандартный smtplib).

Пароль SMTP НИКОГДА не печатается и не логируется. STARTTLS при наличии
поддержки сервером; авторизация — только если заданы user/password.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage


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

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._user or f"observer@{self._host}"
        msg["To"] = self._mail_to
        msg.set_content(body or subject)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                try:
                    smtp.starttls()
                except smtplib.SMTPException:
                    # Сервер без STARTTLS — продолжаем без шифрования транспорта.
                    pass
                if self._user and self._password:
                    smtp.login(self._user, self._password)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailError(f"SMTP ошибка: {exc}") from exc
