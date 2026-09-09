import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import PAPEL_CARREGAMENTO, AtorEntrega, ator_entrega
from app.models.pedido import Order
from app.routers.separacao import transicionar_pedido
from app.schemas.pedido import PedidoStaffOut
from app.services.previsao_entrega import estimar_prazo_entrega
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/queue", response_model=list[PedidoStaffOut])
async def fila_entrega(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ator: AtorEntrega = Depends(ator_entrega),
    db: AsyncSession = Depends(get_db),
):
    if ator.tipo == PAPEL_CARREGAMENTO:
        # O entregador do lote quer ver o lote inteiro, não a fila global por
        # status — o filtro é o carregamento, não `AGUARDANDO_COLETA`.
        filtro = Order.carregamento_id == ator.carregamento_id
    else:
        filtro = Order.status == StatusPedido.AGUARDANDO_COLETA.value
    result = await db.execute(
        select(Order).where(filtro).order_by(Order.id).limit(limit).offset(offset)
    )
    # `de_order`, não o ORM cru: `endereco_entrega` não é mais atributo do
    # model — precisa ser composto (ver PedidoStaffOut.de_order).
    return [PedidoStaffOut.de_order(pedido) for pedido in result.scalars().all()]


@router.get("/mine", response_model=list[PedidoStaffOut])
async def minhas_entregas(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ator: AtorEntrega = Depends(ator_entrega),
    db: AsyncSession = Depends(get_db),
):
    if ator.tipo == PAPEL_CARREGAMENTO:
        filtro = (
            Order.carregamento_id == ator.carregamento_id,
            Order.status == StatusPedido.EM_TRANSITO.value,
        )
    else:
        filtro = (
            Order.deliverer_id == ator.id,
            Order.status == StatusPedido.EM_TRANSITO.value,
        )
    result = await db.execute(
        select(Order).where(*filtro).order_by(Order.id).limit(limit).offset(offset)
    )
    return [PedidoStaffOut.de_order(pedido) for pedido in result.scalars().all()]


@router.patch("/{pedido_id}/collect", response_model=PedidoStaffOut)
async def confirmar_coleta(
    pedido_id: uuid.UUID,
    ator: AtorEntrega = Depends(ator_entrega),
    db: AsyncSession = Depends(get_db),
):
    """
    Claim-on-first-action, COM uma exceção — corrigido no fix round 1
    (reviewer finding #2): a docstring original argumentava "não há dono
    anterior para checar aqui". Falso: `admin.py`'s `assign-deliverer` pode
    setar `orders.deliverer_id` (`entregador_id` antes da task C2) SEM
    mudar o status do pedido — um admin pode
    atribuir o pedido X ao entregador D1 enquanto ele ainda está em
    SEPARADO. Sem honrar essa atribuição, quando o pedido chegasse em
    AGUARDANDO_COLETA, QUALQUER OUTRO entregador D2 chamando `/collect`
    sobrescreveria `deliverer_id` para si (a transição continua válida do
    ponto de vista da máquina de estados) e sequestraria o pedido de D1
    silenciosamente — e o gap #2 fix em `confirmar_entrega`/`deliver`
    passaria a proteger o sequestrador, não D1. Por isso: se
    `deliverer_id` já está definido E é de outra pessoa, rejeita. Se está
    vazio (ninguém atribuiu) ou já é do próprio chamador (idempotente),
    segue o claim-on-first-action normal.

    A proteção contra DUAS chamadas concorrentes de `/collect` no mesmo
    pedido (não sequencial — corrida de verdade) é o `.with_for_update()`
    abaixo: sem lock, duas transações sob READ COMMITTED podem ler o mesmo
    `deliverer_id`/status, ambas passarem nas checagens acima e ambas
    commitarem — último `commit()` ganha, silenciosamente sobrescrevendo o
    primeiro. CLAUDE.md regra 3 (fix round 1, reviewer finding #3). O
    `.with_for_update()` serializa a segunda transação atrás da primeira:
    ela só lê a linha depois que a primeira commita (ou reverte), e nesse
    ponto vê o `deliverer_id` já preenchido.

    A estimativa de prazo abaixo grava em `orders.estimated_delivery_at`
    (`data_prevista_entrega` antes da task C2).

    Task 5: o mesmo endpoint agora também aceita um token de carregamento.
    `ator.autoriza(pedido)` cobre os dois casos — usuário (regra acima) e
    lote (posse é `carregamento_id`, não `deliverer_id`) — mas as mensagens
    de erro continuam distintas por ator, porque a mensagem de usuário já é
    afirmada por teste.
    """
    result = await db.execute(select(Order).where(Order.id == pedido_id).with_for_update())
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if not ator.autoriza(pedido):
        if ator.tipo == PAPEL_CARREGAMENTO:
            raise HTTPException(403, "Este pedido não pertence a este carregamento")
        raise HTTPException(403, "Este pedido já foi atribuído a outro entregador")

    if ator.tipo == PAPEL_CARREGAMENTO:
        # Não há usuário aqui: a posse do pedido já é o `carregamento_id`
        # (task 4, `atribuir_pedido`), então `deliverer_id` fica nulo — o
        # lote é o dono, não uma pessoa.
        quem_fez = None
    else:
        pedido.deliverer_id = ator.id
        quem_fez = ator.id
    await db.flush()

    pedido_atualizado = await transicionar_pedido(
        db, pedido_id, StatusPedido.EM_TRANSITO.value, quem_fez
    )

    # Estima o prazo de entrega com base na média histórica real de
    # tempo entre coleta e entrega — só preenche se o pedido ainda não
    # tiver uma data definida manualmente (ex: aluno já aceitou uma nova
    # data via resolução de ocorrência de atraso, ver ocorrencias.py).
    # Protegido: falha aqui nunca pode impedir a confirmação de coleta,
    # que já foi concluída na linha acima.
    if pedido_atualizado.estimated_delivery_at is None:
        try:
            estimativa, _amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
            if estimativa is not None:
                pedido_atualizado.estimated_delivery_at = estimativa
                await db.commit()
                await db.refresh(pedido_atualizado)
        except Exception:
            # Sem histórico suficiente ainda ou falha pontual — segue sem
            # estimativa. Nunca pode impedir a confirmação de coleta, que já
            # foi concluída acima; só registra para investigação posterior.
            logger.warning("Falha ao estimar prazo de entrega para o pedido {}", pedido_id)

    return PedidoStaffOut.de_order(pedido_atualizado)


@router.patch("/{pedido_id}/deliver", response_model=PedidoStaffOut)
async def confirmar_entrega(
    pedido_id: uuid.UUID,
    ator: AtorEntrega = Depends(ator_entrega),
    db: AsyncSession = Depends(get_db),
):
    """
    Fix do gap de autorização #2 do sweep de segurança: a rota original
    checava só o papel ("entregador"), nunca se o chamador era o
    `orders.deliverer_id` (`entregador_id` antes da task C2) do pedido —
    qualquer entregador podia marcar QUALQUER
    pedido como entregue. Diferente de `confirmar_coleta`, aqui o pedido
    já tem dono (`deliverer_id` foi definido na coleta), então a posse
    PRECISA ser checada antes de deixar concluir a entrega.

    Task 5: a checagem de posse do usuário continua EXPLÍCITA, além de
    `ator.autoriza(pedido)` — `autoriza` aceita `deliverer_id is None` (o
    caso de claim-on-first-action da coleta), e entregar um pedido sem dono
    não pode passar. Para o ator de lote, a posse É o `carregamento_id`, daí
    a segunda checagem, que `autoriza` já cobre sozinha.
    """
    result = await db.execute(select(Order).where(Order.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if ator.tipo != PAPEL_CARREGAMENTO and str(pedido.deliverer_id) != ator.id:
        raise HTTPException(
            403, "Apenas o entregador responsável por este pedido pode confirmar a entrega"
        )
    if not ator.autoriza(pedido):
        raise HTTPException(403, "Este pedido não pertence a este carregamento")

    pedido_atualizado = await transicionar_pedido(
        db,
        pedido_id,
        StatusPedido.ENTREGUE.value,
        ator.id if ator.tipo != PAPEL_CARREGAMENTO else None,
    )
    return PedidoStaffOut.de_order(pedido_atualizado)
