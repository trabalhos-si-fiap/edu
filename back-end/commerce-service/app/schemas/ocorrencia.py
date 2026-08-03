from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FaltaEstoqueIn(BaseModel):
    pedido_id: int
    produto_id: int
    motivo: str


class AtrasoEntregaIn(BaseModel):
    pedido_id: int
    motivo: str
    nova_data_sugerida: datetime


ResolucaoTipo = Literal["substituir", "remover_item", "cancelar_pedido", "aceitar_nova_data"]


class ResolverOcorrenciaIn(BaseModel):
    resolucao: ResolucaoTipo
    produto_escolhido_id: int | None = None  # obrigatório se resolucao == "substituir"


class ProdutoSugeridoOut(BaseModel):
    id: int
    nome: str
    preco: float
    imagem_url: str | None = None


class OcorrenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pedido_id: int
    tipo: str
    status: str
    produto_id: int | None
    nova_data_sugerida: datetime | None
    motivo: str
    resolucao: str | None
    criado_em: datetime
    resolvido_em: datetime | None


class OcorrenciaDetalheOut(OcorrenciaOut):
    produto_original: ProdutoSugeridoOut | None = None
    produtos_sugeridos: list[ProdutoSugeridoOut] = []
