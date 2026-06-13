"""Delivery-tracking service layer.

Holds the business logic for the tracking screen and the ETA prediction. The
order data is **mocked** here for now (no persistence yet) — when the real
orders/logistics storage is wired in, only the private builders change; the
route layer and the ETA pipeline stay untouched.

The tracking payload deliberately mirrors what the Flutter `OrderModel`
consumes, so flipping the app's ``OrderService(useMock: false)`` switches it
onto this endpoint with no further change.
"""

from datetime import UTC, datetime, timedelta

from loguru import logger

from app.core.config import settings
from app.modules.tracking.enums import TrackingStepStatus
from app.modules.tracking.routing import predict_route
from app.modules.tracking.schemas import (
    CourierLocationIn,
    ETAPredictionOut,
    GeoPoint,
    KitItemOut,
    OrderTrackingOut,
    TrackingLocationOut,
    TrackingStepOut,
)

# Mocked delivery destination (the customer's home) used by the ETA estimator.
# The tracking screen contract doesn't carry this coordinate, so it lives here
# until the addresses/orders integration provides the real one.
_MOCK_DESTINATION = GeoPoint(latitude=-23.561414, longitude=-46.655881)


def _build_mocked_tracking(order_id: str) -> OrderTrackingOut:
    """Return a detailed, deterministic mock of an order's tracking.

    Anchored to "now" so the screen always shows a plausible in-progress
    delivery during development.
    """
    now = datetime.now(UTC)
    return OrderTrackingOut(
        id=order_id,
        headline="Status do Rastreio",
        description=(
            "Seu material didático premium está em rota de entrega para "
            "sua residência."
        ),
        estimated_arrival=now + timedelta(days=4),
        steps=[
            TrackingStepOut(
                code="processed",
                title="Processado",
                status=TrackingStepStatus.DONE,
                timestamp=now - timedelta(days=6),
            ),
            TrackingStepOut(
                code="in_transit",
                title="Em Trânsito",
                status=TrackingStepStatus.CURRENT,
                timestamp=now - timedelta(days=4),
            ),
            TrackingStepOut(
                code="delivered",
                title="Entregue",
                status=TrackingStepStatus.PENDING,
                timestamp=None,
            ),
        ],
        location=TrackingLocationOut(
            name="Centro de Distribuição",
            city="Cajamar",
            state="SP",
            updated_at=now - timedelta(minutes=12),
        ),
        kit=[
            KitItemOut(name="Apostila Ed. 5.0 Vol 2"),
            KitItemOut(name="Caderno Editorial Pro"),
        ],
        carrier="Logistics Intel Express",
        map_url=None,
    )


async def get_order_tracking(user_id: object, order_id: str) -> OrderTrackingOut:
    """Return the full tracking payload for an order owned by ``user_id``.

    Ownership is the caller's responsibility to enforce; with the current mock
    every order is treated as belonging to the requesting user. Once orders are
    persisted, this will query the store filtered by ``user_id`` and raise
    :class:`~app.modules.tracking.exceptions.OrderNotFound` on a miss.
    """
    logger.info("tracking: tracking requested order={} user={}", order_id, user_id)
    return _build_mocked_tracking(order_id)


async def predict_eta(
    user_id: object, order_id: str, courier: CourierLocationIn
) -> ETAPredictionOut:
    """Estimate the remaining delivery time from the courier's current position.

    Delegates the geometry/ETA math to :func:`routing.predict_route` and maps
    the result onto the public response schema.
    """
    destination = _MOCK_DESTINATION

    prediction = predict_route(
        courier=(courier.latitude, courier.longitude),
        destination=(destination.latitude, destination.longitude),
        average_speed_kmh=settings.TRACKING_AVERAGE_SPEED_KMH,
        urban_route_factor=settings.TRACKING_URBAN_ROUTE_FACTOR,
    )

    logger.info(
        "tracking: eta computed order={} user={} distance_km={} eta_min={} traffic={}",
        order_id,
        user_id,
        prediction.distance_km,
        prediction.eta_minutes,
        prediction.traffic_level,
    )

    return ETAPredictionOut(
        eta_minutes=prediction.eta_minutes,
        eta_text=prediction.eta_text,
        distance_km=prediction.distance_km,
        straight_line_distance_km=prediction.straight_line_distance_km,
        average_speed_kmh=prediction.effective_speed_kmh,
        traffic_level=prediction.traffic_level,
        route_status=prediction.route_status,
        courier_location=GeoPoint(latitude=courier.latitude, longitude=courier.longitude),
        destination_location=destination,
    )
