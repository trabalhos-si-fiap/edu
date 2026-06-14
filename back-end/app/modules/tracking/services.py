"""Delivery-tracking service layer.

Holds the business logic for the tracking screen and the ETA prediction. The
tracking screen reads the **real** order status (the order's forward-only
lifecycle, advanced by the status pipeline); the route/ETA geometry stays
mocked until the addresses integration provides real coordinates.

The tracking payload deliberately mirrors what the Flutter `OrderModel`
consumes, so the app's ``OrderService`` talks to this endpoint directly.
"""

import uuid

import httpx
import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.orders import services as orders_services
from app.modules.orders.exceptions import OrderNotFound
from app.modules.tracking import directions
from app.modules.tracking.builders import build_order_tracking
from app.modules.tracking.exceptions import RouteUnavailable
from app.modules.tracking.routing import predict_route
from app.modules.tracking.schemas import (
    CourierLocationIn,
    ETAPredictionOut,
    GeoPoint,
    OrderTrackingOut,
    RouteOut,
    RoutePoint,
)

# Mocked delivery destination (the customer's home) used by the ETA estimator.
# The tracking screen contract doesn't carry this coordinate, so it lives here
# until the addresses/orders integration provides the real one.
_MOCK_DESTINATION = GeoPoint(latitude=-23.561414, longitude=-46.655881)

# Mocked distribution center (route origin) — Cajamar/SP. Paired with
# _MOCK_DESTINATION until the orders/addresses integration provides real coords.
_MOCK_ORIGIN = GeoPoint(latitude=-23.3558, longitude=-46.8769)
_ORIGIN_LABEL = "Centro de Distribuição"
_DESTINATION_LABEL = "Endereço de entrega"

# Redis key prefix for cached order routes.
_ROUTE_CACHE_PREFIX = "tracking:route:"


async def get_order_tracking(
    session: AsyncSession, user_id: uuid.UUID, order_id: str
) -> OrderTrackingOut:
    """Return the tracking payload for an order owned by ``user_id``.

    Loads the real order (ownership enforced in the query) and derives the
    timeline from its current status. A malformed id or an order that isn't the
    user's both raise :class:`~app.modules.orders.exceptions.OrderNotFound`,
    which the route maps to a 404 (never leaking whether the order exists).
    """
    try:
        parsed_id = uuid.UUID(order_id)
    except ValueError as exc:
        # Not a real order id — treat as not found, don't 500 on bad input.
        raise OrderNotFound() from exc

    order = await orders_services.get_order(session, user_id, parsed_id)
    logger.info(
        "tracking: tracking requested order={} user={} status={}",
        order_id,
        user_id,
        order.status,
    )
    return build_order_tracking(order)


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


async def get_order_route(redis: aioredis.Redis, user_id: object, order_id: str) -> RouteOut:
    """Return the street route from the distribution center to the order address.

    Lazily calls the Google Directions API only on a cache miss; the origin and
    destination are fixed per order, so the resulting route is cached in Redis
    (security/cost: avoids repeated paid Directions calls). Ownership is the
    caller's responsibility; with the current mock every order resolves.
    """
    cache_key = f"{_ROUTE_CACHE_PREFIX}{order_id}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return RouteOut.model_validate_json(cached)

    api_key = settings.GOOGLE_MAPS_API_PLATAFORM
    if not api_key:
        logger.error("tracking: GOOGLE_MAPS_API_PLATAFORM is not configured")
        raise RouteUnavailable("maps api key not configured")

    async with httpx.AsyncClient() as client:
        result = await directions.fetch_directions(
            client,
            origin=(_MOCK_ORIGIN.latitude, _MOCK_ORIGIN.longitude),
            destination=(_MOCK_DESTINATION.latitude, _MOCK_DESTINATION.longitude),
            api_key=api_key,
        )

    route = RouteOut(
        origin=RoutePoint(
            label=_ORIGIN_LABEL,
            latitude=_MOCK_ORIGIN.latitude,
            longitude=_MOCK_ORIGIN.longitude,
        ),
        destination=RoutePoint(
            label=_DESTINATION_LABEL,
            latitude=_MOCK_DESTINATION.latitude,
            longitude=_MOCK_DESTINATION.longitude,
        ),
        polyline=result.polyline,
        distance_text=result.distance_text,
        distance_km=result.distance_km,
        duration_text=result.duration_text,
        duration_minutes=result.duration_minutes,
    )

    await redis.set(
        cache_key,
        route.model_dump_json(),
        ex=settings.TRACKING_ROUTE_CACHE_TTL_SECONDS,
    )
    logger.info("tracking: route computed order={} user={}", order_id, user_id)
    return route
