import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.orders.enums import OrderStatus


class OrderCreateIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Payment is selected client-side; the order stores a descriptive label
    # (e.g. "PIX", "Visa ••••1234"). Optional to stay close to the original
    # empty-body contract.
    payment_method: str = Field(default="", max_length=120)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("unit_price")
    def _price_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    total: Decimal
    status: OrderStatus
    payment_method: str = ""
    created_at: datetime
    items: list[OrderItemOut]

    @field_serializer("total")
    def _total_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"
