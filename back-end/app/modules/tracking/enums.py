from enum import StrEnum


class OrderStatus(StrEnum):
    """Lifecycle of a delivery as shown on the tracking screen."""

    PLACED = "placed"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class TrafficLevel(StrEnum):
    """Estimated congestion on the courier's route."""

    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


class RouteStatus(StrEnum):
    """Where the courier is relative to the destination."""

    EN_ROUTE = "en_route"
    NEARBY = "nearby"
    ARRIVED = "arrived"
