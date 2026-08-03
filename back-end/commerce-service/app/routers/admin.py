from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.models.pedido import Pedido
from app.models.produto import Estoque
from app.routers.separacao import transicionar_pedido
from app.schemas.pedido import PedidoOut
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/pedidos", response_model=list[PedidoOut])
async def listar_pedidos(
    status: str | None = None,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Pedido)
    if status:
        query = query.where(Pedido.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/pedidos/{pedido_id}/confirmar-pagamento", response_model=PedidoOut)
async def confirmar_pagamento(
    pedido_id: int,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Transição CRIADO -> AGUARDANDO_SEPARACAO, feita pelo admin após confirmar o pagamento."""
    return await transicionar_pedido(
        db, pedido_id, StatusPedido.AGUARDANDO_SEPARACAO.value, user["sub"]
    )


@router.patch("/pedidos/{pedido_id}/atribuir-separador", response_model=PedidoOut)
async def atribuir_separador(
    pedido_id: int,
    separador_id: str,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    pedido.separador_id = separador_id
    await db.commit()
    await db.refresh(pedido)
    return pedido


@router.patch("/pedidos/{pedido_id}/atribuir-entregador", response_model=PedidoOut)
async def atribuir_entregador(
    pedido_id: int,
    entregador_id: str,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    pedido.entregador_id = entregador_id
    await db.commit()
    await db.refresh(pedido)
    return pedido


@router.get("/estoque")
async def listar_estoque(
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Estoque))
    return result.scalars().all()


@router.patch("/estoque/{estoque_id}/ajustar")
async def ajustar_estoque(
    estoque_id: int,
    quantidade: int,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Estoque).where(Estoque.id == estoque_id))
    estoque = result.scalar_one_or_none()
    if not estoque:
        raise HTTPException(404, "Registro de estoque não encontrado")
    estoque.quantidade = quantidade
    await db.commit()
    await db.refresh(estoque)
    return estoque
