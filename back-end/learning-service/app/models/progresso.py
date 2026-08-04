from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AlunoTemaProgresso(Base):
    __tablename__ = "aluno_tema_progresso"
    __table_args__ = (UniqueConstraint("aluno_id", "subtema_id", name="uq_aluno_subtema"),)

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subtema_id = Column(Integer, ForeignKey("subtema.id"))
    nivel_dominio = Column(Float, default=0.0, server_default=text("0.0"))
    intervalo_dias = Column(Float, default=1.0, server_default=text("1.0"))
    streak_acertos = Column(Integer, default=0, server_default=text("0"))
    ultima_revisao = Column(DateTime(timezone=True), nullable=True)
    proxima_revisao = Column(DateTime(timezone=True), nullable=True, index=True)
    total_respondidas = Column(Integer, default=0, server_default=text("0"))
