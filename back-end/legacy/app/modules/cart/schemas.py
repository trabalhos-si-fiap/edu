import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer


class CartItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=999)


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
        return f"{value:.2f}"


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal

    @field_serializer("total")
    def _total_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"
