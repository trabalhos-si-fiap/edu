from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EstoqueAjuste(Base):
    """Porte de `InventoryAdjustment` do Java. Trilha de auditoria de estoque.

    Guarda `quantidade_anterior` e `quantidade_nova` (os dois campos do
    Java), NÃO o delta: o delta é `nova - anterior`, e gravá-lo criaria uma
    terceira fonte da verdade para o mesmo fato, que pode divergir. O schema
    Pydantic o expõe como campo calculado (`app/schemas/estoque.py`).

    Em PORTUGUÊS, ao contrário de `carriers`: este agregado não tem cliente
    próprio — ele é lido através de `/products/{id}/stock-adjustments`, que é
    uma sub-rota de produto. Mesmo critério de `estoque` e `ocorrencias`.

    Sem `ondelete` no FK, de propósito: uma linha de estoque apagada não pode
    levar sua auditoria junto. Um ajuste que não deixa rastro é
    indistinguível de uma perda de dado, e é exatamente isso que esta tabela
    existe para impedir.
    """

    __tablename__ = "estoque_ajustes"

    id = Column(Integer, primary_key=True)
    estoque_id = Column(Integer, ForeignKey("estoque.id"), nullable=False, index=True)
    quantidade_anterior = Column(Integer, nullable=False)
    quantidade_nova = Column(Integer, nullable=False)
    motivo = Column(String(300), nullable=False)
    # Quem fez o ajuste. UUID do `sub` do JWT; sem FK porque o dono do
    # usuário é o auth-users-service, com banco próprio.
    autor_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
