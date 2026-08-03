from datetime import date
from typing import Literal
from uuid import UUID

from edu_common.security import MAX_PASSWORD_BYTES
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

# Precisa bater exatamente com `_educationLevels` em register_screen.dart.
EducationLevel = Literal["9º ano", "1º ano", "2º ano", "3º ano", "Vestibulando"]

Role = Literal["student", "admin", "separador", "entregador"]


def _validar_bytes_senha(v: str) -> None:
    """bcrypt trunca (e `edu_common.hash_password` levanta `ValueError`) para
    senhas acima de `MAX_PASSWORD_BYTES` em UTF-8. `Field(max_length=...)` do
    Pydantic conta *caracteres*, não bytes — uma senha curta em caracteres
    mas cheia de emoji/acentos passaria por ele e ainda estouraria o limite
    do bcrypt, virando 500 em vez de 422. Checar aqui, nos três schemas que
    carregam senha em texto plano, fecha essa lacuna antes do hash.
    """
    if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Senha não pode passar de {MAX_PASSWORD_BYTES} bytes")


class RegisterIn(BaseModel):
    """Payload de `POST /auth/register` — casa com `AuthApi.register()`."""

    name: str
    email: EmailStr
    phone: str
    birth_date: str  # "DD/MM/AAAA", convertido no router
    education_level: EducationLevel
    password: str

    @field_validator("password")
    @classmethod
    def senha_forte(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        if not any(c in '!@#$%^&*(),.?":{}|<>' for c in v):
            raise ValueError("Senha deve conter ao menos um caractere especial")
        _validar_bytes_senha(v)
        return v

    @field_validator("birth_date")
    @classmethod
    def data_valida(cls, v: str) -> str:
        try:
            date.fromisoformat("-".join(reversed(v.split("/"))))
        except (ValueError, IndexError) as exc:
            raise ValueError("Data de nascimento deve estar no formato DD/MM/AAAA") from exc
        return v


class RegisterStaffIn(BaseModel):
    """Cadastro interno de separador/entregador/admin — usado só pelo painel
    administrativo (não pelo app do aluno), por isso mantém nomes em pt-br."""

    nome: str
    email: EmailStr
    senha: str
    telefone: str | None = None
    documento: str | None = None
    role: Role

    @field_validator("senha")
    @classmethod
    def senha_dentro_do_limite(cls, v: str) -> str:
        _validar_bytes_senha(v)
        return v


class LoginIn(BaseModel):
    """Payload de `POST /auth/login` — casa com `AuthApi.login()`."""

    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — não é segredo, é o esquema OAuth2


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    role: str


class AuthResponseOut(BaseModel):
    """Formato esperado por `AuthApi._persistAuth()`: `{user, tokens}`."""

    user: UserOut
    tokens: TokensOut


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    email: EmailStr
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def senha_forte(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        _validar_bytes_senha(v)
        return v
