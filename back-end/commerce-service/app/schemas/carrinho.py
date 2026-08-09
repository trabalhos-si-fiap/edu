"""Schemas do carrinho. Porte de `legacy/app/modules/cart/schemas.py` (task B8).

Campos declarados um a um (regra 6 do CLAUDE.md) — `CartItemOut` não usa
`from_attributes`, é montado campo a campo em `montar_cart_out` porque mistura
dados do item (`quantity`) com dados do produto resolvidos ao vivo (`name`,
`price`, ...).
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

# Nomeado, não um 999 solto em dois arquivos: `app/routers/pedidos.py::recomprar`
# clampa nele antes de repassar para `CartItemIn` (achado 2 do code review da
# task C7 — ver o docstring de `recomprar`).
QUANTIDADE_MAXIMA = 999


class CartItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=QUANTIDADE_MAXIMA)


class CartItemOut(BaseModel):
    product_id: uuid.UUID
    name: str
    type: str
    subtype: str = ""
    price: Decimal
    quantity: int
    subtotal: Decimal
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("price", "subtotal")
    def _money_as_string(self, value: Decimal) -> str:
        # Dinheiro como string ("49.90"), nunca float — mesmo contrato de
        # `ProductOut._price_as_string`.
        return f"{value:.2f}"


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal

    @field_serializer("total")
    def _total_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"
