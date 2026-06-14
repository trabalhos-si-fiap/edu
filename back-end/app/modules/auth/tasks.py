import asyncio

from loguru import logger

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.email import EmailMessage, EmailSender, get_email_sender


def _build_reset_message(email: str, code: str) -> EmailMessage:
    minutes = settings.PASSWORD_RESET_CODE_TTL_SECONDS // 60
    subject = "Seu codigo de recuperacao de senha"
    text = (
        f"Seu codigo de recuperacao e {code}.\n"
        f"Ele expira em {minutes} minutos. Se voce nao pediu isso, ignore este e-mail."
    )
    html = (
        f"<p>Seu codigo de recuperacao e <strong>{code}</strong>.</p>"
        f"<p>Ele expira em {minutes} minutos. Se voce nao pediu isso, ignore este e-mail.</p>"
    )
    return EmailMessage(to=email, subject=subject, html=html, text=text)


async def _send_reset_email(email: str, code: str, *, sender: EmailSender | None = None) -> None:
    sender = sender or get_email_sender()
    await sender.send(_build_reset_message(email, code))


@celery_app.task(
    name="auth.send_password_reset_email",
    time_limit=settings.EMAIL_SEND_TIME_LIMIT,
    soft_time_limit=settings.EMAIL_SEND_SOFT_TIME_LIMIT,
)
def send_password_reset_email_task(email: str, code: str) -> None:
    """Send the OTP email. Idempotent: re-running re-delivers the same code."""
    asyncio.run(_send_reset_email(email, code))
    logger.info("auth: password reset email dispatched to={}", email)
