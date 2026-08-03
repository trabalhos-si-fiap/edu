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
    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno_id: UUID
    status: str
    endereco_entrega: str
    valor_total: Decimal
    separador_id: UUID | None
    entregador_id: UUID | None
    transportadora_nome: str | None
    data_prevista_entrega: datetime | None
    criado_em: datetime


class PrevisaoEntregaOut(BaseModel):
    data_estimada: datetime | None
    amostras_historicas: int
    confiavel: bool  # False se amostras_historicas < MINIMO_AMOSTRAS


class PedidoFilaOut(PedidoOut):
    """PedidoOut + score de risco — usado na fila de separação priorizada
    (ver services/priorizacao_fila.py). Score mais alto = mais urgente."""

    score_risco: float


class PedidoStatusHistoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    observacao: str | None
    criado_em: datetime
