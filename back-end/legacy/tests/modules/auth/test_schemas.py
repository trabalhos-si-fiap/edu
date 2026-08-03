from datetime import date
from typing import ClassVar

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import (
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)


class TestRegisterIn:
    _valid: ClassVar[dict[str, object]] = {
        "name": "Maria Silva",
        "email": "maria@example.com",
        "phone": "11999998888",
        "birth_date": date(1995, 6, 15),
        "education_level": "Vestibulando",
        "password": "Secret!1",
    }

    def test_accepts_valid_payload(self) -> None:
        r = RegisterIn(**self._valid)
        assert r.email == "maria@example.com"
        assert r.phone == "11999998888"
        assert r.education_level.value == "Vestibulando"

    def test_accepts_ddmmyyyy_birth_date_from_flutter(self) -> None:
        r = RegisterIn(**{**self._valid, "birth_date": "15/06/1995"})
        assert r.birth_date == date(1995, 6, 15)

    def test_accepts_iso_birth_date(self) -> None:
        r = RegisterIn(**{**self._valid, "birth_date": "1995-06-15"})
        assert r.birth_date == date(1995, 6, 15)

    def test_strips_phone_formatting(self) -> None:
        r = RegisterIn(**{**self._valid, "phone": "(11) 99999-8888"})
        assert r.phone == "11999998888"

    def test_accepts_10_digit_phone(self) -> None:
        r = RegisterIn(**{**self._valid, "phone": "1133334444"})
        assert r.phone == "1133334444"

    def test_normalizes_email_to_lowercase(self) -> None:
        r = RegisterIn(**{**self._valid, "email": "Foo@Example.COM"})
        assert r.email == "foo@example.com"

    def test_rejects_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "email": "not-an-email"})

    def test_rejects_email_missing_domain(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "email": "foo@bar"})

    def test_rejects_short_password(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "password": "Short!1"})  # 7 chars

    def test_rejects_password_without_special_char(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "password": "NoSpecial123"})

    def test_accepts_password_with_any_listed_special_char(self) -> None:
        for special in '!@#$%^&*(),.?":{}|<>':
            r = RegisterIn(**{**self._valid, "password": f"Password{special}1"})
            assert r.password.endswith("1")

    def test_rejects_unknown_education_level(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "education_level": "Astronauta"})

    def test_rejects_name_too_long(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "name": "x" * 121})

    def test_rejects_phone_too_short(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "phone": "123"})

    def test_rejects_phone_too_long(self) -> None:
        with pytest.raises(ValidationError):
            RegisterIn(**{**self._valid, "phone": "123456789012"})


class TestLoginIn:
    def test_valid_lowercases_email(self) -> None:
        login = LoginIn(email="Foo@bar.com", password="whatever!1")
        assert login.email == "foo@bar.com"

    def test_rejects_oversize_email(self) -> None:
        with pytest.raises(ValidationError):
            LoginIn(email="a" * 250 + "@b.com", password="x!")


class TestRefreshIn:
    def test_valid(self) -> None:
        RefreshIn(refresh_token="some.jwt.token")

    def test_rejects_empty_token(self) -> None:
        with pytest.raises(ValidationError):
            RefreshIn(refresh_token="")


class TestTokenPair:
    def test_default_token_type_is_bearer(self) -> None:
        t = TokenPair(access_token="a", refresh_token="r")
        assert t.token_type == "bearer"


class TestUserOut:
    def test_does_not_expose_password_hash(self) -> None:
        fields = set(UserOut.model_fields.keys())
        assert "password_hash" not in fields
        assert {
            "id",
            "name",
            "email",
            "phone",
            "birth_date",
            "education_level",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        } <= fields
