"""Rede de segurança da apresentação: avança um pedido esquecido.

Não é um simulador de pipeline. Ele existe para o caso de o apresentador ficar
preso numa tela — e por isso é DESLIGADO por padrão, tem prazo longo, e perde
para qualquer ação manual.

Escreve pela MESMA função de transição que as rotas usam
(`app/routers/separacao.py::transicionar_pedido`), nunca por UPDATE direto:
validação de transição, carimbo de `status_updated_at`, linha de histórico e
evento acontecem de um jeito só, e não de dois.
"""

import uuid
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido import Order
from app.routers.separacao import transicionar_pedido
from app.services.status_pedido import StatusPedido

# O passo seguinte de cada estado que pode ser avançado sozinho.
#
# `AGUARDANDO_SUBSTITUICAO` está FORA de propósito: é o único estado que espera
# uma decisão do aluno, e essa decisão é o que a apresentação está mostrando.
# `SEPARADO` também está fora: `finalizar_separacao` já encadeia
# SEPARADO -> AGUARDANDO_COLETA na mesma chamada, então um pedido nunca
# repousa nele em operação normal.
PROXIMO_ESTADO: dict[StatusPedido, StatusPedido] = {
    StatusPedido.CRIADO: StatusPedido.CONFIRMADO,
    StatusPedido.CONFIRMADO: StatusPedido.AGUARDANDO_SEPARACAO,
    StatusPedido.AGUARDANDO_SEPARACAO: StatusPedido.EM_SEPARACAO,
    StatusPedido.EM_SEPARACAO: StatusPedido.SEPARADO,
    StatusPedido.AGUARDANDO_COLETA: StatusPedido.EM_TRANSITO,
    StatusPedido.EM_TRANSITO: StatusPedido.ENTREGUE,
}

OBSERVACAO = "Avanço automático (rede de segurança da apresentação)"


async def avancar_parados(
    db: AsyncSession, agora: datetime, prazo_segundos: int
) -> list[uuid.UUID]:
    """Avança quem está no mesmo estado há mais que `prazo_segundos`.
    `prazo_segundos <= 0` não avança nada."""
    if prazo_segundos <= 0:
        return []

    limite = agora - timedelta(seconds=prazo_segundos)
    pedidos = (
        (
            await db.execute(
                select(Order).where(
                    Order.status.in_([e.value for e in PROXIMO_ESTADO]),
                    Order.status_updated_at < limite,
                )
            )
        )
        .scalars()
        .all()
    )

    avancados: list[uuid.UUID] = []
    for pedido in pedidos:
        destino = PROXIMO_ESTADO[StatusPedido(pedido.status)]
        await transicionar_pedido(db, pedido.id, destino.value, None, observacao=OBSERVACAO)
        avancados.append(pedido.id)
        logger.info("avanco_automatico: pedido {} avançou para {}", pedido.id, destino.value)
    return avancados
