from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.redis_client import get_redis
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.orders.exceptions import OrderNotFound
from app.modules.tracking import services
from app.modules.tracking.exceptions import RouteUnavailable
from app.modules.tracking.schemas import (
    CourierLocationIn,
    ETAPredictionOut,
    OrderTrackingOut,
    RouteOut,
)

# Tracking is a read/derive surface over orders; it owns the tracking detail
# view and the route-prediction endpoint, kept separate from the orders module
# so the logistics concern can be extracted into its own service later.
router = APIRouter(prefix="/orders", tags=["tracking"])

# Order ids are opaque strings (the app uses labels like "ED-99420"), bounded
# to keep the input constrained (security rule #4).
OrderId = Annotated[str, Path(min_length=1, max_length=64)]


@router.get("/{order_id}/tracking", response_model=OrderTrackingOut)
async def get_order_tracking(
    order_id: OrderId,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderTrackingOut:
    """Return every detail needed to render the order-tracking screen."""
    try:
        return await services.get_order_tracking(session, user.id, order_id)
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado"
        ) from exc


@router.post("/{order_id}/predict-eta", response_model=ETAPredictionOut)
async def predict_eta(
    order_id: OrderId,
    payload: CourierLocationIn,
    user: Annotated[User, Depends(get_current_user)],
) -> ETAPredictionOut:
    """Estimate the remaining delivery time given the courier's current position."""
    return await services.predict_eta(user.id, order_id, payload)


@router.get("/{order_id}/route", response_model=RouteOut)
async def get_order_route(
    order_id: OrderId,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> RouteOut:
    """Return the street route from the distribution center to the destination."""
    try:
        return await services.get_order_route(session, redis, user.id, order_id)
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado"
        ) from exc
    except RouteUnavailable as exc:
        # Provider down/over-quota, no route, no address, or key unconfigured —
        # surface a clean 503 instead of a 500 (never echo the provider detail).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rota indisponível no momento",
        ) from exc
