from __future__ import annotations

import json
import urllib.request

from job_finder.notifications.base import Notifier

TELEGRAM_MAX_TEXT = 3500


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, subject: str, message: str) -> None:
        chunks = self._chunk_message(message)
        for index, chunk in enumerate(chunks):
            prefix = subject if index == 0 else f"{subject} (cont.)"
            self._send_chunk(f"{prefix}\n\n{chunk}")

    def _send_chunk(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20):
            return

    def _chunk_message(self, message: str) -> list[str]:
        lines = message.splitlines()
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1
            if current and current_length + line_length > TELEGRAM_MAX_TEXT:
                chunks.append("\n".join(current))
                current = [line]
                current_length = line_length
            else:
                current.append(line)
                current_length += line_length

        if current:
            chunks.append("\n".join(current))
        return chunks or [message[:TELEGRAM_MAX_TEXT]]
