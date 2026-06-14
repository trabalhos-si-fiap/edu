"""Endpoint tests for the delivery-tracking module."""

import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.modules.auth import services as auth_services
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterIn
from app.modules.orders.models import Order, OrderItem
from app.modules.tracking import directions
from app.modules.tracking.directions import DirectionsResult

# The app uses opaque order labels, not UUIDs.
_ORDER_ID = "ED-99420"


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """A client authenticated as a fixed in-memory user.

    Used by the ETA/route endpoints, which don't query the order store.
    """
    user = User(id=uuid.uuid4(), is_active=True)

    async def _override_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = _override_user
    yield client
    # conftest's `client` fixture clears overrides on teardown.


@pytest.fixture
async def db_user(db_session: AsyncSession) -> User:
    return await auth_services.register(
        db_session,
        RegisterIn(
            name="Maria Silva",
            email="maria@example.com",
            phone="11999998888",
            birth_date=date(1995, 6, 15),
            education_level="Vestibulando",
            password="Secret!1",
        ),
    )


@pytest.fixture
async def tracked_order(db_session: AsyncSession, db_user: User) -> Order:
    """A persisted, in-progress order owned by ``db_user``."""
    order = Order(
        user_id=db_user.id,
        total=Decimal("100.00"),
        payment_method="pix",
        status="separating",
        items=[
            OrderItem(
                product_id=uuid.uuid4(),
                product_name="Apostila Ed. 5.0",
                unit_price=Decimal("100.00"),
                quantity=1,
            )
        ],
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


@pytest.fixture
async def db_auth_client(client: AsyncClient, db_user: User) -> AsyncIterator[AsyncClient]:
    """A client authenticated as the persisted ``db_user`` (owns ``tracked_order``)."""

    async def _override_user() -> User:
        return db_user

    app.dependency_overrides[get_current_user] = _override_user
    yield client


async def test_get_order_tracking_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/orders/{_ORDER_ID}/tracking")
    assert resp.status_code == 401


async def test_predict_eta_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/orders/{_ORDER_ID}/predict-eta",
        json={"latitude": -23.55, "longitude": -46.63},
    )
    assert resp.status_code == 401


async def test_get_order_tracking_matches_flutter_contract(
    db_auth_client: AsyncClient, tracked_order: Order
) -> None:
    resp = await db_auth_client.get(f"/api/orders/{tracked_order.id}/tracking")
    assert resp.status_code == 200

    body = resp.json()
    # Exactly the keys OrderModel.fromJson reads.
    assert set(body) == {
        "id",
        "headline",
        "description",
        "estimated_arrival",
        "steps",
        "location",
        "kit",
        "carrier",
        "map_url",
    }
    assert body["id"] == str(tracked_order.id)
    assert body["carrier"]
    # Timeline reflects the real status: 'separating' is the current step.
    steps = {s["code"]: s["status"] for s in body["steps"]}
    assert steps["separating"] == "current"
    assert steps["confirmed"] == "done"
    assert steps["out_for_delivery"] == "pending"
    # Kit is the real order items.
    assert [k["name"] for k in body["kit"]] == ["Apostila Ed. 5.0"]

    raw_steps = body["steps"]
    assert {s["status"] for s in raw_steps} <= {"done", "current", "pending"}
    assert all({"code", "title", "status", "timestamp"} == set(s) for s in raw_steps)

    assert set(body["location"]) == {"name", "city", "state", "updated_at"}
    assert all(set(item) == {"name", "subtitle"} for item in body["kit"])


async def test_get_order_tracking_unknown_order_returns_404(db_auth_client: AsyncClient) -> None:
    resp = await db_auth_client.get(f"/api/orders/{uuid.uuid4()}/tracking")
    assert resp.status_code == 404


async def test_get_order_tracking_malformed_id_returns_404(db_auth_client: AsyncClient) -> None:
    # A non-UUID id (e.g. a legacy label) must 404, never 500.
    resp = await db_auth_client.get(f"/api/orders/{_ORDER_ID}/tracking")
    assert resp.status_code == 404


async def test_get_order_tracking_other_users_order_returns_404(
    db_auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    # An order owned by someone else must be indistinguishable from missing.
    other = Order(
        user_id=uuid.uuid4(),
        total=Decimal("50.00"),
        payment_method="pix",
        status="confirmed",
        items=[
            OrderItem(
                product_id=uuid.uuid4(),
                product_name="X",
                unit_price=Decimal("50.00"),
                quantity=1,
            )
        ],
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    resp = await db_auth_client.get(f"/api/orders/{other.id}/tracking")
    assert resp.status_code == 404


async def test_predict_eta_happy_path(auth_client: AsyncClient) -> None:
    # ~2 km from the mocked destination.
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


async def test_get_order_route_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/orders/{_ORDER_ID}/route")
    assert resp.status_code == 401


async def test_get_order_route_happy_path(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", "test-key")

    async def fake_fetch(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="32 km",
            distance_km=32.0,
            duration_text="48 min",
            duration_minutes=48,
        )

    monkeypatch.setattr(directions, "fetch_directions", fake_fetch)

    resp = await auth_client.get(f"/api/orders/{_ORDER_ID}/route")
    assert resp.status_code == 200

    body = resp.json()
    assert set(body) == {
        "origin",
        "destination",
        "polyline",
        "distance_text",
        "distance_km",
        "duration_text",
        "duration_minutes",
    }
    assert set(body["origin"]) == {"label", "latitude", "longitude"}
    assert body["polyline"] == "enc-poly"
    assert body["origin"]["label"] == "Centro de Distribuição"
    assert body["duration_minutes"] == 48


async def test_get_order_route_unavailable_returns_503(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Provider failure surfaces as RouteUnavailable; the route must map it to a
    # clean 503, never a 500. Here the maps key is unconfigured.
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", None)

    resp = await auth_client.get(f"/api/orders/{_ORDER_ID}/route")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Rota indisponível no momento"
