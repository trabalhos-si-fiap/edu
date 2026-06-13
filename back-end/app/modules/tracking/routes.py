from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.tracking import services
from app.modules.tracking.schemas import (
    CourierLocationIn,
    ETAPredictionOut,
    OrderTrackingOut,
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
) -> OrderTrackingOut:
    """Return every detail needed to render the order-tracking screen."""
    return await services.get_order_tracking(user.id, order_id)


@router.post("/{order_id}/predict-eta", response_model=ETAPredictionOut)
async def predict_eta(
    order_id: OrderId,
    payload: CourierLocationIn,
    user: Annotated[User, Depends(get_current_user)],
) -> ETAPredictionOut:
    """Estimate the remaining delivery time given the courier's current position."""
    return await services.predict_eta(user.id, order_id, payload)
