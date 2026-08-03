from loguru import logger

from app.core.email.base import EmailMessage


class ConsoleEmailAdapter:
    """Dev/test adapter: logs the message, never touches the network."""

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email[console] to={} subject={!r}\n{}",
            message.to,
            message.subject,
            message.text,
        )
