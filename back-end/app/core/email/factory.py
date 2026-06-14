from app.core.config import settings
from app.core.email.base import EmailSender
from app.core.email.console import ConsoleEmailAdapter
from app.core.email.resend import ResendEmailAdapter


def get_email_sender() -> EmailSender:
    """Resolve the configured email adapter. Only place that reads settings."""
    if settings.EMAIL_BACKEND == "resend":
        return ResendEmailAdapter(api_key=settings.RESEND_API_KEY, sender=settings.EMAIL_FROM)
    return ConsoleEmailAdapter()
