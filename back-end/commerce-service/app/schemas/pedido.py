from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.pedido import Order
from app.services.pedidos import endereco_formatado
from app.services.status_pedido import StatusContrato, status_do_contrato

# `PedidoItemIn`/`PedidoCreateIn`/`PedidoOut` morreram nesta task (C6): o
# `product_name` que `PedidoItemIn` carregava era dívida temporária
# declarada com a C6 como dona (task C4) — some porque agora o nome vem do
# catálogo, não do corpo da requisição. `PedidoOut` é substituído por
# `OrderOut` abaixo, mesmo conjunto de campos do alvo de paridade
# (`back-end/legacy/app/modules/orders/schemas.py:40::OrderOut`).


class OrderCreateIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Rótulo escolhido no cliente ("PIX", "Visa ••••1234"). Opcional para
    # ficar perto do contrato de corpo vazio do legacy.
    payment_method: str = Field(default="", max_length=120)
    # Qual endereço salvo recebe o pedido. Opcional pelo mesmo motivo; o app
    # sempre manda o id do endereço selecionado.
    address_id: UUID | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("unit_price")
    def _price_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class OrderOut(BaseModel):
    """Contrato do aluno. `status` é o valor do CONTRATO (seis), não o
    interno (nove) — a tradução acontece em `de_order` abaixo.

    NÃO inclui `picker_id`/`deliverer_id`: identificadores operacionais não
    são assunto do aluno. Staff usa `PedidoStaffOut`.

    NÃO inclui `endereco_entrega` nem os `ship_*`: medido,
    `grep -rn "endereco_entrega" front-end-flutter/lib/` só devolve
    `features/logistics/domain/order.dart::Pedido.fromJson` (Flutter de
    STAFF), e o cliente do aluno
    (`features/marketplace/domain/order_summary.dart::OrderSummary.fromJson`)
    lê só `id, total, status, created_at, items`. O alvo de paridade
    (`back-end/legacy/app/modules/orders/schemas.py:40::OrderOut`) também
    não tem o campo.
    """

    id: UUID
    total: Decimal
    status: StatusContrato
    payment_method: str = ""
    created_at: datetime
    items: list[OrderItemOut]

    @field_serializer("total")
    def _total_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @classmethod
    def de_order(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            total=order.total,
            status=status_do_contrato(order.status),
            payment_method=order.payment_method,
            created_at=order.created_at,
            items=[OrderItemOut.model_validate(i) for i in order.items],
        )


class PedidoStaffOut(BaseModel):
    """Visão de staff. Campos vindos de `orders` em inglês, com uma exceção
    deliberada: `endereco_entrega` continua em português porque é o nome
    de chave que o Flutter de staff já lê (medido:
    `grep -rn "endereco_entrega" front-end-flutter/lib/` devolve
    `features/logistics/domain/order.dart::Pedido.fromJson`) — o valor é
    computado por `endereco_formatado`, não uma coluna do model.
    `score_risco` (de `priorizacao_fila`) é a outra exceção, mas só entra
    em `PedidoFilaOut` abaixo, não aqui. Correção de fix round 2 (code
    review): a versão anterior deste docstring dizia "nenhum [campo] em
    português nesta classe", contradita pela própria declaração do campo
    `endereco_entrega: str` nesta classe.

    Classe PLANA (não herda de `PedidoOut`) porque `endereco_entrega` não é
    mais uma coluna do model — é composta por `endereco_formatado` a partir
    de sete dos oito `ship_*` (ver o docstring de `endereco_formatado` para
    o porquê do oitavo, `ship_label`, ficar de fora).
    `from_attributes`/`model_validate` não alcançaria isso (não há atributo
    `endereco_entrega` no ORM), por isso o único construtor é `de_order`;
    não use `PedidoStaffOut.model_validate(order)`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: str
    total: Decimal
    endereco_entrega: str
    carrier_name: str | None
    estimated_delivery_at: datetime | None
    created_at: datetime
    picker_id: UUID | None
    deliverer_id: UUID | None

    @classmethod
    def de_order(cls, order: Order) -> "PedidoStaffOut":
        return cls(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            total=order.total,
            endereco_entrega=endereco_formatado(order),
            carrier_name=order.carrier_name,
            estimated_delivery_at=order.estimated_delivery_at,
            created_at=order.created_at,
            picker_id=order.picker_id,
            deliverer_id=order.deliverer_id,
        )


class PrevisaoEntregaOut(BaseModel):
    data_estimada: datetime | None
    amostras_historicas: int
    confiavel: bool  # False se amostras_historicas < MINIMO_AMOSTRAS


class PedidoFilaOut(PedidoStaffOut):
    """PedidoStaffOut + score de risco — usado na fila de separação
    priorizada (ver services/priorizacao_fila.py). Score mais alto = mais
    urgente.

    `user_id` (de `orders`) ao lado de `score_risco` (calculado, sem
    tabela) é o resultado correto da regra de língua, não uma
    inconsistência.
    """

    score_risco: float


class PedidoStatusHistoricoOut(BaseModel):
    """Todos os campos vêm de `pedido_status_historico`, tabela sem cliente
    — ficam em português."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    observacao: str | None
    criado_em: datetime
