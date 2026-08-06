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
    """`status` nunca é nulo.

    `EventLog.payload["status"].astext` devolve NULL quando o payload logado
    não traz a chave — este serviço grava payload bruto de outros serviços e
    não controla o formato. As duas rotas que agrupam por status resolvem
    esse NULL na origem com a MESMA sentinela (`SEM_CHAVE_STATUS`), porque
    `/executive-summary` agrupa num `dict[str, int]` e JSON não admite chave
    nula. Manter `str | None` aqui deixava a mesma ausência com duas formas
    na mesma API.
    """

    status: str
    total: int


class TipoContagemOut(BaseModel):
    tipo: str
    total: int


class ResumoMetricasOut(BaseModel):
    """Chaves de agrupamento sempre `str`. Elas vêm de
    `EventLog.payload["..."].astext`, que devolve NULL quando o payload logado
    não traz a chave — Analytics grava payload bruto produzido por outros
    serviços e não controla o formato. A rota resolve esse NULL na origem,
    trocando-o pelos sentinelas `sem_status`/`sem_acao` (`routers/analytics.py`),
    de modo que um evento sem a chave agrega como "sem valor" sem derrubar a
    rota com um 500. Tipar a chave como `str | None` seria mentira em JSON, que
    não admite chave nula: o None sairia serializado como a string "None".

    `sem_status` não é exclusiva desta rota: é a MESMA sentinela que
    `StatusContagemOut.status` (`/analytics/deliveries`) usa para a mesma
    ausência — as duas rotas que agrupam por status concordam na forma."""

    pedidos_criados: int
    pedidos_por_status: dict[str, int]
    ocorrencias_abertas: int
    ocorrencias_resolvidas: int
    diagnosticos_por_acao: dict[str, int]


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
