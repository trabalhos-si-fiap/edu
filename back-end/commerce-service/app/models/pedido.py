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
from sqlalchemy.orm import relationship

from app.database import Base
from app.ids import new_uuid


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

    # `default=new_uuid` é client-side (UUIDv7, ver app/ids.py);
    # `server_default` é o par server-side para qualquer insert que não passe
    # pelo ORM. `gen_random_uuid()` é nativo do PostgreSQL 17.4, sem precisar
    # da extensão `pgcrypto` — mesma medição da task B4.
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # `default=` covers ORM inserts; `server_default` matches schema.sql's
    # `DEFAULT 'CRIADO'` for any insert bypassing the ORM — fix round 1,
    # reviewer finding.
    status = Column(
        String(30), nullable=False, default="CRIADO", server_default=text("'CRIADO'"), index=True
    )
    total = Column(Numeric(10, 2), nullable=False)
    # Rótulo descritivo escolhido no app ("PIX", "Visa ••••1234"). Nunca um
    # dado de cartão: o que identifica a forma de pagamento vive em
    # `payment_methods`, mascarado.
    payment_method = Column(String(120), nullable=False, default="", server_default=text("''"))

    picker_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    deliverer_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    carrier_name = Column(String(100), nullable=True)  # mock por enquanto
    estimated_delivery_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Quando o pedido mudou de status pela última vez. Alimenta os horários da
    # timeline do rastreio; carimbado por `transicionar_pedido`
    # (app/routers/separacao.py).
    status_updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Snapshot do endereço escolhido no checkout. Um pedido é o registro
    # histórico de PARA ONDE foi entregue, então o endereço é copiado aqui e
    # não pode mudar se o aluno editar ou apagar o endereço de origem.
    #
    # Nullable: entre a task C4 e a C6, `POST /orders` cria pedido sem
    # snapshot de endereço (`PedidoCreateIn` perdeu `endereco_entrega` e não
    # ganhou `address_id` ainda — ver app/schemas/pedido.py). Nesse caso
    # `GET /orders/{id}/route` responde 503 por falta de destino, que é o
    # comportamento do legacy.
    #
    # Os tamanhos batem com `auth-users-service/app/models/address.py:23-30`
    # (label 60, zip_code 9, street 160, number 20, complement 120,
    # neighborhood 120, city 120, state 2) e com
    # `back-end/legacy/app/modules/orders/models.py:54-62`. Um endereço que
    # cabe lá tem que caber aqui, senão o checkout estoura no INSERT depois
    # de já ter travado o carrinho.
    ship_label = Column(String(60), nullable=True)
    ship_zip_code = Column(String(9), nullable=True)
    ship_street = Column(String(160), nullable=True)
    ship_number = Column(String(20), nullable=True)
    ship_complement = Column(String(120), nullable=True)
    ship_neighborhood = Column(String(120), nullable=True)
    ship_city = Column(String(120), nullable=True)
    ship_state = Column(String(2), nullable=True)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderItem.product_name",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Snapshot do produto no momento da compra — um pedido é registro
    # histórico e não pode mudar se o catálogo mudar preço ou nome depois.
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    product_name = Column(String(160), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    image_url = Column(String(512), nullable=False, default="", server_default=text("''"))
    rating_avg = Column(Numeric(3, 2), nullable=False, default=0, server_default=text("0"))
    rating_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
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

    order = relationship("Order", back_populates="items")


class PedidoStatusHistorico(Base):
    """Sem cliente — fica em português. Só o FK acompanha o rename."""

    __tablename__ = "pedido_status_historico"

    id = Column(Integer, primary_key=True)
    # Só o TIPO acompanha `orders.id` (task C3). O `id` desta tabela continua
    # inteiro: ela não tem cliente e ninguém a endereça por id.
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    status = Column(String(30), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # quem fez a transição
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
