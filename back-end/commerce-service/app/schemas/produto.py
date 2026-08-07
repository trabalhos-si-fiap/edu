"""Schema público de produto.

Campos declarados um a um de propósito: o model `Product` pode ganhar colunas
internas (custo, margem, fornecedor preferencial) que não podem vazar para o
app só porque foram adicionadas ao banco.
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    subtype: str = ""
    description: str = ""
    price: Decimal
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("price")
    def _price_as_string(self, value: Decimal) -> str:
        # O contrato original serializa dinheiro como string ("49.90") para o
        # cliente nunca herdar erro de arredondamento de float. Isso é
        # contrato, não formatação — o app o lê como String.
        return f"{value:.2f}"
