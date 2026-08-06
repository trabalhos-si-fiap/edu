from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: EmailStr
    role: str
    ativo: bool
    criado_em: datetime


class UserUpdateIn(BaseModel):
    nome: str | None = Field(default=None, max_length=150)
    telefone: str | None = Field(default=None, max_length=20)
