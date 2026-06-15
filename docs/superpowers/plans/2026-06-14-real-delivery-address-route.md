# Real Delivery Address in Order Route — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the delivery route map and tracking location use the order's real
delivery address (a snapshot taken at checkout) instead of the hardcoded São
Paulo destination.

**Architecture:** At checkout the order stores a snapshot of the chosen address
(mirroring the existing `OrderItem` product snapshot). The tracking route loads
the order, enforces ownership, and feeds the snapshot address as **text** to the
Google Directions API, which geocodes it; the geocoded `end_location` coords
position the destination pin. The last-location card derives city/state from the
same snapshot. The `predict-eta` endpoint stays mocked (no Dart consumer; out of
scope, see spec).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, pytest,
httpx MockTransport; Flutter/Dart with `http` MockClient.

**Spec:** `docs/superpowers/specs/2026-06-14-real-delivery-address-route-design.md`

**Deviation from spec (intentional):** The spec proposed a new `AddressNotFound`
exception in the orders module. Instead we **reuse** the existing
`app.modules.addresses.services.get_address`, which already filters by ownership
and raises `app.modules.addresses.exceptions.AddressNotFound`. DRY.

**Spec scope note:** The spec flagged that order seeds might need the snapshot.
Verified: the repo has **no order seeds** (only `app/seeds/products.py`), so no
seed task is needed.

---

## File Structure

**Backend (`back-end/`):**
- `app/modules/orders/models.py` — add `ship_*` snapshot columns to `Order`.
- `alembic/versions/a1b2c3d4e5f6_add_order_ship_address.py` — new migration (create).
- `app/modules/orders/schemas.py` — add `address_id` to `OrderCreateIn`.
- `app/modules/orders/services.py` — snapshot the address in `create_order_from_cart`.
- `app/modules/orders/routes.py` — pass `address_id`; map `AddressNotFound` → 400.
- `app/modules/tracking/directions.py` — `destination: str`; return geocoded coords.
- `app/modules/tracking/services.py` — `get_order_route` loads order, builds
  destination from snapshot; clarify `_MOCK_DESTINATION` comment.
- `app/modules/tracking/routes.py` — inject `session`; map `OrderNotFound` → 404.
- `app/modules/tracking/builders.py` — location city/state from snapshot.
- Tests: `tests/modules/orders/test_services.py`, `tests/test_tracking_directions.py`,
  `tests/test_tracking_services.py`, `tests/test_tracking_routes.py`,
  `tests/test_tracking_builders.py`.

**Frontend (`front-end-flutter/`):**
- `lib/features/marketplace/data/checkout_service.dart` — send `address_id`.
- `lib/features/marketplace/presentation/checkout_screen.dart` — pass `_selectedAddressId`.
- `test/features/marketplace/checkout_service_test.dart` — assert body.

---

## Task 1: Order snapshot columns + migration

**Files:**
- Modify: `back-end/app/modules/orders/models.py`
- Create: `back-end/alembic/versions/a1b2c3d4e5f6_add_order_ship_address.py`

- [ ] **Step 1: Add the snapshot columns to the `Order` model**

In `app/modules/orders/models.py`, inside class `Order`, add these columns right
after the `status_updated_at` column definition (before the `items` relationship):

```python
    # Snapshot of the delivery address chosen at checkout. An order is a
    # historical record of WHERE it shipped, so the address is copied here and
    # must not change if the user later edits/deletes the source Address.
    # Nullable: pre-existing orders and the lenient (address-less) create
    # contract leave these empty; the route endpoint then returns 503.
    ship_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ship_zip_code: Mapped[str | None] = mapped_column(String(9), nullable=True)
    ship_street: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ship_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ship_complement: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ship_neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ship_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ship_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
```

- [ ] **Step 2: Write the migration**

Create `back-end/alembic/versions/a1b2c3d4e5f6_add_order_ship_address.py`:

```python
"""add order ship address snapshot

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-06-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("ship_label", 60),
    ("ship_zip_code", 9),
    ("ship_street", 160),
    ("ship_number", 20),
    ("ship_complement", 120),
    ("ship_neighborhood", 120),
    ("ship_city", 120),
    ("ship_state", 2),
)


def upgrade() -> None:
    for name, length in _COLUMNS:
        op.add_column("orders_orders", sa.Column(name, sa.String(length=length), nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("orders_orders", name)
```

- [ ] **Step 3: Apply the migration**

Run: `cd back-end && uv run alembic upgrade head`
Expected: `Running upgrade f4a5b6c7d8e9 -> a1b2c3d4e5f6, add order ship address snapshot`

- [ ] **Step 4: Commit**

```bash
cd back-end
git add app/modules/orders/models.py alembic/versions/a1b2c3d4e5f6_add_order_ship_address.py
git commit -m "feat(orders): add delivery address snapshot columns to Order"
```

---

## Task 2: Accept and snapshot the address at checkout

**Files:**
- Modify: `back-end/app/modules/orders/schemas.py`
- Modify: `back-end/app/modules/orders/services.py`
- Test: `back-end/tests/modules/orders/test_services.py`

- [ ] **Step 1: Add `address_id` to `OrderCreateIn`**

In `app/modules/orders/schemas.py`, add the import and field. At the top with the
other imports:

```python
import uuid
```
(already imported — confirm it's present; it is used by `OrderItemOut`.)

In class `OrderCreateIn`, add below `payment_method`:

```python
    # Which saved address this order ships to. Optional to preserve the original
    # empty-body contract; when present it is validated and snapshotted onto the
    # order. The app always sends the selected address id.
    address_id: uuid.UUID | None = None
```

- [ ] **Step 2: Write the failing tests for the snapshot**

In `tests/modules/orders/test_services.py`, add these imports at the top
(alongside the existing imports):

```python
from app.modules.addresses import services as addresses_services
from app.modules.addresses.exceptions import AddressNotFound
from app.modules.addresses.schemas import AddressIn
```

Add this test class at the end of the file:

```python
class TestCheckoutAddressSnapshot:
    async def _make_address(self, db_session, user_id):
        return await addresses_services.create_address(
            db_session,
            user_id,
            AddressIn(
                label="Casa",
                zip_code="13201-005",
                street="Rua das Flores",
                number="42",
                complement="Apto 3",
                neighborhood="Centro",
                city="Jundiaí",
                state="SP",
            ),
        )

    async def test_snapshots_address_onto_order(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        address = await self._make_address(db_session, created_user.id)

        order = await services.create_order_from_cart(
            db_session, created_user.id, "PIX", address_id=address.id
        )

        assert order.ship_street == "Rua das Flores"
        assert order.ship_number == "42"
        assert order.ship_city == "Jundiaí"
        assert order.ship_state == "SP"
        assert order.ship_zip_code == "13201-005"
        assert order.ship_label == "Casa"

    async def test_without_address_leaves_snapshot_empty(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        order = await services.create_order_from_cart(db_session, created_user.id, "PIX")
        assert order.ship_street is None

    async def test_rejects_address_of_another_user(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        stranger_address_id = uuid.uuid4()  # never created for this user
        with pytest.raises(AddressNotFound):
            await services.create_order_from_cart(
                db_session, created_user.id, "PIX", address_id=stranger_address_id
            )
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd back-end && uv run pytest tests/modules/orders/test_services.py::TestCheckoutAddressSnapshot -v`
Expected: FAIL — `create_order_from_cart()` got an unexpected keyword argument `address_id`.

- [ ] **Step 4: Implement the snapshot in `create_order_from_cart`**

In `app/modules/orders/services.py`, add the import near the other module imports:

```python
from app.modules.addresses import services as addresses_services
```

Change the signature of `create_order_from_cart`:

```python
async def create_order_from_cart(
    session: AsyncSession,
    user_id: uuid.UUID,
    payment_method: str,
    address_id: uuid.UUID | None = None,
) -> Order:
```

Right after the `products = {...}` dict is built and **before**
`order = Order(...)`, resolve the address (ownership enforced; raises
`AddressNotFound` for missing/foreign):

```python
    address = None
    if address_id is not None:
        address = await addresses_services.get_address(session, user_id, address_id)
```

Then change the `Order(...)` construction to copy the snapshot:

```python
    order = Order(
        user_id=user_id,
        payment_method=payment_method,
        total=Decimal("0.00"),
        ship_label=address.label if address else None,
        ship_zip_code=address.zip_code if address else None,
        ship_street=address.street if address else None,
        ship_number=address.number if address else None,
        ship_complement=address.complement if address else None,
        ship_neighborhood=address.neighborhood if address else None,
        ship_city=address.city if address else None,
        ship_state=address.state if address else None,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd back-end && uv run pytest tests/modules/orders/test_services.py -v`
Expected: PASS (the new class plus all pre-existing tests).

- [ ] **Step 6: Commit**

```bash
cd back-end
git add app/modules/orders/schemas.py app/modules/orders/services.py tests/modules/orders/test_services.py
git commit -m "feat(orders): snapshot delivery address onto order at checkout"
```

---

## Task 3: Wire `address_id` through the create-order route

**Files:**
- Modify: `back-end/app/modules/orders/routes.py`

- [ ] **Step 1: Pass `address_id` and map `AddressNotFound` → 400**

In `app/modules/orders/routes.py`, add the import near the other exception imports:

```python
from app.modules.addresses.exceptions import AddressNotFound
```

Replace the body of the `create_order` route handler with:

```python
    payment_method = payload.payment_method if payload is not None else ""
    address_id = payload.address_id if payload is not None else None
    try:
        order = await services.create_order_from_cart(
            session, user.id, payment_method, address_id=address_id
        )
    except EmptyCart as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        ) from exc
    except AddressNotFound as exc:
        # A stale or foreign address id is a client error, not a 404 on the order.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid delivery address"
        ) from exc
    return await _order_out(order, storage=storage, redis=redis)
```

- [ ] **Step 2: Verify the existing order route tests still pass**

Run: `cd back-end && uv run pytest tests/modules/orders -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd back-end
git add app/modules/orders/routes.py
git commit -m "feat(orders): accept address_id in create-order route"
```

---

## Task 4: Directions client accepts a text destination and returns geocoded coords

**Files:**
- Modify: `back-end/app/modules/tracking/directions.py`
- Test: `back-end/tests/test_tracking_directions.py`

- [ ] **Step 1: Update the directions tests**

In `tests/test_tracking_directions.py`, replace `_DEST` and `_OK_BODY` with:

```python
_DEST = "Rua das Flores, 42, Centro, Jundiaí - SP, 13201-005, Brazil"

_OK_BODY = {
    "status": "OK",
    "routes": [
        {
            "overview_polyline": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
            "legs": [
                {
                    "distance": {"text": "32,4 km", "value": 32400},
                    "duration": {"text": "48 min", "value": 2880},
                    "end_location": {"lat": -23.1857, "lng": -46.8978},
                }
            ],
        }
    ],
}
```

Replace the body assertions in `test_fetch_directions_parses_ok_response` (keep
the existing distance/duration asserts, add the coords):

```python
    assert result.destination_latitude == -23.1857
    assert result.destination_longitude == -46.8978
```

Replace the destination assertion in
`test_fetch_directions_sends_origin_destination_and_key`:

```python
    assert seen["destination"] == _DEST
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_directions.py -v`
Expected: FAIL — `DirectionsResult` has no field `destination_latitude`; and the
destination param is sent through `_format_point` so it won't equal `_DEST`.

- [ ] **Step 3: Update `directions.py`**

In `app/modules/tracking/directions.py`, add the two coord fields to the
dataclass:

```python
@dataclass(frozen=True)
class DirectionsResult:
    """Parsed, provider-agnostic outcome of a directions lookup."""

    polyline: str
    distance_text: str
    distance_km: float
    duration_text: str
    duration_minutes: int
    destination_latitude: float
    destination_longitude: float
```

Change the `destination` parameter type and how it is sent. Update the
`fetch_directions` signature:

```python
async def fetch_directions(
    client: httpx.AsyncClient,
    *,
    origin: tuple[float, float],
    destination: str,
    api_key: str,
) -> DirectionsResult:
```

In the `params` dict, send the destination string verbatim (origin still
formatted from coords):

```python
    params = {
        "origin": _format_point(origin),
        "destination": destination,
        "mode": "driving",
        "key": api_key,
    }
```

After computing `first_leg`, read the geocoded destination point from the last
leg's `end_location`, and include the coords in the returned result:

```python
    last_leg = legs[-1] if legs else {}
    end_location = last_leg.get("end_location") or {}

    return DirectionsResult(
        polyline=route["overview_polyline"]["points"],
        distance_text=first_leg.get("distance", {}).get("text", ""),
        distance_km=distance_meters / 1000,
        duration_text=first_leg.get("duration", {}).get("text", ""),
        duration_minutes=math.ceil(duration_seconds / 60),
        destination_latitude=float(end_location.get("lat", 0.0)),
        destination_longitude=float(end_location.get("lng", 0.0)),
    )
```

Update the module docstring's second sentence to mention the destination is now
a text address:

```python
"""Google Directions API client for the order-route map.

Pure HTTP boundary: given a ``(lat, lng)`` origin and a text destination address
plus an API key, it returns the encoded overview polyline, distance, duration,
and the geocoded destination coordinates (the route's final ``end_location``).
...
"""
```
(Keep the rest of the docstring unchanged.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd back-end && uv run pytest tests/test_tracking_directions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd back-end
git add app/modules/tracking/directions.py tests/test_tracking_directions.py
git commit -m "feat(tracking): directions client takes text destination, returns geocoded coords"
```

---

## Task 5: Route service loads the order and builds the destination from the snapshot

**Files:**
- Modify: `back-end/app/modules/tracking/services.py`
- Test: `back-end/tests/test_tracking_services.py`

- [ ] **Step 1: Rewrite the service tests for the new signature**

Replace the whole contents of `tests/test_tracking_services.py` with:

```python
"""Tests for the tracking service layer (route building + caching)."""

import uuid
from decimal import Decimal

import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.orders.models import Order, OrderItem
from app.modules.tracking import directions, services
from app.modules.tracking.directions import DirectionsResult
from app.modules.tracking.exceptions import OrderNotFound, RouteUnavailable

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
        dict(
            ship_label="Casa",
            ship_zip_code="13201-005",
            ship_street="Rua das Flores",
            ship_number="42",
            ship_complement="Apto 3",
            ship_neighborhood="Centro",
            ship_city="Jundiaí",
            ship_state="SP",
        )
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
    # Destination text is built from the snapshot and carries the real city.
    assert "Jundiaí" in seen["destination"]
    assert "Rua das Flores" in seen["destination"]
    # Destination pin uses the geocoded coords from Directions, not a SP constant.
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

    assert calls["n"] == 1  # second call served from cache
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_services.py -v`
Expected: FAIL — `get_order_route()` signature mismatch / cannot import `OrderNotFound`
from tracking.exceptions usage path, etc.

- [ ] **Step 3: Rewrite `get_order_route` and the destination builder**

In `app/modules/tracking/services.py`:

Add the import for the order model near the orders imports:

```python
from app.modules.orders.models import Order
```

Update the `_MOCK_DESTINATION` comment block to make clear it now serves only the
(unintegrated) predict-eta endpoint:

```python
# Destination used ONLY by the predict-eta endpoint, which has no app consumer
# yet (a future courier app) and needs coordinates for the Haversine math. The
# real order route (get_order_route) derives its destination from the order's
# snapshot address. Remove when predict-eta gets a real address source.
_MOCK_DESTINATION = GeoPoint(latitude=-23.561414, longitude=-46.655881)
```

Add a helper to format the snapshot as a Directions text query, placed above
`get_order_route`:

```python
def _destination_query(order: Order) -> str:
    """Build a Google-geocodable address string from the order's snapshot."""
    parts = [
        order.ship_street,
        order.ship_number,
        order.ship_neighborhood,
        f"{order.ship_city} - {order.ship_state}" if order.ship_city else None,
        order.ship_zip_code,
        "Brazil",
    ]
    return ", ".join(p for p in parts if p)
```

Replace the entire `get_order_route` function with:

```python
async def get_order_route(
    session: AsyncSession,
    redis: aioredis.Redis,
    user_id: uuid.UUID,
    order_id: str,
) -> RouteOut:
    """Return the street route from the distribution center to the order address.

    Loads the order (ownership enforced in the query — security rule #2), builds
    the destination from its delivery-address snapshot, and lazily calls the
    Google Directions API only on a cache miss (origin/destination are fixed per
    order, so the route is cached in Redis to avoid repeated paid calls).
    """
    try:
        parsed_id = uuid.UUID(order_id)
    except ValueError as exc:
        # Not a real order id — treat as not found, don't 500 on bad input.
        raise OrderNotFound() from exc

    order = await orders_services.get_order(session, user_id, parsed_id)
    if not order.ship_street:
        # Order has no delivery-address snapshot (pre-migration or address-less
        # checkout); there is nothing to route to.
        raise RouteUnavailable("order has no delivery address")

    cache_key = f"{_ROUTE_CACHE_PREFIX}{order_id}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return RouteOut.model_validate_json(cached)

    api_key = settings.GOOGLE_MAPS_API_PLATAFORM
    if not api_key:
        logger.error("tracking: GOOGLE_MAPS_API_PLATAFORM is not configured")
        raise RouteUnavailable("maps api key not configured")

    async with httpx.AsyncClient() as client:
        result = await directions.fetch_directions(
            client,
            origin=(_MOCK_ORIGIN.latitude, _MOCK_ORIGIN.longitude),
            destination=_destination_query(order),
            api_key=api_key,
        )

    route = RouteOut(
        origin=RoutePoint(
            label=_ORIGIN_LABEL,
            latitude=_MOCK_ORIGIN.latitude,
            longitude=_MOCK_ORIGIN.longitude,
        ),
        destination=RoutePoint(
            label=order.ship_label or _DESTINATION_LABEL,
            latitude=result.destination_latitude,
            longitude=result.destination_longitude,
        ),
        polyline=result.polyline,
        distance_text=result.distance_text,
        distance_km=result.distance_km,
        duration_text=result.duration_text,
        duration_minutes=result.duration_minutes,
    )

    await redis.set(
        cache_key,
        route.model_dump_json(),
        ex=settings.TRACKING_ROUTE_CACHE_TTL_SECONDS,
    )
    logger.info("tracking: route computed order={} user={}", order_id, user_id)
    return route
```

Note: `OrderNotFound` here is `app.modules.orders.exceptions.OrderNotFound`,
already imported at the top of `services.py` (`from app.modules.orders.exceptions
import OrderNotFound`). Confirm that import is present; it is used by
`get_order_tracking`. The tracking-module `OrderNotFound` in `exceptions.py` is a
separate unused class — leave it; the route maps the orders one (see Task 6).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd back-end && uv run pytest tests/test_tracking_services.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd back-end
git add app/modules/tracking/services.py tests/test_tracking_services.py
git commit -m "feat(tracking): build order route from delivery-address snapshot"
```

---

## Task 6: Route endpoint injects the session and maps OrderNotFound → 404

**Files:**
- Modify: `back-end/app/modules/tracking/routes.py`
- Test: `back-end/tests/test_tracking_routes.py`

- [ ] **Step 1: Rewrite the route-endpoint tests**

In `tests/test_tracking_routes.py`, the `_ORDER_ID`-based route tests no longer
fit (the endpoint now loads a real order). Update the **three route tests** at the
bottom of the file. First, ensure the helper fixtures `tracked_order`,
`db_user`, and `db_auth_client` exist (they already do, used by the tracking
tests). Add a fixture for an order WITH a snapshot address right after the
`tracked_order` fixture:

```python
@pytest.fixture
async def routed_order(db_session: AsyncSession, db_user: User) -> Order:
    """A persisted order owned by ``db_user`` with a delivery-address snapshot."""
    order = Order(
        user_id=db_user.id,
        total=Decimal("100.00"),
        payment_method="pix",
        status="out_for_delivery",
        ship_label="Casa",
        ship_zip_code="13201-005",
        ship_street="Rua das Flores",
        ship_number="42",
        ship_complement="Apto 3",
        ship_neighborhood="Centro",
        ship_city="Jundiaí",
        ship_state="SP",
        items=[
            OrderItem(
                product_id=uuid.uuid4(),
                product_name="Apostila",
                unit_price=Decimal("100.00"),
                quantity=1,
            )
        ],
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order
```

Replace `test_get_order_route_happy_path` with (now uses `db_auth_client` +
`routed_order`):

```python
async def test_get_order_route_happy_path(
    db_auth_client: AsyncClient, routed_order: Order, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", "test-key")

    async def fake_fetch(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="32 km",
            distance_km=32.0,
            duration_text="48 min",
            duration_minutes=48,
            destination_latitude=-23.1857,
            destination_longitude=-46.8978,
        )

    monkeypatch.setattr(directions, "fetch_directions", fake_fetch)

    resp = await db_auth_client.get(f"/api/orders/{routed_order.id}/route")
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
    assert body["destination"]["latitude"] == -23.1857
    assert body["destination"]["longitude"] == -46.8978
    assert body["duration_minutes"] == 48
```

Replace `test_get_order_route_unavailable_returns_503` with (order exists + key
unset → 503):

```python
async def test_get_order_route_unavailable_returns_503(
    db_auth_client: AsyncClient, routed_order: Order, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Provider failure surfaces as RouteUnavailable; the route must map it to a
    # clean 503, never a 500. Here the maps key is unconfigured.
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", None)

    resp = await db_auth_client.get(f"/api/orders/{routed_order.id}/route")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Rota indisponível no momento"
```

Add two new tests after it:

```python
async def test_get_order_route_unknown_order_returns_404(db_auth_client: AsyncClient) -> None:
    resp = await db_auth_client.get(f"/api/orders/{uuid.uuid4()}/route")
    assert resp.status_code == 404


async def test_get_order_route_without_address_returns_503(
    db_auth_client: AsyncClient, tracked_order: Order, monkeypatch: pytest.MonkeyPatch
) -> None:
    # tracked_order has no ship_* snapshot -> nothing to route to.
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", "test-key")
    resp = await db_auth_client.get(f"/api/orders/{tracked_order.id}/route")
    assert resp.status_code == 503
```

Keep `test_get_order_route_requires_auth` as-is (401 happens before any DB load).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_routes.py -k route -v`
Expected: FAIL — endpoint still calls the old service signature.

- [ ] **Step 3: Update the route endpoint**

In `app/modules/tracking/routes.py`:

Add the session dependency import if missing (it is not currently imported here):

```python
from app.core.database import get_session
```
and
```python
from sqlalchemy.ext.asyncio import AsyncSession
```

Add the orders `OrderNotFound` import (the route currently imports the tracking
one; we map the orders one raised by the service):

```python
from app.modules.orders.exceptions import OrderNotFound
```
Note: `routes.py` already has `from app.modules.orders.exceptions import
OrderNotFound` (used by `get_order_tracking`). Confirm it's present — reuse it; do
not add a duplicate. Remove the now-unused tracking `OrderNotFound` import only if
it is unused after this change (it is imported from
`app.modules.tracking.exceptions`? check — currently `get_order_tracking` uses
`from app.modules.orders.exceptions import OrderNotFound`, so the tracking one is
not imported here. No change needed.)

Replace the `get_order_route` endpoint with:

```python
@router.get("/{order_id}/route", response_model=RouteOut)
async def get_order_route(
    order_id: OrderId,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> RouteOut:
    """Return the street route from the distribution center to the destination."""
    try:
        return await services.get_order_route(session, redis, user.id, order_id)
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado"
        ) from exc
    except RouteUnavailable as exc:
        # Provider down/over-quota, no route, no address, or key unconfigured —
        # surface a clean 503 instead of a 500 (never echo the provider detail).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rota indisponível no momento",
        ) from exc
```

- [ ] **Step 4: Run the full tracking route test file**

Run: `cd back-end && uv run pytest tests/test_tracking_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd back-end
git add app/modules/tracking/routes.py tests/test_tracking_routes.py
git commit -m "feat(tracking): load order and enforce ownership in route endpoint"
```

---

## Task 7: Last-location card derives city/state from the snapshot

**Files:**
- Modify: `back-end/app/modules/tracking/builders.py`
- Test: `back-end/tests/test_tracking_builders.py`

- [ ] **Step 1: Inspect the builders test helper**

The `_order(...)` helper in `tests/test_tracking_builders.py` builds an `Order`
without `ship_*` fields. Read the top of the file to confirm the helper signature
before editing:

Run: `cd back-end && sed -n '1,50p' tests/test_tracking_builders.py`

- [ ] **Step 2: Write the failing tests**

In `tests/test_tracking_builders.py`, add these tests at the end of the file
(they pass `ship_*` via the model directly):

```python
def test_location_uses_snapshot_city_when_out_for_delivery() -> None:
    order = _order(OrderStatus.OUT_FOR_DELIVERY)
    order.ship_city = "Jundiaí"
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    assert payload.location.city == "Jundiaí"
    assert payload.location.state == "SP"


def test_location_uses_snapshot_city_when_delivered() -> None:
    order = _order(OrderStatus.DELIVERED)
    order.ship_city = "Campinas"
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    assert payload.location.city == "Campinas"


def test_location_falls_back_to_cd_before_dispatch() -> None:
    order = _order(OrderStatus.SEPARATING)
    order.ship_city = "Jundiaí"
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    # Still at the distribution center until it's out for delivery.
    assert payload.location.city == "Cajamar"
    assert payload.location.state == "SP"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_builders.py -k location -v`
Expected: FAIL — out-for-delivery/delivered still report Cajamar.

- [ ] **Step 4: Update `build_order_tracking`**

In `app/modules/tracking/builders.py`, replace the `location=TrackingLocationOut(...)`
block inside the returned `OrderTrackingOut` with logic that uses the snapshot
once the parcel has left the CD. Just before the `return OrderTrackingOut(...)`,
add:

```python
    # Once the parcel is out for delivery / delivered, the last-known location is
    # the destination city; before that it sits at the distribution center.
    at_destination = status in (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED)
    location_city = order.ship_city if (at_destination and order.ship_city) else "Cajamar"
    location_state = order.ship_state if (at_destination and order.ship_state) else "SP"
```

Then change the `location=` argument to:

```python
        location=TrackingLocationOut(
            name=_LOCATION_NAME.get(status, _DEFAULT_LOCATION_NAME),
            city=location_city,
            state=location_state,
            updated_at=status_updated_at,
        ),
```

Update the comment near `_LOCATION_NAME` that says coordinates stay mocked — it is
now partly real:

```python
# Last-known-location label per status. The city/state are derived from the
# order's delivery-address snapshot once it's out for delivery (see
# build_order_tracking); this dict only drives the location card's name text.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd back-end && uv run pytest tests/test_tracking_builders.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd back-end
git add app/modules/tracking/builders.py tests/test_tracking_builders.py
git commit -m "feat(tracking): last-location city/state from delivery snapshot"
```

---

## Task 8: Flutter — checkout service sends `address_id`

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/data/checkout_service.dart`
- Test: `front-end-flutter/test/features/marketplace/checkout_service_test.dart`

- [ ] **Step 1: Update the test**

In `test/features/marketplace/checkout_service_test.dart`, replace the first test
with one that asserts the body includes `address_id`:

```dart
  test('placeOrder posts payment_method and address_id, returns the order id',
      () async {
    final calls = <String>[];
    Map<String, dynamic>? sentBody;
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      sentBody = jsonDecode(req.body) as Map<String, dynamic>;
      if (req.method == 'POST' && req.url.path.endsWith('/orders')) {
        return http.Response(jsonEncode({'id': 'order-9'}), 201);
      }
      return http.Response('nope', 500);
    });
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    final orderId =
        await service.placeOrder(paymentMethod: 'PIX', addressId: 'addr-1');

    expect(orderId, 'order-9');
    expect(calls, ['POST /api/orders']);
    expect(sentBody, {'payment_method': 'PIX', 'address_id': 'addr-1'});
  });
```

Update the second test's `placeOrder` call to pass an address id:

```dart
    expect(
      () => service.placeOrder(paymentMethod: 'PIX', addressId: 'addr-1'),
      throwsA(isA<CheckoutException>()),
    );
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-end-flutter && flutter test test/features/marketplace/checkout_service_test.dart`
Expected: FAIL — `placeOrder` has no named parameter `addressId`.

- [ ] **Step 3: Update `placeOrder`**

In `lib/features/marketplace/data/checkout_service.dart`, change the `placeOrder`
signature and body. The address id is optional; only include the key when present
(keeps the empty-body-compatible contract):

```dart
  /// Retorna o id do pedido criado.
  Future<String> placeOrder({
    required String paymentMethod,
    String? addressId,
  }) async {
    final headers = await _headers();
    final res = await _send(
      () => _client.post(
        Uri.parse('${ApiConfig.baseUrl}/orders'),
        headers: {'Content-Type': 'application/json', ...headers},
        body: jsonEncode({
          'payment_method': paymentMethod,
          if (addressId != null) 'address_id': addressId,
        }),
      ),
      accept: const {200, 201},
      error: 'Falha ao finalizar o pedido',
    );
    return (jsonDecode(res.body) as Map<String, dynamic>)['id'] as String;
  }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd front-end-flutter && flutter test test/features/marketplace/checkout_service_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd front-end-flutter
git add lib/features/marketplace/data/checkout_service.dart test/features/marketplace/checkout_service_test.dart
git commit -m "feat(checkout): send selected address_id when placing order"
```

---

## Task 9: Flutter — pass the selected address from the checkout screen

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart`

- [ ] **Step 1: Pass `_selectedAddressId` into `placeOrder`**

In `lib/features/marketplace/presentation/checkout_screen.dart`, inside
`_placeOrder`, update the `CheckoutService().placeOrder(...)` call (around line
286) to forward the selected address:

```dart
      await CheckoutService().placeOrder(
        paymentMethod: _paymentTitle(method),
        addressId: _selectedAddressId,
      );
```

- [ ] **Step 2: Static analysis**

Run: `cd front-end-flutter && flutter analyze lib/features/marketplace/presentation/checkout_screen.dart`
Expected: No issues (no new warnings).

- [ ] **Step 3: Commit**

```bash
cd front-end-flutter
git add lib/features/marketplace/presentation/checkout_screen.dart
git commit -m "feat(checkout): forward selected address to order creation"
```

---

## Task 10: Full verification

- [ ] **Step 1: Backend — full test suite + lint**

Run:
```bash
cd back-end
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```
Expected: all tests pass; ruff clean.

- [ ] **Step 2: Frontend — analyze + tests**

Run:
```bash
cd front-end-flutter
flutter analyze
flutter test
```
Expected: no analyzer issues; all tests pass.

- [ ] **Step 3: Manual smoke (optional, requires running stack + Maps key)**

1. Create/select an address in a non-SP city (e.g. Jundiaí) and finalize a
   purchase.
2. Open the order → "Ver mapa". The destination pin and the route end on the
   chosen city, not São Paulo.
3. Advance the order to "out_for_delivery"; the "Última Localização" shows the
   destination city.

---

## Self-Review Notes

- **Spec coverage:** §1 model+migration → Task 1; §2 checkout → Tasks 2–3, 8–9;
  §3 route service → Tasks 5–6; §4 directions → Task 4; §5 builders → Task 7;
  predict-eta out of scope → comment updated in Task 5; seeds → verified none
  exist (noted in header).
- **Ownership/authz gap** (route had none) closed in Tasks 5–6.
- **Type consistency:** `DirectionsResult.destination_latitude/longitude`,
  `get_order_route(session, redis, user_id, order_id)`, and
  `placeOrder(paymentMethod, addressId)` are used identically across all tasks
  and their tests.
</content>
