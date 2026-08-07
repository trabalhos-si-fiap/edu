from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AddressIn(BaseModel):
    """Payload de criação/atualização completa — casa com AddressInput.toJson()
    do Flutter (front-end-flutter/lib/features/profile/data/addresses_api.dart)."""

    label: str = Field(default="", max_length=60)
    zip_code: str = Field(max_length=9)
    street: str = Field(max_length=160)
    number: str = Field(max_length=20)
    complement: str = Field(default="", max_length=120)
    neighborhood: str = Field(max_length=120)
    city: str = Field(max_length=120)
    state: str = Field(max_length=2)
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

    label: str | None = Field(default=None, max_length=60)
    zip_code: str | None = Field(default=None, max_length=9)
    street: str | None = Field(default=None, max_length=160)
    number: str | None = Field(default=None, max_length=20)
    complement: str | None = Field(default=None, max_length=120)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)
    is_favorite: bool | None = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
