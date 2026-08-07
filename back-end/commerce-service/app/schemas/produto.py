"""Schema público de produto.

Campos declarados um a um de propósito: o model `Product` pode ganhar colunas
internas (custo, margem, fornecedor preferencial) que não podem vazar para o
app só porque foram adicionadas ao banco.
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    price: Decimal
    type: str | None = None
    image_url: str | None = None
