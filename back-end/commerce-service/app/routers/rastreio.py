"""Rota do rastreio de pedido — o objeto que a tela de rastreio do app
realmente renderiza.

Separada de `app/routers/pedidos.py` de propósito: o path
`/orders/{id}/tracking` já existia (task C6, devolvendo o histórico de
status) e esta task (C8) troca o que ele devolve, então o handler novo fica
num módulo próprio em vez de ser mais uma rota emendada em `pedidos.py`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import OrderNotFoundError
from app.schemas.rastreio import OrderTrackingOut
from app.services import pedidos as services
from app.services.rastreio_builder import build_order_tracking

router = APIRouter(prefix="/orders", tags=["tracking"])


@router.get("/{order_id}/tracking", response_model=OrderTrackingOut)
async def rastreio_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderTrackingOut:
    """Tudo que a tela de rastreio precisa renderizar.

    Esta rota ANTES devolvia o histórico de status (task C6, que a manteve
    de propósito para não quebrar a tela do Flutter entre duas tasks — ver
    o docstring de `historico_status` em `app/routers/pedidos.py`). O app
    espera o objeto da tela, então a réplica exata fica com a rota e o
    histórico se mudou para `GET /orders/{id}/status-history` — task C8.
    """
    try:
        order = await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    # Log de auditoria: achado 4 da revisão da task C8 — o legacy
    # (app/modules/tracking/services.py::get_order_tracking) emite este
    # log e o porte tinha deixado a linha cair sem nenhuma nota.
    logger.info(
        "tracking: rastreio solicitado order={} user={} status={}",
        order_id,
        user["sub"],
        order.status,
    )
    return build_order_tracking(order)
