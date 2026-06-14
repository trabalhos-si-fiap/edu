from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    """Provider-neutral email payload. No provider-specific fields leak here."""

    to: str
    subject: str
    html: str
    text: str


class EmailSender(Protocol):
    """The port the application core depends on. Adapters implement it."""

    async def send(self, message: EmailMessage) -> None: ...


class EmailDeliveryError(Exception):
    """Raised when a provider rejects or fails to accept a message."""
