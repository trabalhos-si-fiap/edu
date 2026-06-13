# Order Tracking Map Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "Ver mapa" button on the order-tracking screen open an embedded Google Map showing the real street route between the distribution center and the order's destination.

**Architecture:** A new lazy backend endpoint `GET /orders/{id}/route` calls the Google Directions API server-side (key never leaves the server), caches the result in Redis per order, and returns an encoded polyline plus origin/destination points. The Flutter app fetches this on tap and renders it in a new `GoogleMap` screen, decoding the polyline locally.

**Tech Stack:** Python 3.12 / FastAPI / httpx / Redis (backend); Flutter / `google_maps_flutter` / `provider` (frontend). Google Maps Platform key in `back-end/.env` as `GOOGLE_MAPS_API_PLATAFORM`.

---

## File Structure

**Backend (`back-end/`):**
- `app/core/config.py` — add `GOOGLE_MAPS_API_PLATAFORM` setting (modify).
- `app/modules/tracking/exceptions.py` — add `RouteUnavailable` (modify).
- `app/modules/tracking/schemas.py` — add `RoutePoint`, `RouteOut` (modify).
- `app/modules/tracking/directions.py` — Google Directions client (create).
- `app/modules/tracking/services.py` — add `get_order_route` + cache (modify).
- `app/modules/tracking/routes.py` — add `GET /orders/{id}/route` (modify).
- `tests/test_tracking_directions.py` — directions client tests (create).
- `tests/test_tracking_services.py` — service/cache tests (create).
- `tests/test_tracking_routes.py` — endpoint tests (modify).

**Frontend (`front-end-flutter/`):**
- `lib/features/order_tracking/data/polyline_codec.dart` — polyline decoder (create).
- `lib/features/order_tracking/domain/order_route.dart` — `OrderRoute` model (create).
- `lib/features/order_tracking/data/route_service.dart` — HTTP client (create).
- `lib/features/order_tracking/presentation/route_provider.dart` — state machine (create).
- `lib/features/order_tracking/presentation/order_map_screen.dart` — map screen (create).
- `lib/features/order_tracking/presentation/order_tracking_screen.dart` — wire button (modify).
- `lib/main.dart` — register `/order-map` route (modify).
- `pubspec.yaml` — add `google_maps_flutter` (modify).
- `android/app/src/main/AndroidManifest.xml` — Maps SDK key meta-data (modify).
- `android/app/build.gradle.kts` — inject key from gitignored props (modify).
- `android/secrets.properties` — local Maps key, gitignored (create).
- `test/features/order_tracking/polyline_codec_test.dart` (create).
- `test/features/order_tracking/order_route_test.dart` (create).
- `test/features/order_tracking/route_service_test.dart` (create).
- `test/features/order_tracking/route_provider_test.dart` (create).

---

## Task 1: Backend — config, exception, and route schemas

**Files:**
- Modify: `back-end/app/core/config.py:39-48`
- Modify: `back-end/app/modules/tracking/exceptions.py`
- Modify: `back-end/app/modules/tracking/schemas.py:55`
- Test: `back-end/tests/test_tracking_schemas.py` (create)

- [ ] **Step 1: Write the failing schema test**

Create `back-end/tests/test_tracking_schemas.py`:

```python
"""Schema-shape tests for the tracking route payload."""

from app.modules.tracking.schemas import RouteOut, RoutePoint


def test_route_out_serializes_expected_keys_and_rounds_distance() -> None:
    payload = RouteOut(
        origin=RoutePoint(label="Centro de Distribuição", latitude=-23.3558, longitude=-46.8769),
        destination=RoutePoint(label="Endereço de entrega", latitude=-23.561414, longitude=-46.655881),
        polyline="abc123",
        distance_text="32 km",
        distance_km=32.123456,
        duration_text="48 min",
        duration_minutes=48,
    )

    dumped = payload.model_dump()
    assert set(dumped) == {
        "origin",
        "destination",
        "polyline",
        "distance_text",
        "distance_km",
        "duration_text",
        "duration_minutes",
    }
    assert set(dumped["origin"]) == {"label", "latitude", "longitude"}
    assert dumped["distance_km"] == 32.123  # rounded to 3 decimals
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd back-end && uv run pytest tests/test_tracking_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'RouteOut'`.

- [ ] **Step 3: Add the `GOOGLE_MAPS_API_PLATAFORM` setting**

In `back-end/app/core/config.py`, after the `TRACKING_URBAN_ROUTE_FACTOR` line (currently line 48), add:

```python
    # Google Maps Platform key used server-side to call the Directions API for
    # the order-route map. Lives in back-end/.env; never sent to the client.
    # (Spelling matches the key the operator created in .env.)
    GOOGLE_MAPS_API_PLATAFORM: str | None = None
    # Time-to-live for a cached order route. Origin and destination are fixed
    # per order, so the route is stable — cache it to avoid repeat Directions
    # calls (and cost).
    TRACKING_ROUTE_CACHE_TTL_SECONDS: int = 21600  # 6 hours
```

- [ ] **Step 4: Add the `RouteUnavailable` exception**

Replace the contents of `back-end/app/modules/tracking/exceptions.py` with:

```python
class TrackingError(Exception):
    """Base class for delivery-tracking domain errors."""


class OrderNotFound(TrackingError):
    """No trackable order with the given id belongs to the user."""


class RouteUnavailable(TrackingError):
    """The routing provider could not return a route for the given points."""
```

- [ ] **Step 5: Add the `RoutePoint` and `RouteOut` schemas**

In `back-end/app/modules/tracking/schemas.py`, after the `OrderTrackingOut` class (ends at line 55), add:

```python
# --- Order route map (GET /orders/{id}/route) --------------------------------


class RoutePoint(BaseModel):
    """A named endpoint of the delivery route (origin or destination)."""

    label: str = Field(..., max_length=120)
    latitude: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(..., ge=_LNG_MIN, le=_LNG_MAX)


class RouteOut(BaseModel):
    """Street route between the distribution center and the order destination."""

    origin: RoutePoint
    destination: RoutePoint
    polyline: str = Field(..., description="Google overview_polyline (encoded).")
    distance_text: str = Field(..., max_length=40)
    distance_km: float = Field(..., ge=0)
    duration_text: str = Field(..., max_length=40)
    duration_minutes: int = Field(..., ge=0)

    @field_serializer("distance_km")
    def _round_distance(self, value: float) -> float:
        return round(value, 3)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd back-end && uv run pytest tests/test_tracking_schemas.py -v`
Expected: PASS.

- [ ] **Step 7: Lint and commit**

```bash
cd back-end && uv run ruff check app/ tests/ && uv run ruff format app/ tests/
git add app/core/config.py app/modules/tracking/exceptions.py app/modules/tracking/schemas.py tests/test_tracking_schemas.py
git commit -m "feat(tracking): add route schemas, exception and maps key setting"
```

---

## Task 2: Backend — Google Directions client

**Files:**
- Create: `back-end/app/modules/tracking/directions.py`
- Test: `back-end/tests/test_tracking_directions.py`

- [ ] **Step 1: Write the failing tests**

Create `back-end/tests/test_tracking_directions.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_directions.py -v`
Expected: FAIL — `ModuleNotFoundError: ... tracking.directions`.

- [ ] **Step 3: Implement the directions client**

Create `back-end/app/modules/tracking/directions.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd back-end && uv run pytest tests/test_tracking_directions.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd back-end && uv run ruff check app/ tests/ && uv run ruff format app/ tests/
git add app/modules/tracking/directions.py tests/test_tracking_directions.py
git commit -m "feat(tracking): add google directions api client"
```

---

## Task 3: Backend — route service with Redis cache

**Files:**
- Modify: `back-end/app/modules/tracking/services.py`
- Test: `back-end/tests/test_tracking_services.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `back-end/tests/test_tracking_services.py`:

```python
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
    async def fake_fetch(client, *, origin, destination, api_key):  # noqa: ANN001, ANN202
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

    async def counting_fetch(client, *, origin, destination, api_key):  # noqa: ANN001, ANN202
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_services.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'get_order_route'`.

- [ ] **Step 3: Implement the service**

In `back-end/app/modules/tracking/services.py`, update the imports block (lines 13-28) to add Redis, the directions module, the new schemas, the exception, and the config:

```python
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from loguru import logger

from app.core.config import settings
from app.modules.tracking import directions
from app.modules.tracking.enums import TrackingStepStatus
from app.modules.tracking.exceptions import RouteUnavailable
from app.modules.tracking.routing import predict_route
from app.modules.tracking.schemas import (
    CourierLocationIn,
    ETAPredictionOut,
    GeoPoint,
    KitItemOut,
    OrderTrackingOut,
    RouteOut,
    RoutePoint,
    TrackingLocationOut,
    TrackingStepOut,
)

import httpx
```

(Place the `import httpx` with the other stdlib/third-party imports per ruff's ordering; running `ruff format` in Step 5 will fix order.)

Then, just after the `_MOCK_DESTINATION` definition (currently line 33), add the origin and cache constants:

```python
# Mocked distribution center (route origin) — Cajamar/SP. Paired with
# _MOCK_DESTINATION until the orders/addresses integration provides real coords.
_MOCK_ORIGIN = GeoPoint(latitude=-23.3558, longitude=-46.8769)
_ORIGIN_LABEL = "Centro de Distribuição"
_DESTINATION_LABEL = "Endereço de entrega"

# Redis key prefix for cached order routes.
_ROUTE_CACHE_PREFIX = "tracking:route:"
```

Then add the new service function at the end of the file:

```python
async def get_order_route(
    redis: aioredis.Redis, user_id: object, order_id: str
) -> RouteOut:
    """Return the street route from the distribution center to the order address.

    Lazily calls the Google Directions API only on a cache miss; the origin and
    destination are fixed per order, so the resulting route is cached in Redis
    (security/cost: avoids repeated paid Directions calls). Ownership is the
    caller's responsibility; with the current mock every order resolves.
    """
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
            destination=(_MOCK_DESTINATION.latitude, _MOCK_DESTINATION.longitude),
            api_key=api_key,
        )

    route = RouteOut(
        origin=RoutePoint(
            label=_ORIGIN_LABEL,
            latitude=_MOCK_ORIGIN.latitude,
            longitude=_MOCK_ORIGIN.longitude,
        ),
        destination=RoutePoint(
            label=_DESTINATION_LABEL,
            latitude=_MOCK_DESTINATION.latitude,
            longitude=_MOCK_DESTINATION.longitude,
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd back-end && uv run pytest tests/test_tracking_services.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd back-end && uv run ruff check app/ tests/ && uv run ruff format app/ tests/
git add app/modules/tracking/services.py tests/test_tracking_services.py
git commit -m "feat(tracking): add cached order-route service"
```

---

## Task 4: Backend — route endpoint

**Files:**
- Modify: `back-end/app/modules/tracking/routes.py`
- Test: `back-end/tests/test_tracking_routes.py` (modify)

- [ ] **Step 1: Write the failing tests**

In `back-end/tests/test_tracking_routes.py`, add these imports at the top (after the existing imports):

```python
from app.core.config import settings
from app.modules.tracking import directions
from app.modules.tracking.directions import DirectionsResult
```

Then append these tests to the end of the file:

```python
async def test_get_order_route_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/orders/{_ORDER_ID}/route")
    assert resp.status_code == 401


async def test_get_order_route_happy_path(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_PLATAFORM", "test-key")

    async def fake_fetch(client, *, origin, destination, api_key):  # noqa: ANN001, ANN202
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
```

Note: the `redis_client` fixture flushes the test DB between tests, so the cache does not leak across tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd back-end && uv run pytest tests/test_tracking_routes.py -k route -v`
Expected: FAIL — the `/route` endpoint returns 404 (route not registered) instead of 401/200.

- [ ] **Step 3: Implement the endpoint**

In `back-end/app/modules/tracking/routes.py`, update the imports to add Redis, the redis dependency, and `RouteOut`:

```python
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Path

from app.core.redis_client import get_redis
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.tracking import services
from app.modules.tracking.schemas import (
    CourierLocationIn,
    ETAPredictionOut,
    OrderTrackingOut,
    RouteOut,
)
```

Then add the new route after `predict_eta` (end of file):

```python
@router.get("/{order_id}/route", response_model=RouteOut)
async def get_order_route(
    order_id: OrderId,
    user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> RouteOut:
    """Return the street route from the distribution center to the destination."""
    return await services.get_order_route(redis, user.id, order_id)
```

- [ ] **Step 4: Run the full tracking suite to verify it passes**

Run: `cd back-end && uv run pytest tests/test_tracking_routes.py tests/test_tracking_services.py tests/test_tracking_directions.py tests/test_tracking_schemas.py -v`
Expected: PASS (all).

- [ ] **Step 5: Lint and commit**

```bash
cd back-end && uv run ruff check app/ tests/ && uv run ruff format app/ tests/
git add app/modules/tracking/routes.py tests/test_tracking_routes.py
git commit -m "feat(tracking): add order-route endpoint"
```

---

## Task 5: Frontend — add google_maps_flutter dependency

**Files:**
- Modify: `front-end-flutter/pubspec.yaml:41-43`

- [ ] **Step 1: Add the dependency**

In `front-end-flutter/pubspec.yaml`, under `dependencies:` (near `http: ^1.6.0`), add:

```yaml
  google_maps_flutter: ^2.9.0
```

- [ ] **Step 2: Fetch packages**

Run: `cd front-end-flutter && flutter pub get`
Expected: resolves with `google_maps_flutter` added, no errors.

- [ ] **Step 3: Commit**

```bash
cd front-end-flutter && git add pubspec.yaml pubspec.lock
git commit -m "feat(order_tracking): add google_maps_flutter dependency"
```

---

## Task 6: Frontend — polyline decoder

**Files:**
- Create: `front-end-flutter/lib/features/order_tracking/data/polyline_codec.dart`
- Test: `front-end-flutter/test/features/order_tracking/polyline_codec_test.dart`

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/features/order_tracking/polyline_codec_test.dart`:

```dart
import 'package:edu_ia/features/order_tracking/data/polyline_codec.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

void main() {
  group('decodePolyline', () {
    test('decodes the canonical Google example', () {
      // From Google's encoded polyline algorithm documentation.
      final points = decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@');

      expect(points.length, 3);
      expect(points[0].latitude, closeTo(38.5, 1e-5));
      expect(points[0].longitude, closeTo(-120.2, 1e-5));
      expect(points[1].latitude, closeTo(40.7, 1e-5));
      expect(points[1].longitude, closeTo(-120.95, 1e-5));
      expect(points[2].latitude, closeTo(43.252, 1e-5));
      expect(points[2].longitude, closeTo(-126.453, 1e-5));
    });

    test('returns empty list for empty input', () {
      expect(decodePolyline(''), isEmpty);
    });
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/polyline_codec_test.dart`
Expected: FAIL — `Error: Couldn't resolve the package 'polyline_codec'` / file not found.

- [ ] **Step 3: Implement the decoder**

Create `front-end-flutter/lib/features/order_tracking/data/polyline_codec.dart`:

```dart
import 'package:google_maps_flutter/google_maps_flutter.dart';

/// Decodes a Google "encoded polyline" string into a list of [LatLng].
///
/// Implements the standard algorithm
/// (https://developers.google.com/maps/documentation/utilities/polylinealgorithm)
/// inline to avoid pulling an extra package for ~20 lines of logic.
List<LatLng> decodePolyline(String encoded) {
  final points = <LatLng>[];
  int index = 0;
  int lat = 0;
  int lng = 0;

  while (index < encoded.length) {
    lat += _nextDelta(encoded, () => index, (v) => index = v);
    lng += _nextDelta(encoded, () => index, (v) => index = v);
    points.add(LatLng(lat / 1e5, lng / 1e5));
  }
  return points;
}

/// Reads one zig-zag-encoded varint starting at the current index, advancing
/// it via [setIndex], and returns the signed delta.
int _nextDelta(String encoded, int Function() getIndex, void Function(int) setIndex) {
  int index = getIndex();
  int shift = 0;
  int result = 0;
  int byte;
  do {
    byte = encoded.codeUnitAt(index++) - 63;
    result |= (byte & 0x1f) << shift;
    shift += 5;
  } while (byte >= 0x20);
  setIndex(index);
  return (result & 1) != 0 ? ~(result >> 1) : (result >> 1);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/polyline_codec_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Analyze and commit**

```bash
cd front-end-flutter && flutter analyze lib/features/order_tracking/data/polyline_codec.dart
git add lib/features/order_tracking/data/polyline_codec.dart test/features/order_tracking/polyline_codec_test.dart
git commit -m "feat(order_tracking): add polyline decoder"
```

---

## Task 7: Frontend — OrderRoute model

**Files:**
- Create: `front-end-flutter/lib/features/order_tracking/domain/order_route.dart`
- Test: `front-end-flutter/test/features/order_tracking/order_route_test.dart`

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/features/order_tracking/order_route_test.dart`:

```dart
import 'package:edu_ia/features/order_tracking/domain/order_route.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('OrderRoute.fromJson parses the backend contract', () {
    final route = OrderRoute.fromJson({
      'origin': {
        'label': 'Centro de Distribuição',
        'latitude': -23.3558,
        'longitude': -46.8769,
      },
      'destination': {
        'label': 'Endereço de entrega',
        'latitude': -23.561414,
        'longitude': -46.655881,
      },
      'polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
      'distance_text': '32 km',
      'distance_km': 32.4,
      'duration_text': '48 min',
      'duration_minutes': 48,
    });

    expect(route.origin.label, 'Centro de Distribuição');
    expect(route.origin.latitude, -23.3558);
    expect(route.destination.longitude, -46.655881);
    expect(route.distanceText, '32 km');
    expect(route.durationMinutes, 48);
    // Decoded lazily from the encoded polyline.
    expect(route.polylinePoints.length, 3);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/order_route_test.dart`
Expected: FAIL — file `order_route.dart` not found.

- [ ] **Step 3: Implement the model**

Create `front-end-flutter/lib/features/order_tracking/domain/order_route.dart`:

```dart
import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../data/polyline_codec.dart';

/// A named endpoint of the delivery route (origin or destination).
class RoutePoint {
  final String label;
  final double latitude;
  final double longitude;

  const RoutePoint({
    required this.label,
    required this.latitude,
    required this.longitude,
  });

  factory RoutePoint.fromJson(Map<String, dynamic> json) => RoutePoint(
    label: (json['label'] as String?) ?? '',
    latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
    longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
  );

  LatLng get latLng => LatLng(latitude, longitude);
}

/// Street route between the distribution center and the order destination,
/// mirroring the backend `RouteOut` schema (`GET /orders/{id}/route`).
class OrderRoute {
  final RoutePoint origin;
  final RoutePoint destination;
  final String polyline;
  final String distanceText;
  final double distanceKm;
  final String durationText;
  final int durationMinutes;

  const OrderRoute({
    required this.origin,
    required this.destination,
    required this.polyline,
    required this.distanceText,
    required this.distanceKm,
    required this.durationText,
    required this.durationMinutes,
  });

  factory OrderRoute.fromJson(Map<String, dynamic> json) => OrderRoute(
    origin: RoutePoint.fromJson(
      (json['origin'] as Map<String, dynamic>?) ?? const {},
    ),
    destination: RoutePoint.fromJson(
      (json['destination'] as Map<String, dynamic>?) ?? const {},
    ),
    polyline: (json['polyline'] as String?) ?? '',
    distanceText: (json['distance_text'] as String?) ?? '',
    distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
    durationText: (json['duration_text'] as String?) ?? '',
    durationMinutes: (json['duration_minutes'] as int?) ?? 0,
  );

  /// The route geometry, decoded from the encoded [polyline].
  List<LatLng> get polylinePoints => decodePolyline(polyline);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/order_route_test.dart`
Expected: PASS.

- [ ] **Step 5: Analyze and commit**

```bash
cd front-end-flutter && flutter analyze lib/features/order_tracking/domain/order_route.dart
git add lib/features/order_tracking/domain/order_route.dart test/features/order_tracking/order_route_test.dart
git commit -m "feat(order_tracking): add OrderRoute model"
```

---

## Task 8: Frontend — RouteService

**Files:**
- Create: `front-end-flutter/lib/features/order_tracking/data/route_service.dart`
- Test: `front-end-flutter/test/features/order_tracking/route_service_test.dart`

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/features/order_tracking/route_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/order_tracking/data/route_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _body = {
  'origin': {'label': 'Centro de Distribuição', 'latitude': -23.3, 'longitude': -46.8},
  'destination': {'label': 'Endereço de entrega', 'latitude': -23.5, 'longitude': -46.6},
  'polyline': 'enc',
  'distance_text': '32 km',
  'distance_km': 32.0,
  'duration_text': '48 min',
  'duration_minutes': 48,
};

void main() {
  test('fetchRoute parses a 200 response and sends the bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_body), 200);
    });

    final service = RouteService(client: client, tokenStore: _FakeTokenStore());
    final route = await service.fetchRoute('ED-99420');

    expect(route.polyline, 'enc');
    expect(route.origin.label, 'Centro de Distribuição');
    expect(captured.headers['Authorization'], 'Bearer fake-token');
    expect(captured.url.path, endsWith('/orders/ED-99420/route'));
  });

  test('fetchRoute throws RouteException on non-200', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service = RouteService(client: client, tokenStore: _FakeTokenStore());

    expect(() => service.fetchRoute('ED-99420'), throwsA(isA<RouteException>()));
  });
}
```

(If `TokenStore` cannot be subclassed this way, this test will surface it; the `OrderService` accepts an injected `TokenStore`, so the same pattern applies.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/route_service_test.dart`
Expected: FAIL — `route_service.dart` not found.

- [ ] **Step 3: Implement the service**

Create `front-end-flutter/lib/features/order_tracking/data/route_service.dart`:

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/order_route.dart';

/// Lançada quando a busca da rota do mapa falha; carrega mensagem amigável.
class RouteException implements Exception {
  RouteException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP para a rota do pedido no mapa
/// (`GET /orders/{id}/route`, resposta JSON `RouteOut`).
///
/// Mesmo padrão do [OrderService]: consome a API real por padrão; injete
/// `useMock: true` para desenvolver a tela do mapa sem backend/chave.
class RouteService {
  RouteService({
    http.Client? client,
    TokenStore? tokenStore,
    this.useMock = false,
  }) : _client = client ?? http.Client(),
       _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Quando `true`, retorna uma rota mockada em vez de chamar o backend.
  final bool useMock;

  Future<OrderRoute> fetchRoute(String orderId) {
    return useMock ? _fetchMock(orderId) : _fetchRemote(orderId);
  }

  Future<OrderRoute> _fetchRemote(String orderId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/orders/$orderId/route');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on RouteException {
      rethrow;
    } on Exception {
      throw RouteException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw RouteException('Rota não encontrada para este pedido');
    }
    if (res.statusCode != 200) {
      throw RouteException('Falha ao carregar o mapa (${res.statusCode})');
    }
    return OrderRoute.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw RouteException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }

  // --- Mock temporário ------------------------------------------------------

  Future<OrderRoute> _fetchMock(String orderId) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    return OrderRoute.fromJson({
      'origin': {
        'label': 'Centro de Distribuição',
        'latitude': -23.3558,
        'longitude': -46.8769,
      },
      'destination': {
        'label': 'Endereço de entrega',
        'latitude': -23.561414,
        'longitude': -46.655881,
      },
      'polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
      'distance_text': '32 km',
      'distance_km': 32.0,
      'duration_text': '48 min',
      'duration_minutes': 48,
    });
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/route_service_test.dart`
Expected: PASS (2 tests). If `_FakeTokenStore` fails to compile because `TokenStore` methods are not overridable, instead pass a real `TokenStore` and assert only on the URL/status behavior using a token-less path — but the injected-client pattern from `OrderService` should make the subclass work.

- [ ] **Step 5: Analyze and commit**

```bash
cd front-end-flutter && flutter analyze lib/features/order_tracking/data/route_service.dart
git add lib/features/order_tracking/data/route_service.dart test/features/order_tracking/route_service_test.dart
git commit -m "feat(order_tracking): add RouteService client"
```

---

## Task 9: Frontend — RouteProvider state machine

**Files:**
- Create: `front-end-flutter/lib/features/order_tracking/presentation/route_provider.dart`
- Test: `front-end-flutter/test/features/order_tracking/route_provider_test.dart`

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/features/order_tracking/route_provider_test.dart`:

```dart
import 'package:edu_ia/features/order_tracking/data/route_service.dart';
import 'package:edu_ia/features/order_tracking/presentation/route_provider.dart';
import 'package:flutter_test/flutter_test.dart';

class _OkService extends RouteService {
  _OkService() : super(useMock: true);
}

class _FailingService extends RouteService {
  _FailingService() : super();
  @override
  Future<dynamic> fetchRoute(String orderId) async =>
      throw RouteException('boom');
}

void main() {
  test('load() reaches success with a route', () async {
    final provider = RouteProvider(service: _OkService());
    await provider.load('ED-1');

    expect(provider.state, RouteViewState.success);
    expect(provider.route, isNotNull);
    expect(provider.route!.polylinePoints, isNotEmpty);
  });

  test('load() maps RouteException to the error state', () async {
    final provider = RouteProvider(service: _FailingService());
    await provider.load('ED-1');

    expect(provider.state, RouteViewState.error);
    expect(provider.errorMessage, 'boom');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/route_provider_test.dart`
Expected: FAIL — `route_provider.dart` not found.

- [ ] **Step 3: Implement the provider**

Create `front-end-flutter/lib/features/order_tracking/presentation/route_provider.dart`:

```dart
import 'package:flutter/foundation.dart';

import '../data/route_service.dart';
import '../domain/order_route.dart';

/// Estados da requisição da rota do mapa, consumidos pela tela do mapa.
enum RouteViewState { loading, success, error }

/// Gerencia o estado da Tela do Mapa do Pedido. Espelha o [OrderProvider]:
/// a View observa [state]/[route]/[errorMessage] e dispara [load]/[retry].
class RouteProvider extends ChangeNotifier {
  RouteProvider({RouteService? service}) : _service = service ?? RouteService();

  final RouteService _service;

  RouteViewState _state = RouteViewState.loading;
  RouteViewState get state => _state;

  OrderRoute? _route;
  OrderRoute? get route => _route;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  String? _orderId;

  Future<void> load(String orderId) async {
    _orderId = orderId;
    _state = RouteViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _route = await _service.fetchRoute(orderId);
      _state = RouteViewState.success;
    } on RouteException catch (e) {
      _errorMessage = e.message;
      _state = RouteViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = RouteViewState.error;
    }
    notifyListeners();
  }

  Future<void> retry() async {
    final id = _orderId;
    if (id == null) return;
    await load(id);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/route_provider_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Analyze and commit**

```bash
cd front-end-flutter && flutter analyze lib/features/order_tracking/presentation/route_provider.dart
git add lib/features/order_tracking/presentation/route_provider.dart test/features/order_tracking/route_provider_test.dart
git commit -m "feat(order_tracking): add RouteProvider state machine"
```

---

## Task 10: Frontend — map screen, route registration, and button wiring

**Files:**
- Create: `front-end-flutter/lib/features/order_tracking/presentation/order_map_screen.dart`
- Modify: `front-end-flutter/lib/features/order_tracking/presentation/order_tracking_screen.dart:150`
- Modify: `front-end-flutter/lib/main.dart:84`

- [ ] **Step 1: Implement the map screen**

Create `front-end-flutter/lib/features/order_tracking/presentation/order_map_screen.dart`:

```dart
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/order_route.dart';
import 'route_provider.dart';
import 'widgets/order_error_view.dart';

/// Tela do mapa: rota real entre o Centro de Distribuição e o destino.
///
/// Recebe o id do pedido via `Navigator.pushNamed(arguments: '<id>')`,
/// delega o estado ao [RouteProvider] e renderiza o [GoogleMap] no sucesso.
class OrderMapScreen extends StatelessWidget {
  const OrderMapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final orderId =
        ModalRoute.of(context)?.settings.arguments as String? ?? 'ED-99420';

    return ChangeNotifierProvider(
      create: (_) => RouteProvider()..load(orderId),
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: const Text(
            'Rota da Entrega',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 18),
          ),
          leading: IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
        ),
        body: Consumer<RouteProvider>(
          builder: (context, provider, _) {
            switch (provider.state) {
              case RouteViewState.loading:
                return const Center(
                  child: CircularProgressIndicator(color: AppColors.purple),
                );
              case RouteViewState.error:
                return OrderErrorView(
                  message: provider.errorMessage ?? 'Erro desconhecido.',
                  onRetry: provider.retry,
                );
              case RouteViewState.success:
                return _RouteMap(route: provider.route!);
            }
          },
        ),
      ),
    );
  }
}

class _RouteMap extends StatelessWidget {
  final OrderRoute route;

  const _RouteMap({required this.route});

  @override
  Widget build(BuildContext context) {
    final origin = route.origin.latLng;
    final destination = route.destination.latLng;

    return GoogleMap(
      initialCameraPosition: CameraPosition(target: origin, zoom: 10),
      onMapCreated: (controller) {
        controller.animateCamera(
          CameraUpdate.newLatLngBounds(_bounds(origin, destination), 64),
        );
      },
      markers: {
        Marker(
          markerId: const MarkerId('origin'),
          position: origin,
          infoWindow: InfoWindow(title: route.origin.label),
        ),
        Marker(
          markerId: const MarkerId('destination'),
          position: destination,
          infoWindow: InfoWindow(title: route.destination.label),
        ),
      },
      polylines: {
        Polyline(
          polylineId: const PolylineId('route'),
          color: AppColors.purple,
          width: 5,
          points: route.polylinePoints,
        ),
      },
    );
  }

  LatLngBounds _bounds(LatLng a, LatLng b) {
    return LatLngBounds(
      southwest: LatLng(math.min(a.latitude, b.latitude), math.min(a.longitude, b.longitude)),
      northeast: LatLng(math.max(a.latitude, b.latitude), math.max(a.longitude, b.longitude)),
    );
  }
}
```

- [ ] **Step 2: Register the named route**

In `front-end-flutter/lib/main.dart`, add the import near the other `order_tracking` import (line 8):

```dart
import 'package:edu_ia/features/order_tracking/presentation/order_map_screen.dart';
```

Then in the `routes:` map, immediately after the `'/order-tracking'` entry (line 84), add:

```dart
          '/order-map': (_) => const OrderMapScreen(),
```

- [ ] **Step 3: Wire the "Ver mapa" button**

In `front-end-flutter/lib/features/order_tracking/presentation/order_tracking_screen.dart`, replace line 150:

```dart
          LocationCard(location: order.location, onOpenMap: () {}),
```

with:

```dart
          LocationCard(
            location: order.location,
            onOpenMap: () => Navigator.pushNamed(
              context,
              '/order-map',
              arguments: order.id,
            ),
          ),
```

- [ ] **Step 4: Analyze**

Run: `cd front-end-flutter && flutter analyze lib/features/order_tracking/`
Expected: No issues (warnings about `GoogleMap` requiring platform setup are not analyzer errors).

- [ ] **Step 5: Commit**

```bash
cd front-end-flutter
git add lib/features/order_tracking/presentation/order_map_screen.dart lib/features/order_tracking/presentation/order_tracking_screen.dart lib/main.dart
git commit -m "feat(order_tracking): add map screen and wire ver mapa button"
```

---

## Task 11: Android Maps SDK key configuration (gitignored)

**Files:**
- Create: `front-end-flutter/android/secrets.properties`
- Modify: `front-end-flutter/android/app/build.gradle.kts`
- Modify: `front-end-flutter/android/app/src/main/AndroidManifest.xml`
- Modify: `front-end-flutter/.gitignore` (or repo root `.gitignore`)

- [ ] **Step 1: Create the gitignored secrets file**

Create `front-end-flutter/android/secrets.properties` (replace the placeholder with the same key value the backend uses in `back-end/.env`, or a separate Android-restricted key for production):

```properties
MAPS_API_KEY=PASTE_YOUR_MAPS_PLATFORM_KEY_HERE
```

- [ ] **Step 2: Ignore the secrets file in git**

Append to `front-end-flutter/.gitignore` (create it if absent):

```gitignore
android/secrets.properties
```

Verify it is ignored:

Run: `cd front-end-flutter && git check-ignore android/secrets.properties`
Expected: prints `android/secrets.properties` (i.e. it IS ignored).

- [ ] **Step 3: Load the key as a manifest placeholder**

In `front-end-flutter/android/app/build.gradle.kts`, near the top (after the existing imports/plugins block), add code to read the file, and inside `defaultConfig { ... }` inject the placeholder. Add this near the top of the file:

```kotlin
import java.util.Properties

val secretsProperties = Properties().apply {
    val f = rootProject.file("secrets.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
```

Then inside `android { defaultConfig { ... } }` (where `applicationId` is set, around line 28), add:

```kotlin
        manifestPlaceholders["MAPS_API_KEY"] =
            (secretsProperties["MAPS_API_KEY"] as String?) ?: ""
```

- [ ] **Step 4: Reference the placeholder in the manifest**

In `front-end-flutter/android/app/src/main/AndroidManifest.xml`, inside the `<application>` element (as a direct child, alongside the existing entries), add:

```xml
        <meta-data
            android:name="com.google.android.geo.API_KEY"
            android:value="${MAPS_API_KEY}" />
```

- [ ] **Step 5: Verify the build picks up the key**

Run: `cd front-end-flutter && flutter build apk --debug`
Expected: build succeeds. (If it fails for unrelated SDK reasons, at minimum `flutter analyze` must pass and the manifest merge must not error on `MAPS_API_KEY`.)

- [ ] **Step 6: Commit (only the committed files — never the secrets)**

```bash
cd front-end-flutter
git add android/app/build.gradle.kts android/app/src/main/AndroidManifest.xml .gitignore
git status   # confirm android/secrets.properties is NOT staged
git commit -m "feat(order_tracking): inject android maps sdk key from gitignored props"
```

---

## Task 12: (Optional) iOS Maps SDK key configuration

Only needed if building for iOS. The default `ApiConfig.baseUrl` targets the Android emulator, so this can be skipped for an Android-only run.

**Files:**
- Modify: `front-end-flutter/ios/Runner/AppDelegate.swift`

- [ ] **Step 1: Provide the key at startup**

In `front-end-flutter/ios/Runner/AppDelegate.swift`, add `import GoogleMaps` at the top and, inside `application(_:didFinishLaunchingWithOptions:)` before `GeneratedPluginRegistrant.register`, add:

```swift
    GMSServices.provideAPIKey(
      (Bundle.main.object(forInfoDictionaryKey: "MapsApiKey") as? String) ?? "")
```

Then add a `MapsApiKey` entry to `ios/Runner/Info.plist` whose value is supplied by a gitignored xcconfig (mirroring the Android approach). Document the chosen mechanism in a comment so it stays out of git.

- [ ] **Step 2: Commit**

```bash
cd front-end-flutter && git add ios/Runner/AppDelegate.swift
git commit -m "feat(order_tracking): provide ios maps sdk key at startup"
```

---

## Task 13: End-to-end verification

- [ ] **Step 1: Backend — run the full tracking suite**

Run: `cd back-end && uv run pytest tests/ -k tracking -v`
Expected: all tracking tests PASS.

- [ ] **Step 2: Frontend — run all order_tracking tests**

Run: `cd front-end-flutter && flutter test test/features/order_tracking/`
Expected: all PASS.

- [ ] **Step 3: Manual run**

Set `GOOGLE_MAPS_API_PLATAFORM` in `back-end/.env`, set `MAPS_API_KEY` in `android/secrets.properties`, then:

```bash
cd back-end && docker compose up -d
cd front-end-flutter && flutter run
```

Navigate to the order-tracking screen → tap **Ver mapa**. Expected: a Google Map opens with two markers (Centro de Distribuição and Endereço de entrega) and a purple route line following the streets between them.

- [ ] **Step 4: Confirm no secrets were committed**

Run: `git log --oneline -15 && git show --stat HEAD~13..HEAD | grep -iE "secrets.properties|\.env" || echo "no secret files in recent commits"`
Expected: prints `no secret files in recent commits`.

---

## Self-Review Notes

- **Spec coverage:** endpoint (Task 4), directions client (Task 2), Redis cache (Task 3), mocked coords (Task 3), single-key dev usage (Tasks 11–12 reuse the key; production split documented in spec/Task 11), polyline decoder own-impl (Task 6), map screen + button wiring (Task 10), `map_url`/`predict-eta` left untouched (not modified by any task). All covered.
- **Type consistency:** `DirectionsResult` fields (`polyline`, `distance_text`, `distance_km`, `duration_text`, `duration_minutes`) match `RouteOut` and `OrderRoute`. `fetch_directions` signature is identical across the client (Task 2), service call + monkeypatch (Task 3), and endpoint test monkeypatch (Task 4). `RouteViewState`/`load`/`retry` mirror `OrderProvider`. `decodePolyline` name matches between Task 6 and its consumer in Task 7.
- **Security:** every new endpoint keeps `Depends(get_current_user)`; `order_id` stays bounded; API key read from settings server-side and from gitignored native props client-side; no secret committed (Task 13 Step 4 verifies).
