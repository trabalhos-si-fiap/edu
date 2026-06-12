"""Endpoint tests for the delivery-tracking module."""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

_ORDER_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """A client whose requests are authenticated as a fixed in-memory user.

    The tracking data is mocked, so a persisted user is unnecessary — we only
    need ``get_current_user`` to resolve to a valid identity.
    """
    user = User(id=uuid.uuid4(), is_active=True)

    async def _override_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = _override_user
    yield client
    # conftest's `client` fixture clears overrides on teardown.


async def test_get_order_tracking_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/orders/{_ORDER_ID}")
    assert resp.status_code == 401


async def test_predict_eta_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/orders/{_ORDER_ID}/predict-eta",
        json={"latitude": -23.55, "longitude": -46.63},
    )
    assert resp.status_code == 401


async def test_get_order_tracking_returns_full_payload(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(f"/api/orders/{_ORDER_ID}")
    assert resp.status_code == 200

    body = resp.json()
    assert body["order_id"] == _ORDER_ID
    assert body["current_status"] == "out_for_delivery"
    assert body["courier_name"]
    assert len(body["items"]) >= 1
    assert len(body["events"]) >= 1
    # Destination must carry coordinates so the app can draw the route.
    assert "location" in body["destination"]
    assert set(body["destination"]["location"]) == {"latitude", "longitude"}
    assert body["total"] == "138.90"  # 89.90 + 2 * 24.50


async def test_predict_eta_happy_path(auth_client: AsyncClient) -> None:
    # ~2 km from the mocked destination on Av. Paulista.
    resp = await auth_client.post(
        f"/api/orders/{_ORDER_ID}/predict-eta",
        json={"latitude": -23.5750, "longitude": -46.6500},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["eta_minutes"] >= 1
    assert body["eta_text"].endswith("min")
    # Urban-route factor makes the travelled distance longer than the straight line.
    assert body["distance_km"] > body["straight_line_distance_km"]
    assert body["traffic_level"] in {"light", "moderate", "heavy"}
    assert body["route_status"] in {"en_route", "nearby", "arrived"}
    assert body["destination_location"] == {
        "latitude": -23.561414,
        "longitude": -46.655881,
    }


async def test_predict_eta_at_destination_is_arrived(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        f"/api/orders/{_ORDER_ID}/predict-eta",
        json={"latitude": -23.561414, "longitude": -46.655881},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_status"] == "arrived"
    assert body["eta_minutes"] == 0
    assert body["eta_text"] == "chegando"


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": 91.0, "longitude": 0.0},  # latitude out of range
        {"latitude": 0.0, "longitude": 200.0},  # longitude out of range
        {"latitude": 0.0},  # missing longitude
        {"latitude": 0.0, "longitude": 0.0, "extra": 1},  # forbidden extra field
    ],
)
async def test_predict_eta_validates_payload(auth_client: AsyncClient, payload: dict) -> None:
    resp = await auth_client.post(f"/api/orders/{_ORDER_ID}/predict-eta", json=payload)
    assert resp.status_code == 422


async def test_get_order_tracking_rejects_non_uuid(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/orders/not-a-uuid")
    assert resp.status_code == 422
