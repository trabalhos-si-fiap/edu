"""Cliente da Google Directions API para o mapa da rota do pedido.

Fronteira HTTP pura: dada uma origem `(lat, lng)` e um endereço de destino em
texto, mais uma chave de API, devolve a polyline codificada, distância,
duração e as coordenadas geocodificadas do destino (o `end_location` final
da rota). Qualquer falha em obter uma rota utilizável — erro de transporte,
timeout, status da API diferente de OK, ou lista de rotas vazia — vira
:class:`RouteUnavailableError`, para quem chama tratar um único tipo de erro.

A chave de API entra pelo chamador (lida de settings, nunca hardcoded —
regra de segurança #5) e nunca é logada.

Porte de `legacy/app/modules/tracking/directions.py` (task C9). Sem mudança
de lógica: só o import de `RouteUnavailable` -> `RouteUnavailableError`,
agora em `app.exceptions`.
"""

import math
from dataclasses import dataclass

import httpx
from loguru import logger

from app.exceptions import RouteUnavailableError

_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class DirectionsResult:
    """Resultado da busca de rota, já interpretado e agnóstico de provedor."""

    polyline: str
    distance_text: str
    distance_km: float
    duration_text: str
    duration_minutes: int
    destination_latitude: float
    destination_longitude: float


def _format_point(point: tuple[float, float]) -> str:
    lat, lng = point
    return f"{lat},{lng}"


async def fetch_directions(
    client: httpx.AsyncClient,
    *,
    origin: tuple[float, float],
    destination: str,
    api_key: str,
) -> DirectionsResult:
    """Busca a rota de carro `origin` -> `destination` na Google.

    Levanta :class:`RouteUnavailableError` para qualquer falha em produzir
    uma rota.
    """
    params = {
        "origin": _format_point(origin),
        "destination": destination,
        "mode": "driving",
        "key": api_key,
    }

    try:
        response = await client.get(_DIRECTIONS_URL, params=params, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:  # ValueError cobre JSON inválido
        logger.warning("tracking: directions request failed: {}", type(exc).__name__)
        raise RouteUnavailableError("directions request failed") from exc

    status = body.get("status")
    routes = body.get("routes") or []
    if status != "OK" or not routes:
        logger.warning("tracking: directions returned status={} routes={}", status, len(routes))
        raise RouteUnavailableError(f"directions status: {status}")

    route = routes[0]
    legs = route.get("legs") or []
    distance_meters = sum(leg.get("distance", {}).get("value", 0) for leg in legs)
    duration_seconds = sum(leg.get("duration", {}).get("value", 0) for leg in legs)
    first_leg = legs[0] if legs else {}

    last_leg = legs[-1] if legs else {}
    end_location = last_leg.get("end_location") or {}
    if "lat" not in end_location or "lng" not in end_location:
        # Sem ponto geocodificado do destino — não dá para posicionar o pino;
        # falha rápido em vez de cair em (0, 0).
        logger.warning("tracking: directions OK response missing end_location")
        raise RouteUnavailableError("directions response missing end_location")

    return DirectionsResult(
        polyline=route["overview_polyline"]["points"],
        distance_text=first_leg.get("distance", {}).get("text", ""),
        distance_km=distance_meters / 1000,
        duration_text=first_leg.get("duration", {}).get("text", ""),
        duration_minutes=math.ceil(duration_seconds / 60),
        destination_latitude=float(end_location.get("lat", 0.0)),
        destination_longitude=float(end_location.get("lng", 0.0)),
    )
