"""Консольный канал — печать в stdout. Для тестов без секретов."""

from __future__ import annotations


class ConsoleChannel:
    name = "console"

    def send(self, subject: str, body: str) -> None:
        print(f"[notify:console] {subject}")
        if body:
            for line in body.splitlines():
                print(f"    {line}")
