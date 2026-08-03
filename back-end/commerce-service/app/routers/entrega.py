from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
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

router = APIRouter(prefix="/entrega", tags=["entrega"])


@router.get("/fila", response_model=list[PedidoOut])
async def fila_entrega(
    user: dict = Depends(requer_papel("entregador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Pedido).where(Pedido.status == StatusPedido.AGUARDANDO_COLETA.value)
    )
    return result.scalars().all()


@router.get("/minhas-entregas", response_model=list[PedidoOut])
async def minhas_entregas(
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Pedido).where(
            Pedido.entregador_id == user["sub"],
            Pedido.status == StatusPedido.EM_TRANSITO.value,
        )
    )
    return result.scalars().all()


@router.patch("/{pedido_id}/confirmar-coleta", response_model=PedidoOut)
async def confirmar_coleta(
    pedido_id: int,
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
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


@router.patch("/{pedido_id}/confirmar-entrega", response_model=PedidoOut)
async def confirmar_entrega(
    pedido_id: int,
    user: dict = Depends(requer_papel("entregador")),
    db: AsyncSession = Depends(get_db),
):
    return await transicionar_pedido(db, pedido_id, StatusPedido.ENTREGUE.value, user["sub"])
