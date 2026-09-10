from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EtapaRoadmap(Base):
    """Uma etapa do percurso: um subtema, com prazo e conclusão.

    `uq_etapa_aluno_subtema` é o que torna a regeneração segura — regerar é
    apagar e reinserir, e a constraint garante que nenhuma passagem crie
    duas etapas do mesmo subtema para o mesmo aluno.

    `ordem` é a posição no percurso (0-based), derivada de `Tema.ordem` e
    `Subtema.ordem` na geração. Ela não é única de propósito: duas
    regenerações podem produzir a mesma ordem para subtemas diferentes se o
    seed mudar, e o que identifica a etapa é o subtema, não a posição.
    """

    __tablename__ = "etapa_roadmap"
    __table_args__ = (UniqueConstraint("aluno_id", "subtema_id", name="uq_etapa_aluno_subtema"),)

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subtema_id = Column(Integer, ForeignKey("subtema.id"), nullable=False)
    ordem = Column(Integer, nullable=False)
    prazo = Column(Date, nullable=False)
    concluida_em = Column(DateTime(timezone=True), nullable=True)
