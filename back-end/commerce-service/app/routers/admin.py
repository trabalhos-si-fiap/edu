from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.models.pedido import Pedido
from app.models.produto import Estoque
from app.routers.separacao import transicionar_pedido
from app.schemas.estoque import EstoqueOut
from app.schemas.pedido import PedidoStaffOut
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/orders", response_model=list[PedidoStaffOut])
async def listar_pedidos(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Pedido)
    if status:
        query = query.where(Pedido.status == status)
    query = query.order_by(Pedido.id).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/orders/{pedido_id}/confirm-payment", response_model=PedidoStaffOut)
async def confirmar_pagamento(
    pedido_id: int,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Transição CRIADO -> AGUARDANDO_SEPARACAO, feita pelo admin após confirmar o pagamento."""
    return await transicionar_pedido(
        db, pedido_id, StatusPedido.AGUARDANDO_SEPARACAO.value, user["sub"]
    )


@router.patch("/orders/{pedido_id}/assign-picker", response_model=PedidoStaffOut)
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


@router.patch("/orders/{pedido_id}/assign-deliverer", response_model=PedidoStaffOut)
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


@router.get("/inventory", response_model=list[EstoqueOut])
async def listar_estoque(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    `response_model` adicionado além do escopo original do brief — a rota
    devolvia o objeto ORM `Estoque` cru (sem schema nenhum), violando a
    regra "nenhum endpoint devolve objeto ORM cru". Ver
    app/schemas/estoque.py para o porquê.
    """
    result = await db.execute(select(Estoque).order_by(Estoque.id).limit(limit).offset(offset))
    return result.scalars().all()


@router.patch("/inventory/{estoque_id}/adjust", response_model=EstoqueOut)
async def ajustar_estoque(
    estoque_id: int,
    # `ge=0`: sem piso, um admin gravava estoque negativo e a separação
    # passava a trabalhar contra um número que não existe no mundo físico.
    quantidade: int = Query(ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    # `with_for_update()`: o ajuste é um read→write sobre recurso compartilhado
    # (regra 3 do CLAUDE.md) — serializa dois ajustes concorrentes na mesma
    # linha em vez de deixá-los correr em paralelo contra o mesmo SELECT.
    # Não muda QUEM vence: esta rota grava um valor absoluto, não um delta,
    # então o último commit sempre define o valor final, com ou sem lock —
    # medido em task-11-report.md, não é apenas suposição.
    result = await db.execute(select(Estoque).where(Estoque.id == estoque_id).with_for_update())
    estoque = result.scalar_one_or_none()
    if not estoque:
        raise HTTPException(404, "Registro de estoque não encontrado")
    estoque.quantidade = quantidade
    await db.commit()
    await db.refresh(estoque)
    return estoque
