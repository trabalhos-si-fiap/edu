from enum import StrEnum


class TrackingStepStatus(StrEnum):
    """State of each step in the tracking timeline (matches the Flutter app)."""

    DONE = "done"
    CURRENT = "current"
    PENDING = "pending"


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
