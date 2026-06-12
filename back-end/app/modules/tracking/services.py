"""Delivery-tracking service layer.

Holds the business logic for the tracking screen and the ETA prediction. The
order data is **mocked** here for now (no persistence yet) — when the real
orders/logistics storage is wired in, only the private ``_build_mocked_order``
helper needs to change; the route layer and the ETA pipeline stay untouched.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from loguru import logger

from app.core.config import settings
from app.modules.tracking.enums import OrderStatus
from app.modules.tracking.routing import predict_route
from app.modules.tracking.schemas import (
    CourierLocationIn,
    DeliveryAddress,
    ETAPredictionOut,
    GeoPoint,
    OrderTrackingItem,
    OrderTrackingOut,
    TrackingEvent,
)

# Mocked destination — Av. Paulista, São Paulo. Replaced by the order's real
# address once the addresses/orders integration is in place.
_MOCK_DESTINATION = DeliveryAddress(
    label="Casa",
    street="Avenida Paulista",
    number="1578",
    complement="Apto 142",
    district="Bela Vista",
    city="São Paulo",
    state="SP",
    zip_code="01310-200",
    location=GeoPoint(latitude=-23.561414, longitude=-46.655881),
)


def _build_mocked_order(user_id: uuid.UUID, order_id: uuid.UUID) -> OrderTrackingOut:
    """Return a detailed, deterministic mock of a trackable order.

    The timeline is anchored to "now" so the screen always shows a plausible,
    in-progress delivery during development.
    """
    now = datetime.now(UTC)
    placed_at = now - timedelta(minutes=42)

    items = [
        OrderTrackingItem(
            product_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            product_name="Apostila ENEM - Matemática",
            quantity=1,
            unit_price=Decimal("89.90"),
            image_url="https://cdn.estuda.app/products/apostila-mat.png",
        ),
        OrderTrackingItem(
            product_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            product_name="Kit Canetas Marca-Texto (6 cores)",
            quantity=2,
            unit_price=Decimal("24.50"),
            image_url="https://cdn.estuda.app/products/marca-texto.png",
        ),
    ]
    total = sum((item.unit_price * item.quantity for item in items), Decimal("0.00"))

    events = [
        TrackingEvent(
            status=OrderStatus.PLACED,
            description="Pedido recebido e aguardando confirmação de pagamento.",
            occurred_at=placed_at,
        ),
        TrackingEvent(
            status=OrderStatus.CONFIRMED,
            description="Pagamento confirmado.",
            occurred_at=placed_at + timedelta(minutes=3),
        ),
        TrackingEvent(
            status=OrderStatus.PREPARING,
            description="Pedido em separação no centro de distribuição.",
            occurred_at=placed_at + timedelta(minutes=12),
        ),
        TrackingEvent(
            status=OrderStatus.OUT_FOR_DELIVERY,
            description="Pedido saiu para entrega com o entregador.",
            occurred_at=placed_at + timedelta(minutes=30),
        ),
    ]

    return OrderTrackingOut(
        order_id=order_id,
        current_status=OrderStatus.OUT_FOR_DELIVERY,
        total=total,
        courier_name="Carlos Henrique",
        items=items,
        events=events,
        destination=_MOCK_DESTINATION,
        placed_at=placed_at,
        estimated_delivery_at=now + timedelta(minutes=18),
    )


async def get_order_tracking(user_id: uuid.UUID, order_id: uuid.UUID) -> OrderTrackingOut:
    """Return the full tracking payload for an order owned by ``user_id``.

    Ownership is the caller's responsibility to enforce; with the current mock
    every order is treated as belonging to the requesting user. Once orders are
    persisted, this will query the store filtered by ``user_id`` and raise
    :class:`~app.modules.tracking.exceptions.OrderNotFound` on a miss.
    """
    logger.info("tracking: tracking requested order={} user={}", order_id, user_id)
    return _build_mocked_order(user_id, order_id)


async def predict_eta(
    user_id: uuid.UUID, order_id: uuid.UUID, courier: CourierLocationIn
) -> ETAPredictionOut:
    """Estimate the remaining delivery time from the courier's current position.

    Delegates the geometry/ETA math to :func:`routing.predict_route` and maps
    the result onto the public response schema.
    """
    order = _build_mocked_order(user_id, order_id)
    destination = order.destination.location

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
