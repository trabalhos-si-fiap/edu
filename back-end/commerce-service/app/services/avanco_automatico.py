"""Rede de segurança da apresentação: avança um pedido esquecido.

Não é um simulador de pipeline. Ele existe para o caso de o apresentador ficar
preso numa tela — e por isso é DESLIGADO por padrão, tem prazo longo, e perde
para qualquer ação manual.

Escreve pela MESMA função de transição que as rotas usam
(`app/routers/separacao.py::transicionar_pedido`), nunca por UPDATE direto:
validação de transição, carimbo de `status_updated_at`, linha de histórico e
evento acontecem de um jeito só, e não de dois.

O salto AGUARDANDO_COLETA -> EM_TRANSITO é o único com efeito extra: ele
substitui `PATCH /delivery/{id}/collect`, então congela a coordenada de
destino como a coleta faz. O que ele NÃO faz é gravar `deliverer_id` — ver o
comentário no laço e `docs/back-end/order-flow.md` §4.
"""

import uuid
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido import Order
from app.routers.separacao import transicionar_pedido
from app.services.posicao import congelar_destino
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
        origem = StatusPedido(pedido.status)
        destino = PROXIMO_ESTADO[origem]
        atualizado = await transicionar_pedido(
            db, pedido.id, destino.value, None, observacao=OBSERVACAO
        )

        if origem is StatusPedido.AGUARDANDO_COLETA:
            # Este salto SUBSTITUI `PATCH /delivery/{id}/collect`, e a coleta
            # faz duas coisas que a transição sozinha não faz. Uma delas
            # cabe aqui: congelar a coordenada de destino. Sem ela o pedido
            # entra em EM_TRANSITO sem destino, o simulador de posição o
            # filtra fora (`avancar_carregamentos` exige destino congelado) e
            # o mapa do comprador nunca anda para esse pedido.
            #
            # `congelar_destino` nunca levanta, por desenho — não precisa de
            # guard aqui, do mesmo jeito que `confirmar_coleta` não tem um.
            #
            # A outra coisa, `deliverer_id`, NÃO é feita: não há pessoa
            # nenhuma coletando, e inventar um dono seria gravar mentira no
            # histórico. A consequência está escrita em
            # `docs/back-end/order-flow.md` §4.
            await congelar_destino(db, atualizado)

        avancados.append(pedido.id)
        logger.info("avanco_automatico: pedido {} avançou para {}", pedido.id, destino.value)
    return avancados
