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
    cliente, e o cliente já chega aqui HOJE, não na fase 4: o gateway
    roteia as rotas que leem estes models para o commerce, e o Flutter
    aponta para o gateway em toda plataforma.
    `sed -n '17,23p' back-end/api-gateway/app/routing.py`:

        "orders": "commerce",
        "cart": "commerce",
        "payment-methods": "commerce",
        "picking": "commerce",
        "delivery": "commerce",
        "occurrences": "commerce",
        "admin": "commerce",

    e `api_config.dart::baseUrl` (front-end-flutter/lib/core/network/,
    linhas 33-40) devolve `http://localhost:8100/api` ou
    `http://10.0.2.2:8100/api` — a porta 8100 é o gateway.

    `pedido_status_historico` continua em português: sem cliente.

    `status` guarda o estado INTERNO (nove valores, `StatusPedido`). A
    função que traduz para os seis do contrato (`StatusContrato`) EXISTE
    (`app/services/status_pedido.py::status_do_contrato`) mas ainda NÃO
    está ligada a nenhuma resposta: `grep -rn "status_do_contrato"
    app/routers/ app/schemas/` devolve zero linhas (exit 1), e
    `PedidoOut.status` é `str` alimentado por `from_attributes`, ou seja,
    serializa o valor interno cru. Quem liga é a task C6, em
    `OrderOut.de_order` (`status=status_do_contrato(order.status)`); o
    contrato de staff continua expondo o valor interno de propósito.
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
    # aqui sem fornecedor. Hoje o único write é o payload de `POST /orders`
    # — `grep -rn "supplier_id" app/routers/`:
    #     app/routers/pedidos.py:48:                supplier_id=item.supplier_id,
    # uma linha só; a separação não escreve nesta coluna.
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
