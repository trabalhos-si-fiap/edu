from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
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
    user: dict = Depends(requer_papel("entregador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .where(Order.status == StatusPedido.AGUARDANDO_COLETA.value)
        .order_by(Order.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/mine", response_model=list[PedidoStaffOut])
async def minhas_entregas(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .where(
            Order.deliverer_id == user["sub"],
            Order.status == StatusPedido.EM_TRANSITO.value,
        )
        .order_by(Order.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.patch("/{pedido_id}/collect", response_model=PedidoStaffOut)
async def confirmar_coleta(
    pedido_id: int,
    user: dict = Depends(requer_papel("entregador")),
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
    """
    result = await db.execute(select(Order).where(Order.id == pedido_id).with_for_update())
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if pedido.deliverer_id is not None and str(pedido.deliverer_id) != user["sub"]:
        raise HTTPException(403, "Este pedido já foi atribuído a outro entregador")

    pedido.deliverer_id = user["sub"]
    await db.flush()

    pedido_atualizado = await transicionar_pedido(
        db, pedido_id, StatusPedido.EM_TRANSITO.value, user["sub"]
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

    return pedido_atualizado


@router.patch("/{pedido_id}/deliver", response_model=PedidoStaffOut)
async def confirmar_entrega(
    pedido_id: int,
    user: dict = Depends(requer_papel("entregador")),
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
    """
    result = await db.execute(select(Order).where(Order.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if str(pedido.deliverer_id) != user["sub"]:
        raise HTTPException(
            403, "Apenas o entregador responsável por este pedido pode confirmar a entrega"
        )

    return await transicionar_pedido(db, pedido_id, StatusPedido.ENTREGUE.value, user["sub"])
