"""Rota do rastreio de pedido — o objeto que a tela de rastreio do app
realmente renderiza — e, desde a task C9, a rota no mapa e a previsão de ETA.

Separada de `app/routers/pedidos.py` de propósito: o path
`/orders/{id}/tracking` já existia (task C6, devolvendo o histórico de
status) e a C8 trocou o que ele devolve, então o handler novo ficou num
módulo próprio em vez de ser mais uma rota emendada em `pedidos.py`. A C9
segue o mesmo módulo para `/route` e `/predict-eta`, que também são do
domínio de rastreio.
"""

import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import OrderNotFoundError, RouteUnavailableError
from app.redis_client import get_redis
from app.schemas.rastreio import CourierLocationIn, ETAPredictionOut, OrderTrackingOut, RouteOut
from app.services import pedidos as pedidos_services
from app.services import rastreio as services
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
        order = await pedidos_services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
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


@router.get("/{order_id}/route", response_model=RouteOut)
async def rota_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> RouteOut:
    """Rota de rua do centro de distribuição até o endereço do pedido."""
    try:
        return await services.rota_do_pedido(db, redis, uuid.UUID(user["sub"]), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    except RouteUnavailableError as exc:
        # Provedor fora do ar, sem cota, sem rota, sem endereço ou chave não
        # configurada — 503 limpo, nunca ecoando o detalhe do provedor (que
        # pode conter a chave ou o endereço completo) NEM logando-o. Regra 5
        # do CLAUDE.md: nunca logar dado sensível — o texto de erro do
        # Google pode carregar a chave da API ou o endereço completo do
        # aluno. Guardado por
        # `test_route_503_never_logs_the_provider_detail` (Minor 4, rodada
        # de correção 1).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rota indisponível no momento",
        ) from exc


@router.post("/{order_id}/predict-eta", response_model=ETAPredictionOut)
async def prever_eta(
    order_id: uuid.UUID,
    payload: CourierLocationIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ETAPredictionOut:
    """Estimativa do tempo restante dada a posição atual do entregador.

    Diferente do legacy: carrega o pedido antes de calcular, só para checar
    ownership (regra 2 do CLAUDE.md) — divergência deliberada nº 6, decisão
    do usuário de 2026-08-08. Ver `app/services/rastreio.py::prever_eta`.
    """
    try:
        return await services.prever_eta(db, uuid.UUID(user["sub"]), order_id, payload)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
