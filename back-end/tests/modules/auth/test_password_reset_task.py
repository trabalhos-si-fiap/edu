from app.core.email.base import EmailMessage
from app.modules.auth.tasks import _build_reset_message, _send_reset_email


def test_build_reset_message_contains_code_and_ttl() -> None:
    msg = _build_reset_message("user@example.com", "123456")
    assert isinstance(msg, EmailMessage)
    assert msg.to == "user@example.com"
    assert "123456" in msg.text
    assert "123456" in msg.html
    assert "10" in msg.text  # 600s == 10 minutes


async def test_send_reset_email_uses_injected_sender() -> None:
    sent: list[EmailMessage] = []

    class FakeSender:
        async def send(self, message: EmailMessage) -> None:
            sent.append(message)

    await _send_reset_email("user@example.com", "123456", sender=FakeSender())
    assert len(sent) == 1
    assert sent[0].to == "user@example.com"
