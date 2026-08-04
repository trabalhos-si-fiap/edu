from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.models.event_log import EventLog
from app.schemas.analytics import (
    AlunoEventoOut,
    AnomaliasResponseOut,
    ResumoExecutivoOut,
    ResumoMetricasOut,
    StatusContagemOut,
    TipoContagemOut,
)
from app.services.deteccao_anomalia import detectar_anomalias
from app.services.resumo_ia import gerar_resumo_executivo, gerar_resumo_fallback

router = APIRouter(prefix="/analytics", tags=["analytics"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
# `dias`/`dias_historico` viram `WHERE criado_em >= ...` — sem teto um admin
# (ou um bug no Flutter) poderia pedir um range de décadas e forçar um scan
# gigante na tabela de log de eventos.
MAX_DIAS = 365


@router.get("/aluno/{aluno_id}", response_model=list[AlunoEventoOut])
async def evolucao_aluno(
    aluno_id: str,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Evolução de domínio do aluno ao longo do tempo, extraída do log de eventos."""
    result = await db.execute(
        select(EventLog)
        .where(
            EventLog.tipo == "diagnostic.completed",
            EventLog.payload["aluno_id"].astext == aluno_id,
        )
        .order_by(EventLog.criado_em.asc())
        .limit(limit)
        .offset(offset)
    )
    eventos = result.scalars().all()
    return [
        AlunoEventoOut(
            tema_id=e.payload.get("tema_id"),
            dominio_tema=e.payload.get("dominio_tema"),
            acao=e.payload.get("acao"),
            data=e.criado_em,
        )
        for e in eventos
    ]


@router.get("/entregas", response_model=list[StatusContagemOut])
async def metricas_entregas(
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Contagem de pedidos por status, com base nos eventos order.status_changed.

    Sem paginação: o resultado tem no máximo uma linha por status de pedido —
    um conjunto pequeno e fixo definido pelo Commerce Service, não uma
    listagem que cresce com o volume de dados.
    """
    result = await db.execute(
        select(
            EventLog.payload["status"].astext.label("status"),
            func.count().label("total"),
        )
        .where(EventLog.tipo == "order.status_changed")
        .group_by(text("status"))
    )
    return [StatusContagemOut(status=row.status, total=row.total) for row in result.all()]


@router.get("/resumo", response_model=list[TipoContagemOut])
async def resumo_geral(
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Contagem geral de eventos por tipo, útil como visão rápida do dashboard.

    Sem paginação: no máximo uma linha por routing key ligada à fila
    (`ROUTING_KEYS` em `app/events/consumer.py`), um conjunto pequeno e fixo.
    """
    result = await db.execute(
        select(EventLog.tipo, func.count().label("total")).group_by(EventLog.tipo)
    )
    return [TipoContagemOut(tipo=row.tipo, total=row.total) for row in result.all()]


@router.get("/resumo-executivo", response_model=ResumoExecutivoOut)
async def resumo_executivo(
    dias: int = Query(7, ge=1, le=MAX_DIAS),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Painel executivo para o admin: métricas agregadas do período (pedidos,
    status, ocorrências, diagnósticos) + um resumo em linguagem natural
    gerado por LLM a partir desses MESMOS números — o LLM só narra o que
    já foi calculado abaixo, nunca inventa métrica nova (ver resumo_ia.py).
    """
    desde = datetime.now(UTC) - timedelta(days=dias)

    pedidos_criados_result = await db.execute(
        select(func.count()).where(EventLog.tipo == "order.created", EventLog.criado_em >= desde)
    )
    pedidos_criados = pedidos_criados_result.scalar() or 0

    status_result = await db.execute(
        select(
            EventLog.payload["status"].astext.label("status"),
            func.count().label("total"),
        )
        .where(EventLog.tipo == "order.status_changed", EventLog.criado_em >= desde)
        .group_by(text("status"))
    )
    pedidos_por_status = {row.status: row.total for row in status_result.all()}

    ocorrencias_abertas_result = await db.execute(
        select(func.count()).where(
            EventLog.tipo.in_(["order.stock_issue", "order.delivery_delayed"]),
            EventLog.criado_em >= desde,
        )
    )
    ocorrencias_criadas = ocorrencias_abertas_result.scalar() or 0

    ocorrencias_resolvidas_result = await db.execute(
        select(func.count()).where(
            EventLog.tipo == "order.occurrence_resolved", EventLog.criado_em >= desde
        )
    )
    ocorrencias_resolvidas = ocorrencias_resolvidas_result.scalar() or 0
    ocorrencias_abertas = max(0, ocorrencias_criadas - ocorrencias_resolvidas)

    diagnosticos_result = await db.execute(
        select(
            EventLog.payload["acao"].astext.label("acao"),
            func.count().label("total"),
        )
        .where(EventLog.tipo == "diagnostic.completed", EventLog.criado_em >= desde)
        .group_by(text("acao"))
    )
    diagnosticos_por_acao = {row.acao: row.total for row in diagnosticos_result.all()}

    contexto = {
        "periodo_dias": dias,
        "pedidos_criados": pedidos_criados,
        "pedidos_por_status": pedidos_por_status,
        "ocorrencias_abertas": ocorrencias_abertas,
        "ocorrencias_resolvidas": ocorrencias_resolvidas,
        "diagnosticos_por_acao": diagnosticos_por_acao,
    }

    resumo = await gerar_resumo_executivo(contexto)
    if resumo is None:
        resumo = gerar_resumo_fallback(contexto)

    return ResumoExecutivoOut(
        periodo_dias=dias,
        metricas=ResumoMetricasOut(
            pedidos_criados=pedidos_criados,
            pedidos_por_status=pedidos_por_status,
            ocorrencias_abertas=ocorrencias_abertas,
            ocorrencias_resolvidas=ocorrencias_resolvidas,
            diagnosticos_por_acao=diagnosticos_por_acao,
        ),
        resumo_executivo=resumo,
    )


@router.get("/anomalias", response_model=AnomaliasResponseOut)
async def anomalias_operacionais(
    dias_historico: int = Query(30, ge=1, le=MAX_DIAS),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Compara a contagem de hoje de eventos-chave (pedidos criados,
    ocorrências, diagnósticos) contra a média histórica dos últimos
    `dias_historico` dias, sinalizando desvios estatisticamente
    significativos (z-score). Tipos sem histórico suficiente ainda
    (menos de `MINIMO_DIAS_HISTORICO` dias de dados) não aparecem no
    resultado — ver `services/deteccao_anomalia.py`.
    """
    return AnomaliasResponseOut(
        dias_historico=dias_historico,
        resultados=await detectar_anomalias(db, dias_historico=dias_historico),
    )
