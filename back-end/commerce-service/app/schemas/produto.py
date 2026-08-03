"""Schema público de produto.

Campos declarados um a um de propósito: o model `Produto` pode ganhar colunas
internas (custo, margem, fornecedor preferencial) que não podem vazar para o
app só porque foram adicionadas ao banco.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(validation_alias="id")
    name: str = Field(validation_alias="nome")
    description: str | None = Field(default=None, validation_alias="descricao")
    price: Decimal = Field(validation_alias="preco")
    category: str | None = Field(default=None, validation_alias="categoria")
    image_url: str | None = Field(default=None, validation_alias="imagem_url")
