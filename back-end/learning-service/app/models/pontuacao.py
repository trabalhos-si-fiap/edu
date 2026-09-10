from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class LancamentoPontos(Base):
    """Extrato de pontos — uma linha por fato que pontuou, nunca um contador.

    Um contador incrementado a cada acerto seria leitura seguida de escrita
    num recurso compartilhado (regra 3 do CLAUDE.md), e não permitiria
    explicar de onde vieram os pontos.

    `uq_lancamento_idempotente` é a regra inteira da idempotência: responder
    de novo a mesma questão tenta gravar a mesma trinca e o
    `ON CONFLICT DO NOTHING` do serviço a descarta.
    """

    __tablename__ = "lancamento_pontos"
    __table_args__ = (
        UniqueConstraint("aluno_id", "origem", "referencia", name="uq_lancamento_idempotente"),
    )

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # "questao" | "revisao" | "etapa" | "streak" — ver services/pontuacao.py
    origem = Column(String(20), nullable=False)
    referencia = Column(String(60), nullable=False)
    pontos = Column(Integer, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
