from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.models.pedido import Pedido
from app.routers.separacao import transicionar_pedido
from app.schemas.pedido import PedidoOut
from app.services.previsao_entrega import estimar_prazo_entrega
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/queue", response_model=list[PedidoOut])
async def fila_entrega(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("entregador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Pedido)
        .where(Pedido.status == StatusPedido.AGUARDANDO_COLETA.value)
        .order_by(Pedido.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/mine", response_model=list[PedidoOut])
async def minhas_entregas(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.entregador_id == user["sub"],
            Pedido.status == StatusPedido.EM_TRANSITO.value,
        )
        .order_by(Pedido.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.patch("/{pedido_id}/collect", response_model=PedidoOut)
async def confirmar_coleta(
    pedido_id: int,
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
    """
    Claim-on-first-action, DE PROPÓSITO — decisão deliberada, não uma
    lacuna: esta rota é o próprio ato de reivindicar o pedido para entrega,
    não uma ação sobre um pedido já reivindicado. Não há "dono anterior"
    para checar aqui, ao contrário de `confirmar_entrega` logo abaixo (gap
    #2 do sweep), onde o pedido JÁ tem um `entregador_id` definido por esta
    mesma rota e a posse precisa ser validada antes de deixar concluir a
    entrega.

    A proteção contra reivindicação dupla não é um `if`, é a máquina de
    estados: só AGUARDANDO_COLETA -> EM_TRANSITO é uma transição válida
    (services/status_pedido.py). Um segundo entregador que tente coletar o
    mesmo pedido encontra `pedido.status` já em EM_TRANSITO e
    `transicionar_pedido` rejeita com 400 antes de sobrescrever o
    `entregador_id` do primeiro — a ordem das linhas abaixo (atribui
    `entregador_id` ANTES de chamar `transicionar_pedido`) é inofensiva
    porque, se a transição for rejeitada, a sessão nunca commita: `db.flush()`
    só empurra a mudança para a transação aberta, `transicionar_pedido` é
    quem chama `db.commit()` — se ele levantar 400, o `entregador_id`
    sobrescrito nunca persiste.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    pedido.entregador_id = user["sub"]
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
    if pedido_atualizado.data_prevista_entrega is None:
        try:
            estimativa, _amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
            if estimativa is not None:
                pedido_atualizado.data_prevista_entrega = estimativa
                await db.commit()
                await db.refresh(pedido_atualizado)
        except Exception:
            # Sem histórico suficiente ainda ou falha pontual — segue sem
            # estimativa. Nunca pode impedir a confirmação de coleta, que já
            # foi concluída acima; só registra para investigação posterior.
            logger.warning("Falha ao estimar prazo de entrega para o pedido {}", pedido_id)

    return pedido_atualizado


@router.patch("/{pedido_id}/deliver", response_model=PedidoOut)
async def confirmar_entrega(
    pedido_id: int,
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
    """
    Fix do gap de autorização #2 do sweep de segurança: a rota original
    checava só o papel ("entregador"), nunca se o chamador era o
    `entregador_id` do pedido — qualquer entregador podia marcar QUALQUER
    pedido como entregue. Diferente de `confirmar_coleta`, aqui o pedido
    já tem dono (`entregador_id` foi definido na coleta), então a posse
    PRECISA ser checada antes de deixar concluir a entrega.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if str(pedido.entregador_id) != user["sub"]:
        raise HTTPException(
            403, "Apenas o entregador responsável por este pedido pode confirmar a entrega"
        )

    return await transicionar_pedido(db, pedido_id, StatusPedido.ENTREGUE.value, user["sub"])
