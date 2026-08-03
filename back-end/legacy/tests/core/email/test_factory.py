import pytest

from app.core.email.console import ConsoleEmailAdapter
from app.core.email.factory import get_email_sender
from app.core.email.resend import ResendEmailAdapter


def test_factory_returns_console_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "EMAIL_BACKEND", "console")
    assert isinstance(get_email_sender(), ConsoleEmailAdapter)


def test_factory_returns_resend_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "re_test_key")
    assert isinstance(get_email_sender(), ResendEmailAdapter)


def test_package_reexports() -> None:
    from app.core.email import EmailMessage, EmailSender, get_email_sender  # noqa: F401
