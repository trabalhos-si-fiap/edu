"""
Estimativa de prazo de entrega a partir de dados históricos reais — média
do tempo entre coleta (EM_TRANSITO) e entrega (ENTREGUE) de pedidos já
concluídos, extraída de `pedido_status_historico`.

IMPORTANTE — isso é estatística simples (média sobre dados reais), não
embeddings nem LLM. É intencional: é o desenho de "IA de Predição" já
combinado desde o planejamento inicial do projeto (heurística/estatística
no MVP, Prophet ou modelo mais sofisticado como evolução futura quando
houver volume de dados de produção). Ver README para essa nota.

Enquanto o histórico for pequeno (`MINIMO_AMOSTRAS`), a função
deliberadamente NÃO estima nada — é mais honesto não mostrar previsão do
que mostrar uma média calculada sobre 1 ou 2 entregas, que não significa
nada estatisticamente.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido import PedidoStatusHistorico

MINIMO_AMOSTRAS = 3


async def _historico_transito_para_entregue(db: AsyncSession) -> list[float]:
    """
    Duração (em horas) entre EM_TRANSITO e ENTREGUE de cada pedido que já
    completou esse ciclo — a amostra histórica usada para estimar o prazo
    de pedidos novos.
    """
    result = await db.execute(
        select(
            PedidoStatusHistorico.order_id,
            PedidoStatusHistorico.status,
            PedidoStatusHistorico.criado_em,
        )
        .where(PedidoStatusHistorico.status.in_(["EM_TRANSITO", "ENTREGUE"]))
        .order_by(PedidoStatusHistorico.order_id, PedidoStatusHistorico.criado_em)
    )

    por_pedido: dict[int, dict[str, datetime]] = defaultdict(dict)
    for pedido_id, status, criado_em in result.all():
        # Mantém a primeira ocorrência de cada status por pedido (por
        # segurança, caso algum dia haja mais de uma transição igual).
        por_pedido[pedido_id].setdefault(status, criado_em)

    duracoes_horas = []
    for marcos in por_pedido.values():
        inicio = marcos.get("EM_TRANSITO")
        fim = marcos.get("ENTREGUE")
        if inicio and fim and fim > inicio:
            duracoes_horas.append((fim - inicio).total_seconds() / 3600)

    return duracoes_horas


async def estimar_prazo_entrega(
    db: AsyncSession, momento_coleta: datetime
) -> tuple[datetime | None, int]:
    """
    Estima a data/hora de entrega somando ao momento da coleta a média
    histórica real de duração do trajeto (EM_TRANSITO -> ENTREGUE).

    Retorna (data_estimada, quantidade_de_entregas_na_amostra). Se ainda
    não houver histórico suficiente (`MINIMO_AMOSTRAS`), retorna
    (None, quantidade_encontrada) — o chamador decide como lidar com a
    ausência de estimativa.
    """
    duracoes = await _historico_transito_para_entregue(db)
    if len(duracoes) < MINIMO_AMOSTRAS:
        return None, len(duracoes)

    media_horas = sum(duracoes) / len(duracoes)
    return momento_coleta + timedelta(hours=media_horas), len(duracoes)
