from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class Ocorrencia(Base):
    __tablename__ = "ocorrencias"

    id = Column(Integer, primary_key=True)
    # O NOME da coluna fica: `ocorrencias` é agregado sem cliente. Só o alvo
    # do FK acompanha o rename de `pedidos` para `orders` (task C2).
    pedido_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)  # FALTA_ESTOQUE | ATRASO_ENTREGA
    # `default=` covers ORM inserts; `server_default` matches schema.sql's
    # `DEFAULT 'ABERTA'` for any insert bypassing the ORM — fix round 1,
    # reviewer finding.
    status = Column(
        String(20), nullable=False, default="ABERTA", server_default=text("'ABERTA'"), index=True
    )

    # Campos específicos de FALTA_ESTOQUE
    produto_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    produtos_sugeridos = Column(
        JSONB, nullable=True
    )  # lista de produto_ids similares (string, JSON não tem UUID)
    produto_escolhido_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)

    # Campos específicos de ATRASO_ENTREGA
    nova_data_sugerida = Column(DateTime(timezone=True), nullable=True)

    motivo = Column(Text, nullable=False)
    resolucao = Column(String(30), nullable=True)
    # SUBSTITUIR | REMOVER_ITEM | CANCELAR_PEDIDO | ACEITAR_NOVA_DATA

    criado_por = Column(UUID(as_uuid=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    resolvido_em = Column(DateTime(timezone=True), nullable=True)
