import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.events.publisher import publish_event
from app.models.pedido import Order, OrderItem, PedidoStatusHistorico
from app.schemas.pedido import (
    PedidoCreateIn,
    PedidoOut,
    PedidoStatusHistoricoOut,
    PrevisaoEntregaOut,
)
from app.services.previsao_entrega import MINIMO_AMOSTRAS, estimar_prazo_entrega
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=PedidoOut, status_code=201)
async def criar_pedido(
    payload: PedidoCreateIn,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if not payload.itens:
        raise HTTPException(400, "O pedido precisa ter ao menos um item")

    valor_total = sum(item.unit_price * item.quantity for item in payload.itens)

    pedido = Order(
        user_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        endereco_entrega=payload.endereco_entrega,
        total=valor_total,
    )
    db.add(pedido)
    await db.flush()  # gera pedido.id sem commitar ainda

    for item in payload.itens:
        db.add(
            OrderItem(
                order_id=pedido.id,
                product_id=item.product_id,
                supplier_id=item.supplier_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
        )

    db.add(PedidoStatusHistorico(order_id=pedido.id, status=StatusPedido.CRIADO.value))
    await db.commit()
    await db.refresh(pedido)

    # `str(pedido.id)`: `orders.id` é UUID desde a fase 2 e JSON não tem tipo
    # UUID — o transporte (`edu_common/events.py`, `json.dumps(payload)`)
    # estoura `TypeError` com o valor cru. As CHAVES continuam em português:
    # renomeá-las dessincronizaria produtor e consumidor sem nenhum cliente
    # pedindo. Só o tipo do valor muda.
    await publish_event(
        "order.created",
        {
            "pedido_id": str(pedido.id),
            "aluno_id": str(aluno_id),
            "valor_total": float(valor_total),
        },
    )

    return pedido


@router.get("/mine", response_model=list[PedidoOut])
async def meus_pedidos(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .where(Order.user_id == aluno_id)
        .order_by(Order.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/{pedido_id}", response_model=PedidoOut)
async def detalhe_pedido(
    pedido_id: uuid.UUID,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == pedido_id, Order.user_id == aluno_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    return pedido


@router.get("/{pedido_id}/tracking", response_model=list[PedidoStatusHistoricoOut])
async def rastreio_pedido(
    pedido_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Garante que o pedido pertence ao aluno autenticado antes de expor o histórico
    result = await db.execute(select(Order).where(Order.id == pedido_id, Order.user_id == aluno_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Pedido não encontrado")

    historico = await db.execute(
        select(PedidoStatusHistorico)
        .where(PedidoStatusHistorico.order_id == pedido_id)
        .order_by(PedidoStatusHistorico.criado_em.asc())
        .limit(limit)
        .offset(offset)
    )
    return historico.scalars().all()


@router.get("/{pedido_id}/delivery-estimate", response_model=PrevisaoEntregaOut)
async def previsao_entrega_pedido(
    pedido_id: uuid.UUID,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Estimativa de prazo de entrega — se o pedido já tem uma data definida
    (seja pela previsão automática ao confirmar coleta, seja por uma
    ocorrência de atraso que o aluno aceitou), retorna ela diretamente.
    Caso contrário, calcula uma estimativa "a partir de agora" com base
    no histórico real de entregas — transparente sobre quantas entregas
    embasam o número (`amostras_historicas`) e se é confiável o
    suficiente (`confiavel`, false com poucas amostras).
    """
    result = await db.execute(select(Order).where(Order.id == pedido_id, Order.user_id == aluno_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if pedido.estimated_delivery_at is not None:
        # Já existe uma data definida (previsão automática anterior ou
        # aceite de nova data via ocorrência) — não recalcula por cima.
        _estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
        return PrevisaoEntregaOut(
            data_estimada=pedido.estimated_delivery_at,
            amostras_historicas=amostras,
            confiavel=amostras >= MINIMO_AMOSTRAS,
        )

    estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
    return PrevisaoEntregaOut(
        data_estimada=estimativa,
        amostras_historicas=amostras,
        confiavel=amostras >= MINIMO_AMOSTRAS,
    )
