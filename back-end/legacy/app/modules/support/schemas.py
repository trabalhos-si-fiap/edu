import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SupportMessageIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=2000)


class SupportMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: str
    body: str
    created_at: datetime
