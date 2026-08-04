import dataclasses

from app.core.email.base import EmailDeliveryError, EmailMessage


def test_email_message_is_frozen_dataclass() -> None:
    msg = EmailMessage(to="a@b.com", subject="Hi", html="<p>hi</p>", text="hi")
    assert msg.to == "a@b.com"
    assert msg.subject == "Hi"
    assert dataclasses.is_dataclass(msg)
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        msg.to = "other@b.com"  # type: ignore[misc]


def test_email_delivery_error_is_exception() -> None:
    assert issubclass(EmailDeliveryError, Exception)
