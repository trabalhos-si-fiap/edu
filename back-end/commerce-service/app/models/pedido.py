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
    # Nullable: mesmo depois da C6, `POST /orders` pode criar pedido sem
    # snapshot de endereço — `address_id` em `OrderCreateIn` é opcional
    # (ver app/schemas/pedido.py). Nesse caso `GET /orders/{id}/route`
    # responde 503 por falta de destino, que é o comportamento do legacy.
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
    # Por isso SEM `ForeignKey`, decisão do usuário (2026-08-09, task C10):
    # com FK, apagar um produto que qualquer pedido referencia levanta
    # `IntegrityError`/`ForeignKeyViolationError`, e o caminho "produto saiu
    # do catálogo é pulado" da recompra (C7) fica inalcançável em produção.
    # O legacy nunca teve essa FK, de propósito, pelo mesmo motivo:
    # `back-end/legacy/app/modules/orders/models.py:84`. A coluna continua
    # `nullable=False` e continua sendo snapshot — só o `ForeignKey` sai.
    product_id = Column(UUID(as_uuid=True), nullable=False)
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
    # models/carrinho.py), então um item que nasce do carrinho — o único
    # jeito de criar um pedido desde a task C6 — chega aqui sem fornecedor.
    # Reconfirmado depois da C6 (2026-08-09), `grep -rn "supplier_id" app/`
    # não devolve nenhuma escrita na coluna em lugar nenhum do serviço — só
    # esta declaração de coluna e o comentário "`supplier_id` fica None" em
    # `app/services/pedidos.py::criar_pedido_do_carrinho`, que documenta a
    # omissão de propósito. Quem a preenche é trabalho futuro da separação,
    # ainda não implementado.
    supplier_id = Column(Integer, ForeignKey("fornecedores.id"), nullable=True)

    order = relationship("Order", back_populates="items")


class PedidoStatusHistorico(Base):
    """Sem cliente — fica em português. Só o FK acompanha o rename."""

    __tablename__ = "pedido_status_historico"

    id = Column(Integer, primary_key=True)
    # Só o TIPO acompanha `orders.id` (task C3). O `id` desta tabela continua
    # inteiro: ela não tem cliente e ninguém a endereça por id.
    # `nullable=False` desde a task C10 (decisão do usuário, 2026-08-09):
    # nullable foi o que deixou o bug de flush da C6 gravar `order_id=NULL`
    # em silêncio em vez de levantar.
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    status = Column(String(30), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # quem fez a transição
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
