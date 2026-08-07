"""
Priorização da fila de separação por risco, em vez de FIFO simples —
combina tempo de espera (SLA) com risco de falta de estoque nos itens do
pedido, para separar primeiro os pedidos mais urgentes E os que têm maior
chance de virar uma ocorrência de falta de estoque se não forem separados
logo. É gestão PROATIVA de eventos (evitar a ocorrência) em vez de reativa
(só reagir depois que ela acontece, como o restante do módulo de
ocorrências já faz).

IMPORTANTE: isso é uma heurística de pontuação (regra de negócio
ponderada), não um modelo de machine learning treinado — ainda não há
dado histórico suficiente (cancelamentos, ocorrências passadas) para
treinar um classificador de risco de verdade. É o desenho correto para o
estágio atual do produto; evoluir para um modelo treinado (ex: regressão
logística sobre o histórico real) é um passo natural quando houver volume
de produção. Ver README.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido import Pedido, PedidoItem
from app.models.produto import Estoque

LIMIAR_ESTOQUE_BAIXO = 5
PESO_ESPERA = 0.6
PESO_RISCO_ESTOQUE = 0.4
HORAS_ESPERA_MAXIMA_NORMALIZACAO = 48  # espera considerada "máxima" para normalizar o score


async def _estoque_total_por_produto(
    db: AsyncSession, produto_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Soma o estoque de cada produto entre todos os fornecedores."""
    if not produto_ids:
        return {}
    result = await db.execute(
        select(Estoque.produto_id, Estoque.quantidade).where(Estoque.produto_id.in_(produto_ids))
    )
    totais: dict[uuid.UUID, int] = {}
    for produto_id, quantidade in result.all():
        totais[produto_id] = totais.get(produto_id, 0) + quantidade
    return totais


async def priorizar_fila(db: AsyncSession, pedidos: list[Pedido]) -> list[tuple[Pedido, float]]:
    """
    Retorna os pedidos ordenados por score de risco (maior primeiro),
    junto com o score calculado (0.0 a 1.0) — combina tempo de espera na
    fila e risco de falta de estoque nos itens do pedido.
    """
    if not pedidos:
        return []

    pedido_ids = [p.id for p in pedidos]
    itens_result = await db.execute(select(PedidoItem).where(PedidoItem.pedido_id.in_(pedido_ids)))
    itens_por_pedido: dict[int, list[PedidoItem]] = {}
    for item in itens_result.scalars().all():
        itens_por_pedido.setdefault(item.pedido_id, []).append(item)

    todos_produto_ids = [item.produto_id for itens in itens_por_pedido.values() for item in itens]
    estoque_por_produto = await _estoque_total_por_produto(db, todos_produto_ids)

    agora = datetime.now(UTC)
    pontuados = []

    for pedido in pedidos:
        horas_espera = (agora - pedido.criado_em).total_seconds() / 3600
        espera_normalizada = min(horas_espera / HORAS_ESPERA_MAXIMA_NORMALIZACAO, 1.0)

        itens = itens_por_pedido.get(pedido.id, [])
        tem_item_com_estoque_baixo = any(
            estoque_por_produto.get(item.produto_id, 0) <= LIMIAR_ESTOQUE_BAIXO for item in itens
        )
        risco_estoque = 1.0 if tem_item_com_estoque_baixo else 0.0

        score = PESO_ESPERA * espera_normalizada + PESO_RISCO_ESTOQUE * risco_estoque
        pontuados.append((pedido, round(score, 3)))

    pontuados.sort(key=lambda par: par[1], reverse=True)
    return pontuados
