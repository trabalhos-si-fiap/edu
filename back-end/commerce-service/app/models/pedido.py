from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Order(Base):
    """Pedido. Em inglês — tabela e colunas — porque é um agregado com
    cliente (o app Flutter, na fase 4).

    `pedido_status_historico` continua em português: sem cliente. `status`
    guarda o estado INTERNO (nove valores, `StatusPedido`); a tradução para
    os seis do contrato (`StatusContrato`) acontece na serialização, não
    aqui.
    """

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # `default=` covers ORM inserts; `server_default` matches schema.sql's
    # `DEFAULT 'CRIADO'` for any insert bypassing the ORM — fix round 1,
    # reviewer finding.
    status = Column(
        String(30), nullable=False, default="CRIADO", server_default=text("'CRIADO'"), index=True
    )
    endereco_entrega = Column(Text, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    picker_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    deliverer_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    carrier_name = Column(String(100), nullable=True)  # mock por enquanto
    estimated_delivery_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    # `nullable=True` explícito, não uma mudança: a coluna já nascia nullable
    # (o model não declarava `nullable=`, e o default do SQLAlchemy é
    # nullable). Medido na cadeia de migrations aplicada a um banco
    # descartável, `\d pedido_itens`: `fornecedor_id | integer | | ` — sem
    # `not null`. `cart_items` não tem noção de fornecedor (ver
    # models/carrinho.py), então um item que nascesse do carrinho chegaria
    # aqui sem fornecedor. Hoje quem preenche é o próprio payload de
    # `POST /orders` (`PedidoItemIn.supplier_id`, obrigatório); nada em
    # `separacao.py` escreve nesta coluna — `grep -rn "fornecedor_id\|
    # supplier_id" app/` não acha um único write fora de `pedidos.py`.
    supplier_id = Column(Integer, ForeignKey("fornecedores.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)


class PedidoStatusHistorico(Base):
    """Sem cliente — fica em português. Só o FK acompanha o rename."""

    __tablename__ = "pedido_status_historico"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    status = Column(String(30), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # quem fez a transição
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
