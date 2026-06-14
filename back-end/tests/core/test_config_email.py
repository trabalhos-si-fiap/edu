from app.core.config import settings


def test_email_defaults_are_safe() -> None:
    assert settings.EMAIL_BACKEND == "console"
    assert settings.RESEND_API_KEY is None
    assert settings.EMAIL_FROM


def test_password_reset_defaults() -> None:
    assert settings.PASSWORD_RESET_CODE_TTL_SECONDS == 600
    assert settings.PASSWORD_RESET_MAX_ATTEMPTS == 5
    assert settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS == 5
    assert settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS == 900
    assert settings.EMAIL_SEND_TIME_LIMIT == 30
    assert settings.EMAIL_SEND_SOFT_TIME_LIMIT == 25
