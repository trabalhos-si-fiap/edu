"""Tests for the Google Directions API client (httpx mocked, no network)."""

import httpx
import pytest

from app.modules.tracking.directions import DirectionsResult, fetch_directions
from app.modules.tracking.exceptions import RouteUnavailable

_ORIGIN = (-23.3558, -46.8769)
_DEST = (-23.561414, -46.655881)

_OK_BODY = {
    "status": "OK",
    "routes": [
        {
            "overview_polyline": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
            "legs": [
                {
                    "distance": {"text": "32,4 km", "value": 32400},
                    "duration": {"text": "48 min", "value": 2880},
                }
            ],
        }
    ],
}


def _client(handler: "callable") -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_directions_parses_ok_response() -> None:
    async with _client(lambda req: httpx.Response(200, json=_OK_BODY)) as client:
        result = await fetch_directions(client, origin=_ORIGIN, destination=_DEST, api_key="k")

    assert isinstance(result, DirectionsResult)
    assert result.polyline == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    assert result.distance_text == "32,4 km"
    assert result.distance_km == pytest.approx(32.4)
    assert result.duration_text == "48 min"
    assert result.duration_minutes == 48  # 2880s -> 48 min


async def test_fetch_directions_sends_origin_destination_and_key() -> None:
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=_OK_BODY)

    async with _client(handler) as client:
        await fetch_directions(client, origin=_ORIGIN, destination=_DEST, api_key="secret-key")

    assert seen["origin"] == "-23.3558,-46.8769"
    assert seen["destination"] == "-23.561414,-46.655881"
    assert seen["key"] == "secret-key"


async def test_fetch_directions_raises_on_non_ok_status() -> None:
    body = {"status": "ZERO_RESULTS", "routes": []}
    async with _client(lambda req: httpx.Response(200, json=body)) as client:
        with pytest.raises(RouteUnavailable):
            await fetch_directions(client, origin=_ORIGIN, destination=_DEST, api_key="k")


async def test_fetch_directions_raises_on_empty_routes() -> None:
    body = {"status": "OK", "routes": []}
    async with _client(lambda req: httpx.Response(200, json=body)) as client:
        with pytest.raises(RouteUnavailable):
            await fetch_directions(client, origin=_ORIGIN, destination=_DEST, api_key="k")


async def test_fetch_directions_raises_on_http_error() -> None:
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=req)

    async with _client(boom) as client:
        with pytest.raises(RouteUnavailable):
            await fetch_directions(client, origin=_ORIGIN, destination=_DEST, api_key="k")
