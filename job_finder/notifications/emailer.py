from __future__ import annotations

import smtplib
from email.message import EmailMessage

from job_finder.notifications.base import Notifier


class EmailNotifier(Notifier):
    name = "email"

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        to_address: str,
        use_ssl: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_address = to_address
        self.use_ssl = use_ssl

    def send(self, subject: str, message: str) -> None:
        email = EmailMessage()
        email["Subject"] = subject
        email["From"] = self.from_address
        email["To"] = self.to_address
        email.set_content(message)

        if self.use_ssl:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(email)
            return

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(email)
