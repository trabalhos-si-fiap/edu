from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.events.publisher import publish_event
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Pedido, PedidoStatusHistorico
from app.schemas.pedido import PedidoFilaOut, PedidoOut
from app.services.priorizacao_fila import priorizar_fila
from app.services.status_pedido import StatusPedido, validar_transicao

router = APIRouter(prefix="/separacao", tags=["separacao"])


async def transicionar_pedido(
    db: AsyncSession,
    pedido_id: int,
    novo_status: str,
    user_id: str | None,
    observacao: str | None = None,
) -> Pedido:
    """
    Função central de transição de estado do pedido — reutilizada pelos
    routers de separação, entrega e admin, para garantir que toda mudança
    de status passe pela mesma validação e publique o mesmo evento.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if not validar_transicao(pedido.status, novo_status):
        raise HTTPException(400, f"Transição inválida: {pedido.status} → {novo_status}")

    pedido.status = novo_status
    db.add(
        PedidoStatusHistorico(
            pedido_id=pedido.id,
            status=novo_status,
            user_id=user_id,
            observacao=observacao,
        )
    )
    await db.commit()
    await db.refresh(pedido)

    await publish_event(
        "order.status_changed",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(pedido.aluno_id),
            "status": novo_status,
        },
    )
    return pedido


@router.get("/fila", response_model=list[PedidoFilaOut])
async def fila_separacao(
    user: dict = Depends(requer_papel("separador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Fila ordenada por risco (não FIFO) — prioriza pedidos que já esperam
    há mais tempo E pedidos com itens em risco de faltar no estoque, para
    separar esses antes que a falta vire uma ocorrência de verdade. Ver
    services/priorizacao_fila.py para o desenho do score.
    """
    result = await db.execute(
        select(Pedido).where(Pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value)
    )
    pedidos = result.scalars().all()

    pedidos_pontuados = await priorizar_fila(db, list(pedidos))

    return [
        PedidoFilaOut(**PedidoOut.model_validate(pedido).model_dump(), score_risco=score)
        for pedido, score in pedidos_pontuados
    ]


@router.patch("/{pedido_id}/iniciar", response_model=PedidoOut)
async def iniciar_separacao(
    pedido_id: int,
    user: dict = Depends(requer_papel("separador")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    pedido.separador_id = user["sub"]
    await db.flush()

    return await transicionar_pedido(db, pedido_id, StatusPedido.EM_SEPARACAO.value, user["sub"])


@router.patch("/{pedido_id}/finalizar", response_model=PedidoOut)
async def finalizar_separacao(
    pedido_id: int,
    user: dict = Depends(requer_papel("separador")),
    db: AsyncSession = Depends(get_db),
):
    ocorrencia_result = await db.execute(
        select(Ocorrencia).where(Ocorrencia.pedido_id == pedido_id, Ocorrencia.status == "ABERTA")
    )
    if ocorrencia_result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Existe uma ocorrência aberta aguardando decisão do aluno. "
            "Aguarde a resolução antes de finalizar a separação.",
        )

    await transicionar_pedido(db, pedido_id, StatusPedido.SEPARADO.value, user["sub"])
    # Encadeia automaticamente para "aguardando coleta" — pronto para o entregador
    return await transicionar_pedido(
        db, pedido_id, StatusPedido.AGUARDANDO_COLETA.value, user["sub"]
    )
