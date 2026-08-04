from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class EventLog(Base):
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True)
    tipo = Column(String(50), nullable=False, index=True)  # ex: diagnostic.completed
    payload = Column(JSONB, nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)
