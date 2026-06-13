"""Tests for the tracking service layer (route building + caching)."""

import uuid

import pytest
import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.tracking import directions, services
from app.modules.tracking.directions import DirectionsResult
from app.modules.tracking.exceptions import RouteUnavailable

_ORDER_ID = "ED-99420"

_FAKE_RESULT = DirectionsResult(
    polyline="enc",
    distance_text="32 km",
    distance_km=32.0,
    duration_text="48 min",
    duration_minutes=48,
)


@pytest.fixture(autouse=True)
def _set_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", "test-key")


async def test_get_order_route_builds_payload(
    redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_fetch(client, *, origin, destination, api_key):
        return _FAKE_RESULT

    monkeypatch.setattr(directions, "fetch_directions", fake_fetch)

    route = await services.get_order_route(redis_client, uuid.uuid4(), _ORDER_ID)

    assert route.origin.label == "Centro de Distribuição"
    assert route.destination.label == "Endereço de entrega"
    assert route.polyline == "enc"
    assert route.distance_km == 32.0
    assert route.duration_minutes == 48


async def test_get_order_route_caches_result(
    redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    async def counting_fetch(client, *, origin, destination, api_key):
        calls["n"] += 1
        return _FAKE_RESULT

    monkeypatch.setattr(directions, "fetch_directions", counting_fetch)

    first = await services.get_order_route(redis_client, uuid.uuid4(), _ORDER_ID)
    second = await services.get_order_route(redis_client, uuid.uuid4(), _ORDER_ID)

    assert calls["n"] == 1  # second call served from cache
    assert first.model_dump() == second.model_dump()


async def test_get_order_route_without_key_raises(
    redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", None)

    with pytest.raises(RouteUnavailable):
        await services.get_order_route(redis_client, uuid.uuid4(), _ORDER_ID)
