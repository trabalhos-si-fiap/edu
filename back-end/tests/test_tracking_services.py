"""Tests for the tracking service layer (route building + caching)."""

import uuid
from decimal import Decimal

import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.orders.exceptions import OrderNotFound
from app.modules.orders.models import Order, OrderItem
from app.modules.tracking import directions, services
from app.modules.tracking.directions import DirectionsResult
from app.modules.tracking.exceptions import RouteUnavailable

_FAKE_RESULT = DirectionsResult(
    polyline="enc",
    distance_text="32 km",
    distance_km=32.0,
    duration_text="48 min",
    duration_minutes=48,
    destination_latitude=-23.1857,
    destination_longitude=-46.8978,
)


@pytest.fixture(autouse=True)
def _set_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", "test-key")


async def _make_order(db_session: AsyncSession, user_id: uuid.UUID, *, with_address: bool) -> Order:
    ship = (
        {
            "ship_label": "Casa",
            "ship_zip_code": "13201-005",
            "ship_street": "Rua das Flores",
            "ship_number": "42",
            "ship_complement": "Apto 3",
            "ship_neighborhood": "Centro",
            "ship_city": "Jundiaí",
            "ship_state": "SP",
        }
        if with_address
        else {}
    )
    order = Order(
        user_id=user_id,
        total=Decimal("100.00"),
        payment_method="pix",
        status="separating",
        items=[
            OrderItem(
                product_id=uuid.uuid4(),
                product_name="Apostila",
                unit_price=Decimal("100.00"),
                quantity=1,
            )
        ],
        **ship,
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


async def test_get_order_route_builds_payload(
    db_session: AsyncSession, redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    order = await _make_order(db_session, user_id, with_address=True)
    seen: dict[str, object] = {}

    async def fake_fetch(client, *, origin, destination, api_key):
        seen["destination"] = destination
        return _FAKE_RESULT

    monkeypatch.setattr(directions, "fetch_directions", fake_fetch)

    route = await services.get_order_route(db_session, redis_client, user_id, str(order.id))

    assert route.origin.label == "Centro de Distribuição"
    assert "Jundiaí" in seen["destination"]
    assert "Rua das Flores" in seen["destination"]
    assert route.destination.latitude == -23.1857
    assert route.destination.longitude == -46.8978
    assert route.polyline == "enc"
    assert route.duration_minutes == 48


async def test_get_order_route_caches_result(
    db_session: AsyncSession, redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    order = await _make_order(db_session, user_id, with_address=True)
    calls = {"n": 0}

    async def counting_fetch(client, *, origin, destination, api_key):
        calls["n"] += 1
        return _FAKE_RESULT

    monkeypatch.setattr(directions, "fetch_directions", counting_fetch)

    first = await services.get_order_route(db_session, redis_client, user_id, str(order.id))
    second = await services.get_order_route(db_session, redis_client, user_id, str(order.id))

    assert calls["n"] == 1
    assert first.model_dump() == second.model_dump()


async def test_get_order_route_unknown_order_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis
) -> None:
    with pytest.raises(OrderNotFound):
        await services.get_order_route(db_session, redis_client, uuid.uuid4(), str(uuid.uuid4()))


async def test_get_order_route_foreign_order_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis
) -> None:
    owner = uuid.uuid4()
    order = await _make_order(db_session, owner, with_address=True)
    stranger = uuid.uuid4()
    with pytest.raises(OrderNotFound):
        await services.get_order_route(db_session, redis_client, stranger, str(order.id))


async def test_get_order_route_malformed_id_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis
) -> None:
    with pytest.raises(OrderNotFound):
        await services.get_order_route(db_session, redis_client, uuid.uuid4(), "ED-99420")


async def test_get_order_route_without_address_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    order = await _make_order(db_session, user_id, with_address=False)
    with pytest.raises(RouteUnavailable):
        await services.get_order_route(db_session, redis_client, user_id, str(order.id))


async def test_get_order_route_without_key_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    order = await _make_order(db_session, user_id, with_address=True)
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", None)

    with pytest.raises(RouteUnavailable):
        await services.get_order_route(db_session, redis_client, user_id, str(order.id))
