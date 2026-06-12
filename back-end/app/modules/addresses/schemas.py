import uuid

from pydantic import BaseModel, ConfigDict, Field


class AddressIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(default="", max_length=60)
    zip_code: str = Field(min_length=1, max_length=9)
    street: str = Field(min_length=1, max_length=160)
    number: str = Field(min_length=1, max_length=20)
    complement: str = Field(default="", max_length=120)
    neighborhood: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    is_favorite: bool = False


class AddressPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str | None = Field(default=None, max_length=60)
    zip_code: str | None = Field(default=None, min_length=1, max_length=9)
    street: str | None = Field(default=None, min_length=1, max_length=160)
    number: str | None = Field(default=None, min_length=1, max_length=20)
    complement: str | None = Field(default=None, max_length=120)
    neighborhood: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    is_favorite: bool | None = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str = ""
    zip_code: str
    street: str
    number: str
    complement: str = ""
    neighborhood: str
    city: str
    state: str
    is_favorite: bool = False
