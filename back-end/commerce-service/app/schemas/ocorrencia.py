import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FaltaEstoqueIn(BaseModel):
    pedido_id: uuid.UUID
    produto_id: uuid.UUID
    motivo: str


class AtrasoEntregaIn(BaseModel):
    pedido_id: uuid.UUID
    motivo: str
    nova_data_sugerida: datetime


ResolucaoTipo = Literal["substituir", "remover_item", "cancelar_pedido", "aceitar_nova_data"]


class ResolverOcorrenciaIn(BaseModel):
    resolucao: ResolucaoTipo
    produto_escolhido_id: uuid.UUID | None = None  # obrigatório se resolucao == "substituir"


class ProdutoSugeridoOut(BaseModel):
    id: uuid.UUID
    nome: str
    preco: float
    imagem_url: str | None = None


class OcorrenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # `id` da ocorrência continua inteiro — só `pedido_id` acompanha
    # `orders.id` virando uuid (task C3).
    id: int
    pedido_id: uuid.UUID
    tipo: str
    status: str
    produto_id: uuid.UUID | None
    nova_data_sugerida: datetime | None
    motivo: str
    resolucao: str | None
    criado_em: datetime
    resolvido_em: datetime | None


class OcorrenciaDetalheOut(OcorrenciaOut):
    produto_original: ProdutoSugeridoOut | None = None
    produtos_sugeridos: list[ProdutoSugeridoOut] = []
