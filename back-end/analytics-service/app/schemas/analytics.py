"""Schemas de resposta do serviço — nenhum endpoint devolve objeto ORM cru
(`EventLog`); todo campo é explícito aqui em vez de `model_config =
{"from_attributes": True}` expondo o registro inteiro."""

from datetime import datetime

from pydantic import BaseModel


class AlunoEventoOut(BaseModel):
    """Um evento `diagnostic.completed` na linha do tempo do aluno.

    Os nomes dos campos seguem o payload que o produtor realmente publica
    (`learning-service/app/routers/diagnostico.py`): `tema_id` e
    `dominio_tema` — o domínio é do *tema* avaliado, não de um subtema.
    """

    tema_id: int | None = None
    dominio_tema: float | None = None
    acao: str | None = None
    data: datetime | None = None


class StatusContagemOut(BaseModel):
    status: str | None = None
    total: int


class TipoContagemOut(BaseModel):
    tipo: str
    total: int


class ResumoMetricasOut(BaseModel):
    """Chaves de agrupamento `str | None` pelo mesmo motivo que
    `StatusContagemOut.status` é opcional: elas vêm de
    `EventLog.payload["..."].astext`, que devolve NULL quando o payload
    logado não traz a chave. Analytics grava payload bruto produzido por
    outros serviços e não controla o formato — um evento sem a chave tem
    que agregar como "sem valor", nunca derrubar a rota com um 500.
    JSON não admite chave nula, então ela sai serializada como "None"."""

    pedidos_criados: int
    pedidos_por_status: dict[str | None, int]
    ocorrencias_abertas: int
    ocorrencias_resolvidas: int
    diagnosticos_por_acao: dict[str | None, int]


class ResumoExecutivoOut(BaseModel):
    periodo_dias: int
    metricas: ResumoMetricasOut
    resumo_executivo: str


class AnomaliaOut(BaseModel):
    tipo_evento: str
    contagem_hoje: int
    media_historica: float
    desvio_historico: float
    z_score: float | None = None
    anomalia: bool
    dias_historico_usados: int


class AnomaliasResponseOut(BaseModel):
    dias_historico: int
    resultados: list[AnomaliaOut]
