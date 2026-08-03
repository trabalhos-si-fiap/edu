"""Local route-prediction service.

This module is a stand-in for a real routing provider (Google Maps Directions,
OSRM, …). Until that integration lands, the ETA is estimated from the
great-circle (Haversine) distance between the courier and the destination,
corrected by an *urban-route factor* that approximates the extra distance of
real streets, turns and detours, and by a traffic penalty applied to the
average speed.

All functions here are pure and deterministic — given the same inputs they
return the same output — which keeps them trivially unit-testable. The traffic
level is derived from the distance (the longer the route, the more congestion a
courier tends to cross); swapping this for a live feed later only changes
``estimate_traffic`` without touching the rest of the pipeline.
"""

import math
from dataclasses import dataclass

from app.modules.tracking.enums import RouteStatus, TrafficLevel

_EARTH_RADIUS_KM = 6371.0088

# Distance bands (in route km) used to classify congestion.
_LIGHT_TRAFFIC_MAX_KM = 2.0
_MODERATE_TRAFFIC_MAX_KM = 7.0

# Fraction of the average speed actually achievable under each traffic level.
_TRAFFIC_SPEED_FACTOR: dict[TrafficLevel, float] = {
    TrafficLevel.LIGHT: 1.0,
    TrafficLevel.MODERATE: 0.8,
    TrafficLevel.HEAVY: 0.6,
}

# Proximity thresholds (in straight-line km) for the courier→destination state.
_ARRIVED_MAX_KM = 0.05
_NEARBY_MAX_KM = 0.5


@dataclass(frozen=True)
class RoutePrediction:
    """Outcome of a route estimation, in plain domain types."""

    straight_line_distance_km: float
    distance_km: float
    eta_minutes: int
    eta_text: str
    effective_speed_kmh: float
    traffic_level: TrafficLevel
    route_status: RouteStatus


def haversine_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    """Great-circle distance between two ``(lat, lng)`` points, in kilometres.

    Uses the Haversine formula on a spherical-Earth approximation, which is
    accurate to well within the error introduced by the urban-route factor.
    """
    lat1, lng1 = origin
    lat2, lng2 = destination

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


def estimate_traffic(distance_km: float) -> TrafficLevel:
    """Classify congestion from the route distance.

    A short hop is usually light; longer routes cross more avenues and
    intersections, so they are progressively heavier.
    """
    if distance_km <= _LIGHT_TRAFFIC_MAX_KM:
        return TrafficLevel.LIGHT
    if distance_km <= _MODERATE_TRAFFIC_MAX_KM:
        return TrafficLevel.MODERATE
    return TrafficLevel.HEAVY


def estimate_route_status(straight_line_distance_km: float) -> RouteStatus:
    """Map the courier's proximity to a coarse route state."""
    if straight_line_distance_km <= _ARRIVED_MAX_KM:
        return RouteStatus.ARRIVED
    if straight_line_distance_km <= _NEARBY_MAX_KM:
        return RouteStatus.NEARBY
    return RouteStatus.EN_ROUTE


def format_eta(minutes: int) -> str:
    """Render a minute count as a human-friendly string (pt-BR)."""
    if minutes <= 0:
        return "chegando"
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"{hours} h"
    return f"{hours} h {rest} min"


def predict_route(
    courier: tuple[float, float],
    destination: tuple[float, float],
    *,
    average_speed_kmh: float,
    urban_route_factor: float,
) -> RoutePrediction:
    """Estimate distance and ETA for a courier heading to a destination.

    Steps:
        1. Straight-line (Haversine) distance courier→destination.
        2. Real route distance = straight line * ``urban_route_factor``.
        3. Traffic level derived from the route distance.
        4. Effective speed = ``average_speed_kmh`` * traffic penalty.
        5. ETA = route distance / effective speed.
    """
    if average_speed_kmh <= 0:
        raise ValueError("average_speed_kmh must be positive")
    if urban_route_factor < 1:
        raise ValueError("urban_route_factor must be >= 1")

    straight_line = haversine_km(courier, destination)
    route_distance = straight_line * urban_route_factor

    traffic = estimate_traffic(route_distance)
    effective_speed = average_speed_kmh * _TRAFFIC_SPEED_FACTOR[traffic]

    eta_minutes = math.ceil(route_distance / effective_speed * 60)
    route_status = estimate_route_status(straight_line)
    if route_status is RouteStatus.ARRIVED:
        eta_minutes = 0

    return RoutePrediction(
        straight_line_distance_km=round(straight_line, 3),
        distance_km=round(route_distance, 3),
        eta_minutes=eta_minutes,
        eta_text=format_eta(eta_minutes),
        effective_speed_kmh=round(effective_speed, 2),
        traffic_level=traffic,
        route_status=route_status,
    )
