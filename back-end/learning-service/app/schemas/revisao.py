from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RevisaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtema_id: int
    nome: str
    nivel_dominio: float
    proxima_revisao: datetime | None
    video_url: str | None = None
