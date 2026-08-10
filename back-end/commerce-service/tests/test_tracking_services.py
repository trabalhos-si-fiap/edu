"""Testes da camada de serviço do rastreio (construção de rota + cache).

Porte de `legacy/tests/test_tracking_services.py` (task C9, arquivo
inteiro: 7 de 7). `services.get_order_route` virou `services.rota_do_pedido`
e `app.modules.tracking.exceptions.{OrderNotFound,RouteUnavailable}` viraram
`app.exceptions.{OrderNotFoundError,RouteUnavailableError}` (regra N818 do
ruff — ver task-C9-brief.md, "Contexto autoritativo do controlador").

`redis_client` é `fakeredis` (`tests/conftest.py`), não o Redis vivo do
usuário — decisão de 2026-08-07 (bloco B). `test_get_order_route_caches_result`
depende disso: cada `FakeRedis()` é um backend em memória isolado por teste
(function-scoped), o que já garante isolamento entre testes sem precisar de
`flushdb`.
"""

import uuid
from decimal import Decimal

import pytest
import redis.asyncio as aioredis
from edu_common.security import create_access_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import OrderNotFoundError, RouteUnavailableError
from app.models.pedido import Order, OrderItem
from app.models.produto import Product
from app.services import directions
from app.services import rastreio as services
from app.services.directions import DirectionsResult
from app.services.status_pedido import StatusPedido

_FAKE_RESULT = DirectionsResult(
    polyline="enc",
    distance_text="32 km",
    distance_km=32.0,
    duration_text="48 min",
    duration_minutes=48,
    destination_latitude=-23.1857,
    destination_longitude=-46.8978,
)


def headers_for(role: str, sub: str) -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _set_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")


async def _make_order(db_session: AsyncSession, user_id: uuid.UUID, *, with_address: bool) -> Order:
    # `order_items.product_id` tem FK para `products` neste serviço (o
    # legacy usa um `uuid.uuid4()` solto, sem FK) — mesmo achado já
    # documentado em `tests/test_tracking_routes.py::_tracked_order`. Semeia
    # um `Product` real antes do item.
    produto = Product(name="Apostila", price=Decimal("100.00"), type="apostila")
    db_session.add(produto)
    await db_session.flush()

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
        status=StatusPedido.EM_SEPARACAO.value,
        items=[
            OrderItem(
                product_id=produto.id,
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

    route = await services.rota_do_pedido(db_session, redis_client, user_id, order.id)

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

    first = await services.rota_do_pedido(db_session, redis_client, user_id, order.id)
    second = await services.rota_do_pedido(db_session, redis_client, user_id, order.id)

    assert calls["n"] == 1
    assert first.model_dump() == second.model_dump()


async def test_get_order_route_unknown_order_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis
) -> None:
    with pytest.raises(OrderNotFoundError):
        await services.rota_do_pedido(db_session, redis_client, uuid.uuid4(), uuid.uuid4())


async def test_get_order_route_foreign_order_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis
) -> None:
    owner = uuid.uuid4()
    order = await _make_order(db_session, owner, with_address=True)
    stranger = uuid.uuid4()
    with pytest.raises(OrderNotFoundError):
        await services.rota_do_pedido(db_session, redis_client, stranger, order.id)


async def test_get_order_route_malformed_id_raises(client) -> None:
    """No legacy, `services.get_order_route` recebia `order_id: str` e um id
    malformado (não-UUID) virava `OrderNotFound` (404) DENTRO do serviço —
    `legacy/tests/test_tracking_services.py::test_get_order_route_malformed_id_raises`
    chamava `services.get_order_route(db, redis, user_id, "ED-99420")`
    diretamente e esperava `pytest.raises(OrderNotFound)`.

    Aqui `rota_do_pedido` tipa `order_id: uuid.UUID` — o mesmo tipo do path
    param do FastAPI (`GET /orders/{order_id}/route`). Um id malformado
    nunca chega ao serviço: o FastAPI rejeita a conversão do path e devolve
    **422** antes de qualquer código nosso rodar. Não há mais nada para
    `services.rota_do_pedido` levantar nesse caso — a prova equivalente,
    portanto, é no limite HTTP, não numa chamada direta ao serviço.

    Divergência deliberada (registrada no relatório da task C9, para o
    portão da C12 achar — junto da mesma divergência que a C8 documentou só
    em docstring para `/tracking`)."""
    resp = await client.get(
        "/orders/ED-99420/route", headers=headers_for("student", str(uuid.uuid4()))
    )
    assert resp.status_code == 422


async def test_get_order_route_without_address_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis
) -> None:
    user_id = uuid.uuid4()
    order = await _make_order(db_session, user_id, with_address=False)
    with pytest.raises(RouteUnavailableError):
        await services.rota_do_pedido(db_session, redis_client, user_id, order.id)


async def test_get_order_route_without_key_raises(
    db_session: AsyncSession, redis_client: aioredis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    order = await _make_order(db_session, user_id, with_address=True)
    monkeypatch.setattr(settings, "google_maps_api_key", "")

    with pytest.raises(RouteUnavailableError):
        await services.rota_do_pedido(db_session, redis_client, user_id, order.id)
