from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PedidoItemIn(BaseModel):
    """Campos em inglês porque seguem `order_items` (regra de língua do
    spec: o schema segue a TABELA, não o router)."""

    product_id: UUID
    supplier_id: int
    quantity: int
    unit_price: Decimal


class PedidoCreateIn(BaseModel):
    # `endereco_entrega` fica em português: a coluna `orders.endereco_entrega`
    # não muda de nome nesta task (some em C4).
    endereco_entrega: str
    itens: list[PedidoItemIn]


class PedidoOut(BaseModel):
    """Contrato voltado ao aluno — `POST /orders`, `GET /orders/mine`,
    `GET /orders/{id}`. NÃO inclui `picker_id`/`deliverer_id`:
    identificadores operacionais internos (quem está separando/entregando)
    não são assunto do aluno, mesma classe do vazamento de `descricao_ia`
    fechado no learning-service (fix round 1, reviewer finding). Endpoints
    de staff (separador/entregador/admin) usam `PedidoStaffOut` abaixo.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: str
    endereco_entrega: str
    total: Decimal
    carrier_name: str | None
    estimated_delivery_at: datetime | None
    created_at: datetime


class PedidoStaffOut(PedidoOut):
    """PedidoOut + os identificadores operacionais que o aluno não deve
    ver, mas que separador/entregador/admin precisam para saber quem está
    com o pedido. Usado em picking/, delivery/ e admin/ — nunca em
    pedidos.py (rotas do aluno)."""

    picker_id: UUID | None
    deliverer_id: UUID | None


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
