"""SIMULAÇÃO. Não há entregador real nem GPS neste sistema.

Este módulo interpola uma posição entre a origem do carregamento e o destino
do pedido, conforme o tempo desde a entrada em EM_TRANSITO, e a grava pela
MESMA função que uma posição vinda de um aparelho gravaria
(`app/services/posicao.py::registrar_posicao`).

Como trocar por GPS real: acrescente o chamador novo de `registrar_posicao` e
desligue este job no `app/scheduler.py` (task 7). Nada da leitura, do model
ou da tela muda — é por isso que a porta de escrita é separada do simulador.

O relatório de entrega desta spec lista esta simulação como simulação
(`docs/back-end/order-flow.md`, task 15).
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.services.posicao import registrar_posicao
from app.services.status_pedido import StatusPedido

# Quanto tempo o percurso inteiro leva, na simulação. Não é a ETA do rastreio
# (essa vem de `previsao_entrega`/Directions): é o relógio da animação, e ele
# é curto porque a apresentação inteira dura minutos.
DURACAO_PERCURSO = timedelta(minutes=6)


def fracao_percorrida(
    inicio: datetime, agora: datetime, duracao: timedelta = DURACAO_PERCURSO
) -> float:
    """0.0 na largada, 1.0 na chegada, e nunca mais que 1.0 — o entregador não
    passa do endereço."""
    if duracao.total_seconds() <= 0:
        return 1.0
    decorrido = (agora - inicio).total_seconds() / duracao.total_seconds()
    return max(0.0, min(1.0, decorrido))


def interpolar(
    origem: tuple[Decimal, Decimal], destino: tuple[Decimal, Decimal], fracao: float
) -> tuple[Decimal, Decimal]:
    """Interpolação linear, com o resultado quantizado nas 6 casas decimais da
    coluna — gravar mais casas do que a coluna guarda faria a leitura devolver
    um valor diferente do que o cálculo produziu."""
    passo = Decimal(str(fracao))
    lat = origem[0] + (destino[0] - origem[0]) * passo
    lng = origem[1] + (destino[1] - origem[1]) * passo
    casas = Decimal("0.000001")
    return lat.quantize(casas), lng.quantize(casas)


async def avancar_carregamentos(db: AsyncSession, agora: datetime) -> int:
    """Grava uma posição por carregamento com pedido EM_TRANSITO. Devolve
    quantos carregamentos avançaram.

    Por CARREGAMENTO, não por pedido: o lote anda junto, é isso que ele é. O
    destino usado é o do primeiro pedido do lote que tem coordenada congelada
    — com uma parada por lote (roteirização com várias paradas está fora do
    escopo da spec), esse é o destino.
    """
    linhas = (
        await db.execute(
            select(Carregamento, Order)
            .join(Order, Order.carregamento_id == Carregamento.id)
            .where(
                Order.status == StatusPedido.EM_TRANSITO.value,
                Order.destino_lat.is_not(None),
                Carregamento.origem_lat.is_not(None),
            )
            .order_by(Carregamento.id, Order.created_at)
        )
    ).all()

    vistos: set[int] = set()
    avancados = 0
    for carregamento, pedido in linhas:
        if carregamento.id in vistos:
            continue
        vistos.add(carregamento.id)
        fracao = fracao_percorrida(pedido.status_updated_at, agora)
        lat, lng = interpolar(
            (carregamento.origem_lat, carregamento.origem_lng),
            (pedido.destino_lat, pedido.destino_lng),
            fracao,
        )
        await registrar_posicao(db, carregamento.id, lat, lng)
        avancados += 1
    return avancados
