"""
Detecção de anomalias operacionais simples: compara a contagem diária de
eventos-chave (pedidos criados, ocorrências, diagnósticos) de HOJE contra
a média histórica dos últimos dias, usando z-score.

IMPORTANTE — isso não é machine learning, é estatística descritiva simples
(média + desvio padrão). É intencional para o MVP: um detector mais
sofisticado (ex: séries temporais com sazonalidade, tipo Prophet) exigiria
muito mais dado histórico do que a plataforma tem hoje. Ver README.

Tipos de evento sem histórico suficiente (`MINIMO_DIAS_HISTORICO`) são
omitidos do resultado — mais honesto do que forçar uma classificação
"normal" sem base estatística para isso.
"""

from datetime import UTC, datetime, timedelta
from statistics import mean, stdev

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_log import EventLog

MINIMO_DIAS_HISTORICO = 5
LIMIAR_Z_SCORE = 2.0

TIPOS_MONITORADOS = [
    "order.created",
    "order.stock_issue",
    "order.delivery_delayed",
    "diagnostic.completed",
]


async def _contagem_diaria_por_tipo(db: AsyncSession, tipo: str, dias: int) -> dict[str, int]:
    """{data_iso: contagem} dos últimos `dias` dias (incluindo hoje) para um tipo de evento."""
    desde = datetime.now(UTC) - timedelta(days=dias)
    result = await db.execute(
        select(
            func.date(EventLog.criado_em).label("dia"),
            func.count().label("total"),
        )
        .where(EventLog.tipo == tipo, EventLog.criado_em >= desde)
        .group_by(func.date(EventLog.criado_em))
    )
    return {str(row.dia): row.total for row in result.all()}


async def detectar_anomalias(db: AsyncSession, dias_historico: int = 30) -> list[dict]:
    """
    Para cada tipo de evento monitorado, compara a contagem de HOJE contra
    a média + desvio padrão dos dias anteriores (excluindo hoje da base).
    """
    hoje = datetime.now(UTC).date().isoformat()
    resultado = []

    for tipo in TIPOS_MONITORADOS:
        contagens = await _contagem_diaria_por_tipo(db, tipo, dias_historico)
        contagem_hoje = contagens.pop(hoje, 0)  # remove hoje da base histórica

        valores_historicos = list(contagens.values())
        if len(valores_historicos) < MINIMO_DIAS_HISTORICO:
            continue  # histórico insuficiente para julgar o que é "normal"

        media_historica = mean(valores_historicos)
        desvio_historico = stdev(valores_historicos) if len(valores_historicos) > 1 else 0.0

        if desvio_historico == 0:
            z_score = None
            e_anomalia = contagem_hoje != media_historica
        else:
            z_score = (contagem_hoje - media_historica) / desvio_historico
            e_anomalia = abs(z_score) >= LIMIAR_Z_SCORE

        resultado.append(
            {
                "tipo_evento": tipo,
                "contagem_hoje": contagem_hoje,
                "media_historica": round(media_historica, 2),
                "desvio_historico": round(desvio_historico, 2),
                "z_score": round(z_score, 2) if z_score is not None else None,
                "anomalia": e_anomalia,
                "dias_historico_usados": len(valores_historicos),
            }
        )

    return resultado
