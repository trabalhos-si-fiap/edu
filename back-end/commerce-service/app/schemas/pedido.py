from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PedidoItemIn(BaseModel):
    produto_id: int
    fornecedor_id: int
    quantidade: int
    preco_unitario: Decimal


class PedidoCreateIn(BaseModel):
    endereco_entrega: str
    itens: list[PedidoItemIn]


class PedidoOut(BaseModel):
    """Contrato voltado ao aluno — `POST /orders`, `GET /orders/mine`,
    `GET /orders/{id}`. NÃO inclui `separador_id`/`entregador_id`:
    identificadores operacionais internos (quem está separando/entregando)
    não são assunto do aluno, mesma classe do vazamento de `descricao_ia`
    fechado no learning-service (fix round 1, reviewer finding). Endpoints
    de staff (separador/entregador/admin) usam `PedidoStaffOut` abaixo.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno_id: UUID
    status: str
    endereco_entrega: str
    valor_total: Decimal
    transportadora_nome: str | None
    data_prevista_entrega: datetime | None
    criado_em: datetime


class PedidoStaffOut(PedidoOut):
    """PedidoOut + os identificadores operacionais que o aluno não deve
    ver, mas que separador/entregador/admin precisam para saber quem está
    com o pedido. Usado em picking/, delivery/ e admin/ — nunca em
    pedidos.py (rotas do aluno)."""

    separador_id: UUID | None
    entregador_id: UUID | None


class PrevisaoEntregaOut(BaseModel):
    data_estimada: datetime | None
    amostras_historicas: int
    confiavel: bool  # False se amostras_historicas < MINIMO_AMOSTRAS


class PedidoFilaOut(PedidoStaffOut):
    """PedidoStaffOut + score de risco — usado na fila de separação
    priorizada (ver services/priorizacao_fila.py). Score mais alto = mais
    urgente."""

    score_risco: float


class PedidoStatusHistoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    observacao: str | None
    criado_em: datetime
