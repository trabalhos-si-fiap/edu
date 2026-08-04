import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


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
        # The original contract serializes monetary values as strings ("49.90")
        # so clients never inherit float rounding error.
        return f"{value:.2f}"


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class CategoryOut(BaseModel):
    type: str
    count: int


class CategoryList(BaseModel):
    items: list[CategoryOut]


class ReviewIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author: str
    rating: int
    comment: str = ""
    created_at: datetime


class ReviewList(BaseModel):
    items: list[ReviewOut]
    total: int
    rating_avg: float
    rating_count: int
