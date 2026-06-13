"""Google Directions API client for the order-route map.

Pure HTTP boundary: given two ``(lat, lng)`` points and an API key, it returns
the encoded overview polyline plus distance and duration. Any failure to obtain
a usable route — transport error, timeout, non-OK API status, or empty route
list — is surfaced as :class:`RouteUnavailable` so callers handle one error type.

The API key is passed in by the caller (read from settings, never hardcoded —
security rule #5) and is never logged.
"""

import math
from dataclasses import dataclass

import httpx
from loguru import logger

from app.modules.tracking.exceptions import RouteUnavailable

_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class DirectionsResult:
    """Parsed, provider-agnostic outcome of a directions lookup."""

    polyline: str
    distance_text: str
    distance_km: float
    duration_text: str
    duration_minutes: int


def _format_point(point: tuple[float, float]) -> str:
    lat, lng = point
    return f"{lat},{lng}"


async def fetch_directions(
    client: httpx.AsyncClient,
    *,
    origin: tuple[float, float],
    destination: tuple[float, float],
    api_key: str,
) -> DirectionsResult:
    """Fetch the driving route ``origin`` -> ``destination`` from Google.

    Raises :class:`RouteUnavailable` on any failure to produce a route.
    """
    params = {
        "origin": _format_point(origin),
        "destination": _format_point(destination),
        "mode": "driving",
        "key": api_key,
    }

    try:
        response = await client.get(_DIRECTIONS_URL, params=params, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:  # ValueError covers bad JSON
        logger.warning("tracking: directions request failed: {}", type(exc).__name__)
        raise RouteUnavailable("directions request failed") from exc

    status = body.get("status")
    routes = body.get("routes") or []
    if status != "OK" or not routes:
        logger.warning("tracking: directions returned status={} routes={}", status, len(routes))
        raise RouteUnavailable(f"directions status: {status}")

    route = routes[0]
    legs = route.get("legs") or []
    distance_meters = sum(leg.get("distance", {}).get("value", 0) for leg in legs)
    duration_seconds = sum(leg.get("duration", {}).get("value", 0) for leg in legs)
    first_leg = legs[0] if legs else {}

    return DirectionsResult(
        polyline=route["overview_polyline"]["points"],
        distance_text=first_leg.get("distance", {}).get("text", ""),
        distance_km=distance_meters / 1000,
        duration_text=first_leg.get("duration", {}).get("text", ""),
        duration_minutes=math.ceil(duration_seconds / 60),
    )
