import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.auth.enums import EducationLevel

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_DIGITS_RE = re.compile(r"^\d{10,11}$")
_SPECIAL_CHAR_RE = re.compile(r'[!@#$%^&*(),.?":{}|<>]')
_DDMMYYYY_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


class RegisterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    phone: str = Field(max_length=20)  # pre-normalization; digits-only post-validator
    birth_date: date
    education_level: EducationLevel
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        normalized = v.lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError("invalid email format")
        return normalized

    @field_validator("phone", mode="before")
    @classmethod
    def _digits_only_phone(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("phone must be a string")
        digits = re.sub(r"\D", "", v)
        if not _PHONE_DIGITS_RE.match(digits):
            raise ValueError("phone must contain 10 or 11 digits")
        return digits

    @field_validator("birth_date", mode="before")
    @classmethod
    def _parse_birth_date(cls, v: object) -> object:
        if isinstance(v, str):
            m = _DDMMYYYY_RE.match(v)
            if m:
                day, month, year = m.groups()
                return date(int(year), int(month), int(day))
        return v

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        if not _SPECIAL_CHAR_RE.search(v):
            raise ValueError("password must contain at least one special character")
        return v


class LoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    phone: str
    birth_date: date
    education_level: EducationLevel
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair
