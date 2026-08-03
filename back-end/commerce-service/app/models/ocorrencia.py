from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class Ocorrencia(Base):
    __tablename__ = "ocorrencias"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)  # FALTA_ESTOQUE | ATRASO_ENTREGA
    status = Column(String(20), nullable=False, default="ABERTA", index=True)

    # Campos específicos de FALTA_ESTOQUE
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=True)
    produtos_sugeridos = Column(JSONB, nullable=True)  # lista de produto_ids similares
    produto_escolhido_id = Column(Integer, ForeignKey("produtos.id"), nullable=True)

    # Campos específicos de ATRASO_ENTREGA
    nova_data_sugerida = Column(DateTime(timezone=True), nullable=True)

    motivo = Column(Text, nullable=False)
    resolucao = Column(String(30), nullable=True)
    # SUBSTITUIR | REMOVER_ITEM | CANCELAR_PEDIDO | ACEITAR_NOVA_DATA

    criado_por = Column(UUID(as_uuid=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    resolvido_em = Column(DateTime(timezone=True), nullable=True)
