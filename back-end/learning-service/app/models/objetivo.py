from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ObjetivoAluno(Base):
    """Objetivo de estudo do aluno e a data em que ele quer chegar lá.

    Um por aluno (`uq_objetivo_aluno`): a spec fala em "um objetivo ativo",
    e sem a constraint dois POSTs simultâneos do mesmo aluno criariam dois,
    com o roadmap gerado a partir de um deles e a tela lendo o outro.

    `titulo` é texto livre com teto (regra 4 do CLAUDE.md). `data_alvo` é
    `Date`, não `DateTime`: prova é um dia, não um instante, e comparar
    fuso horário com "faltam N dias" só produziria erro de um dia.
    """

    __tablename__ = "objetivo_aluno"
    __table_args__ = (UniqueConstraint("aluno_id", name="uq_objetivo_aluno"),)

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    titulo = Column(String(120), nullable=False)
    data_alvo = Column(Date, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
