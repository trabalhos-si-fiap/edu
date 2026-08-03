from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: EmailStr
    role: str
    ativo: bool
    criado_em: datetime


class UserUpdateIn(BaseModel):
    nome: str | None = None
    telefone: str | None = None
