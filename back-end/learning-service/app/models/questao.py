from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Questao(Base):
    __tablename__ = "questao"
    __table_args__ = (
        CheckConstraint("nivel_dificuldade BETWEEN 1 AND 3", name="ck_nivel_dificuldade"),
    )

    id = Column(Integer, primary_key=True)
    # index=True: schema.sql original tem `CREATE INDEX idx_questao_subtema
    # ON questao(subtema_id)` — sem isso, o autogenerate do Alembic nunca
    # criaria esse índice (divergência descoberta comparando o schema.sql
    # contra o model, conforme a Recipe D pede).
    subtema_id = Column(Integer, ForeignKey("subtema.id"), index=True)
    enunciado = Column(Text, nullable=False)
    alternativas = Column(JSONB, nullable=False)  # {"A": "...", "B": "...", ...}
    gabarito = Column(String(1), nullable=False)
    nivel_dificuldade = Column(Integer, nullable=False)  # 1=fácil, 2=médio, 3=difícil
    fonte = Column(String(50), default="ENEM")
    ano = Column(Integer, nullable=True)
