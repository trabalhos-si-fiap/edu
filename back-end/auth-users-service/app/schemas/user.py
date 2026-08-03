from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: UUID
    nome: str
    email: EmailStr
    role: str
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


class UserUpdateIn(BaseModel):
    nome: str | None = None
    telefone: str | None = None
