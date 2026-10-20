import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from cropstar_api.settings import Settings


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    @property
    def available(self) -> bool:
        """Whether this instance can send email at all."""
        ...

    def send(self, email: Email) -> None: ...


class NullMailer:
    """Used when no SMTP server is configured: features that need email report so."""

    @property
    def available(self) -> bool:
        return False

    def send(self, email: Email) -> None:
        raise RuntimeError("Email is not configured on this instance")


class SmtpMailer:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._starttls = starttls

    @property
    def available(self) -> bool:
        return True

    def send(self, email: Email) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.body)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._starttls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


def mailer_from_settings(settings: Settings) -> Mailer:
    if not settings.smtp_host:
        return NullMailer()
    return SmtpMailer(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_from,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
        starttls=settings.smtp_starttls,
    )
