from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id
from app.events.publisher import publish_event
from app.models.pedido import Pedido, PedidoItem, PedidoStatusHistorico
from app.schemas.pedido import (
    PedidoCreateIn,
    PedidoOut,
    PedidoStatusHistoricoOut,
    PrevisaoEntregaOut,
)
from app.services.previsao_entrega import MINIMO_AMOSTRAS, estimar_prazo_entrega
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


@router.post("", response_model=PedidoOut, status_code=201)
async def criar_pedido(
    payload: PedidoCreateIn,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    if not payload.itens:
        raise HTTPException(400, "O pedido precisa ter ao menos um item")

    valor_total = sum(item.preco_unitario * item.quantidade for item in payload.itens)

    pedido = Pedido(
        aluno_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        endereco_entrega=payload.endereco_entrega,
        valor_total=valor_total,
    )
    db.add(pedido)
    await db.flush()  # gera pedido.id sem commitar ainda

    for item in payload.itens:
        db.add(
            PedidoItem(
                pedido_id=pedido.id,
                produto_id=item.produto_id,
                fornecedor_id=item.fornecedor_id,
                quantidade=item.quantidade,
                preco_unitario=item.preco_unitario,
            )
        )

    db.add(PedidoStatusHistorico(pedido_id=pedido.id, status=StatusPedido.CRIADO.value))
    await db.commit()
    await db.refresh(pedido)

    await publish_event(
        "order.created",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(aluno_id),
            "valor_total": float(valor_total),
        },
    )

    return pedido


@router.get("/meus", response_model=list[PedidoOut])
async def meus_pedidos(
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.aluno_id == aluno_id))
    return result.scalars().all()


@router.get("/{pedido_id}", response_model=PedidoOut)
async def detalhe_pedido(
    pedido_id: int,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Pedido).where(Pedido.id == pedido_id, Pedido.aluno_id == aluno_id)
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    return pedido


@router.get("/{pedido_id}/rastreio", response_model=list[PedidoStatusHistoricoOut])
async def rastreio_pedido(
    pedido_id: int,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    # Garante que o pedido pertence ao aluno autenticado antes de expor o histórico
    result = await db.execute(
        select(Pedido).where(Pedido.id == pedido_id, Pedido.aluno_id == aluno_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Pedido não encontrado")

    historico = await db.execute(
        select(PedidoStatusHistorico)
        .where(PedidoStatusHistorico.pedido_id == pedido_id)
        .order_by(PedidoStatusHistorico.criado_em.asc())
    )
    return historico.scalars().all()


@router.get("/{pedido_id}/previsao-entrega", response_model=PrevisaoEntregaOut)
async def previsao_entrega_pedido(
    pedido_id: int,
    aluno_id: str = Depends(get_current_student_id),
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
    result = await db.execute(
        select(Pedido).where(Pedido.id == pedido_id, Pedido.aluno_id == aluno_id)
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if pedido.data_prevista_entrega is not None:
        # Já existe uma data definida (previsão automática anterior ou
        # aceite de nova data via ocorrência) — não recalcula por cima.
        _estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
        return PrevisaoEntregaOut(
            data_estimada=pedido.data_prevista_entrega,
            amostras_historicas=amostras,
            confiavel=amostras >= MINIMO_AMOSTRAS,
        )

    estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
    return PrevisaoEntregaOut(
        data_estimada=estimativa,
        amostras_historicas=amostras,
        confiavel=amostras >= MINIMO_AMOSTRAS,
    )
