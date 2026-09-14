"""Rede de segurança da apresentação: avança um pedido esquecido.

Não é um simulador de pipeline. Ele existe para o caso de o apresentador ficar
preso numa tela — e por isso é DESLIGADO no código, e perde para qualquer ação
manual. O `docker-compose.yml` o liga com três minutos por passo.

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

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido import Order
from app.routers.separacao import tem_ocorrencia_aguardando_aluno, transicionar_pedido
from app.services.posicao import congelar_destino
from app.services.status_pedido import StatusPedido

# O passo seguinte de cada estado que pode ser avançado sozinho.
#
# `AGUARDANDO_SUBSTITUICAO` está FORA de propósito: é o único estado que espera
# uma decisão do aluno, e essa decisão é o que a apresentação está mostrando.
PROXIMO_ESTADO: dict[StatusPedido, StatusPedido] = {
    StatusPedido.CRIADO: StatusPedido.CONFIRMADO,
    StatusPedido.CONFIRMADO: StatusPedido.AGUARDANDO_SEPARACAO,
    StatusPedido.AGUARDANDO_SEPARACAO: StatusPedido.EM_SEPARACAO,
    StatusPedido.EM_SEPARACAO: StatusPedido.SEPARADO,
    StatusPedido.SEPARADO: StatusPedido.AGUARDANDO_COLETA,
    StatusPedido.AGUARDANDO_COLETA: StatusPedido.EM_TRANSITO,
    StatusPedido.EM_TRANSITO: StatusPedido.ENTREGUE,
}

# Estados que nenhuma rota manual deixa em repouso: quem entra num deles sai
# dele na MESMA chamada. `confirmar_pagamento_do_pedido` (admin.py) encadeia
# CONFIRMADO -> AGUARDANDO_SEPARACAO; `finalizar_separacao` (separacao.py)
# encadeia SEPARADO -> AGUARDANDO_COLETA. A rede de segurança faz o mesmo no
# mesmo tique, com as mesmas linhas de histórico e os mesmos eventos, na mesma
# ordem.
#
# Antes, SEPARADO ficava fora do mapa ("ninguém repousa nele") enquanto
# EM_SEPARACAO avançava PARA ele — então todo pedido que a rede de segurança
# separava parava em SEPARADO para sempre: fora da fila do entregador (que lê
# AGUARDANDO_COLETA) e fora de qualquer rota manual (`finish` exige
# EM_SEPARACAO). Encadear em vez de só pôr SEPARADO no mapa evita um prazo
# inteiro num estado invisível para os dois perfis; manter SEPARADO no mapa
# ainda resgata quem já ficou preso lá (pelo bug, ou por um encadeamento
# interrompido entre as duas transições).
ESTADOS_DE_PASSAGEM: frozenset[StatusPedido] = frozenset(
    {StatusPedido.CONFIRMADO, StatusPedido.SEPARADO}
)


def saltos_a_partir_de(origem: StatusPedido) -> list[StatusPedido]:
    """Os estados que um tique grava para um pedido parado em `origem`, em
    ordem: o próximo, e mais um enquanto o destino for estado de passagem."""
    destino = PROXIMO_ESTADO[origem]
    caminho = [destino]
    while destino in ESTADOS_DE_PASSAGEM:
        destino = PROXIMO_ESTADO[destino]
        caminho.append(destino)
    return caminho


OBSERVACAO = "Avanço automático (rede de segurança da apresentação)"


async def avancar_parados(
    db: AsyncSession, agora: datetime, prazo_segundos: int
) -> list[uuid.UUID]:
    """Avança quem está no mesmo estado há mais que `prazo_segundos`.
    `prazo_segundos <= 0` não avança nada."""
    if prazo_segundos <= 0:
        return []

    limite = agora - timedelta(seconds=prazo_segundos)
    # COLUNAS, não a entidade `Order` — obrigatório, não estilo. Uma entidade
    # carregada aqui fica no identity map, e o `SELECT ... FOR UPDATE` de
    # `transicionar_pedido` na mesma sessão a devolveria SEM repopular os
    # atributos: a revalidação com lock olharia o status da varredura, e um
    # pedido que foi para AGUARDANDO_SUBSTITUICAO nessa janela ganharia
    # SEPARADO por cima. Mesmo defeito, e mesma correção, de
    # `admin.py::confirmar_pagamento`.
    parados = (
        await db.execute(
            select(Order.id, Order.status).where(
                Order.status.in_([e.value for e in PROXIMO_ESTADO]),
                Order.status_updated_at < limite,
            )
        )
    ).all()

    avancados: list[uuid.UUID] = []
    for pedido_id, status in parados:
        if await _avancar_um(db, pedido_id, StatusPedido(status)):
            avancados.append(pedido_id)
    return avancados


async def _avancar_um(db: AsyncSession, pedido_id: uuid.UUID, origem: StatusPedido) -> bool:
    """Grava os saltos de `origem` (`saltos_a_partir_de`). Devolve se ao menos
    um foi gravado."""
    if origem is StatusPedido.EM_SEPARACAO and await tem_ocorrencia_aguardando_aluno(db, pedido_id):
        # O salto EM_SEPARACAO -> SEPARADO -> AGUARDANDO_COLETA substitui
        # `finalizar_separacao`, e ela recusa terminar com decisão do aluno
        # pendente. Recusar aqui também é o que impede a rede de segurança de
        # mandar para coleta um pedido cujo item o aluno ainda vai trocar.
        logger.info(
            "avanco_automatico: pedido {} segue em separação — ocorrência aberta "
            "aguardando o aluno",
            pedido_id,
        )
        return False
    avancou = False
    for destino in saltos_a_partir_de(origem):
        try:
            atualizado = await transicionar_pedido(
                db, pedido_id, destino.value, None, observacao=OBSERVACAO
            )
        except HTTPException as exc:
            # A varredura de `avancar_parados` é sem lock; `transicionar_pedido`
            # relê a linha COM lock. Um pedido cujo status mudou nessa janela
            # (ação manual, outra transição concorrente) faz o funil
            # autoritativo recusar com 400 — o comportamento certo. O que
            # estava errado era deixar esse 400 escapar do laço: um único
            # pedido em estado inconsistente pulava todos os pedidos ainda não
            # visitados naquele tique. A rede de segurança de um pedido não
            # pode depender do estado de outro.
            #
            # No meio de um encadeamento, o salto já gravado fica. Se a
            # interrupção for outra (broker fora entre os dois saltos — essa
            # levanta e encerra o tique, como encerraria
            # `finalizar_separacao`), o pedido repousa no estado de passagem
            # e o tique seguinte o retoma, porque os estados de passagem
            # continuam no mapa.
            if exc.status_code != 400:
                raise
            logger.warning(
                "avanco_automatico: pedido {} não avançou para {} — o status mudou "
                "entre a varredura e a transição; o tique segue nos demais.",
                pedido_id,
                destino.value,
            )
            return avancou

        if destino is StatusPedido.EM_TRANSITO:
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

        avancou = True
        logger.info("avanco_automatico: pedido {} avançou para {}", pedido_id, destino.value)
    return avancou
