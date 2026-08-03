from app.core.config import Settings


def _default(name: str) -> object:
    """The value declared on the Settings class, independent of any local .env."""
    return Settings.model_fields[name].default


def test_email_defaults_are_safe() -> None:
    # Assert the SHIPPED defaults, not the loaded values — a developer's local
    # .env may set a real RESEND_API_KEY or switch the backend.
    assert _default("EMAIL_BACKEND") == "console"
    assert _default("RESEND_API_KEY") is None
    assert _default("EMAIL_FROM")


def test_password_reset_defaults() -> None:
    assert _default("PASSWORD_RESET_CODE_TTL_SECONDS") == 600
    assert _default("PASSWORD_RESET_MAX_ATTEMPTS") == 5
    assert _default("PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS") == 5
    assert _default("PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS") == 900
    assert _default("EMAIL_SEND_TIME_LIMIT") == 30
    assert _default("EMAIL_SEND_SOFT_TIME_LIMIT") == 25
