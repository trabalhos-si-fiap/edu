from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.pedido import Order
from app.services.pedidos import endereco_formatado


class PedidoItemIn(BaseModel):
    """Campos em inglês porque seguem `order_items` (regra de língua do
    spec: o schema segue a TABELA, não o router).

    `product_name`: `order_items.product_name` é `NOT NULL` sem default (a
    tabela já nasce assim — ver a migration desta task), e `criar_pedido`
    (app/routers/pedidos.py) monta o `OrderItem` a partir deste schema. Sem
    o campo aqui, o INSERT estouraria para todo `POST /orders`. Este campo
    morre junto com o schema inteiro na task C6, quando o nome do produto
    passa a vir do carrinho, não do corpo da requisição."""

    product_id: UUID
    supplier_id: int
    quantity: int
    unit_price: Decimal
    product_name: str = Field(max_length=160)


class PedidoCreateIn(BaseModel):
    """`endereco_entrega` saiu: a coluna morreu (vira os oito `ship_*`) e
    não existe para onde escrever a string. Entre esta task e a C6,
    `POST /orders` cria pedido sem snapshot de endereço — o mesmo contrato
    que a C6 e o legacy têm (`OrderCreateIn.address_id: uuid.UUID | None =
    None`, corpo vazio aceito). O endereço volta na C6, pela fonte real
    (`address_id` → auth-users), não por texto livre."""

    itens: list[PedidoItemIn]


class PedidoOut(BaseModel):
    """Contrato voltado ao aluno — `POST /orders`, `GET /orders/mine`,
    `GET /orders/{id}`. NÃO inclui `picker_id`/`deliverer_id`:
    identificadores operacionais internos (quem está separando/entregando)
    não são assunto do aluno, mesma classe do vazamento de `descricao_ia`
    fechado no learning-service (fix round 1, reviewer finding). Endpoints
    de staff (separador/entregador/admin) usam `PedidoStaffOut` abaixo.

    NÃO inclui `endereco_entrega` nem um substituto computado: medido,
    `grep -rn "endereco_entrega" front-end-flutter/lib/` só devolve
    `features/logistics/domain/order.dart::Pedido.fromJson` (Flutter de
    STAFF, alvo da C4b), e o cliente do aluno
    (`features/marketplace/domain/order_summary.dart::OrderSummary.fromJson`)
    lê só `id, total, status, created_at, items`. O alvo de paridade
    (`back-end/legacy/app/modules/orders/schemas.py:40::OrderOut`) também
    não tem o campo, e a C6 substitui este schema por `OrderOut` com esse
    mesmo conjunto — dar ao aluno um campo que ninguém lê e que morre duas
    tasks depois não faria sentido.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: str
    total: Decimal
    carrier_name: str | None
    estimated_delivery_at: datetime | None
    created_at: datetime


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
    português nesta classe", contradita pela própria declaração de
    `endereco_entrega` seis linhas abaixo.

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
