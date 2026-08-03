from uuid import UUID

from pydantic import BaseModel, field_validator


class AddressIn(BaseModel):
    """Payload de criação/atualização completa — casa com AddressInput.toJson()
    do Flutter (front-end-flutter/lib/features/profile/data/addresses_api.dart)."""

    label: str = ""
    zip_code: str
    street: str
    number: str
    complement: str = ""
    neighborhood: str
    city: str
    state: str
    is_favorite: bool = False

    @field_validator("state")
    @classmethod
    def uf_valida(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 2:
            raise ValueError("UF deve ter 2 letras")
        return v


class AddressPatch(BaseModel):
    """Atualização parcial — usada tanto pelo form completo (todos os campos)
    quanto pelo atalho `setFavorite` (só `is_favorite`)."""

    label: str | None = None
    zip_code: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    is_favorite: bool | None = None


class AddressOut(BaseModel):
    id: UUID
    label: str
    zip_code: str
    street: str
    number: str
    complement: str
    neighborhood: str
    city: str
    state: str
    is_favorite: bool

    class Config:
        from_attributes = True
