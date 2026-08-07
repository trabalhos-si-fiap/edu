"""Schemas de review. Copiados de `legacy/app/modules/products/schemas.py` —
já estão em inglês e não precisam de tradução (mesmo critério de
`app/schemas/produto.py`)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
