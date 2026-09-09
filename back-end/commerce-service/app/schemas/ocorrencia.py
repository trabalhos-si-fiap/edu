import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ids import Int32Id


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
    transportadora_id: int | None = None
    nova_data_sugerida: datetime | None
    motivo: str
    resolucao: str | None
    criado_em: datetime
    resolvido_em: datetime | None


class OcorrenciaDetalheOut(OcorrenciaOut):
    produto_original: ProdutoSugeridoOut | None = None
    produtos_sugeridos: list[ProdutoSugeridoOut] = []


# Os quatro tipos que uma ocorrência de TRANSPORTADORA pode ter. Porte de
# `OccurrenceType` do Java: `DELIVERY_DELAY` é o `ATRASO_ENTREGA` que já
# existia aqui, e por isso não virou um valor novo. `FALTA_ESTOQUE` fica de
# fora de propósito — falta de estoque é do separador, não da transportadora,
# e tem rota própria (`POST /occurrences/stock-shortage`).
TipoOcorrenciaTransportadora = Literal["ATRASO_ENTREGA", "DANO", "FALHA_ENTREGA", "OUTRO"]


class OcorrenciaTransportadoraIn(BaseModel):
    pedido_id: uuid.UUID
    transportadora_id: Int32Id
    tipo: TipoOcorrenciaTransportadora
    motivo: str = Field(min_length=1, max_length=2000)


class FecharOcorrenciaIn(BaseModel):
    observacao: str | None = Field(default=None, max_length=2000)


class OcorrenciaList(BaseModel):
    items: list[OcorrenciaOut]
    total: int
    limit: int
    offset: int
