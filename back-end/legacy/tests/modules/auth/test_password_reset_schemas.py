import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import PasswordResetConfirmIn, PasswordResetRequestIn


def test_request_lowercases_email() -> None:
    assert PasswordResetRequestIn(email="Foo@Example.COM").email == "foo@example.com"


def test_confirm_accepts_valid_payload() -> None:
    payload = PasswordResetConfirmIn(email="a@b.com", code="123456", new_password="Secret!1")
    assert payload.code == "123456"
    assert payload.email == "a@b.com"


@pytest.mark.parametrize("bad_code", ["12345", "1234567", "12a456", "abcdef"])
def test_confirm_rejects_non_six_digit_code(bad_code: str) -> None:
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(email="a@b.com", code=bad_code, new_password="Secret!1")


def test_confirm_rejects_password_without_special_char() -> None:
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(email="a@b.com", code="123456", new_password="Secret12")
