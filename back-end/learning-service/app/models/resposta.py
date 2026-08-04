from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class DiagnosticoResposta(Base):
    """
    Resposta individual de cada questão de um diagnóstico. Antes existia
    no schema mas não era persistida (só o agregado por subtema era
    salvo). Agora é gravada de verdade — é o que permite ao Chatbot
    Service confirmar "o aluno já respondeu essa questão" antes de expor
    o gabarito na explicação (ver GET /diagnostic/questions/{id}/context).
    """

    __tablename__ = "diagnostico_resposta"

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    questao_id = Column(Integer, ForeignKey("questao.id"), index=True)
    alternativa_escolhida = Column(String(1), nullable=False)
    acertou = Column(Boolean, nullable=False)
    respondido_em = Column(DateTime(timezone=True), server_default=func.now())
