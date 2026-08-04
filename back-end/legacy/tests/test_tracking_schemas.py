"""Schema-shape tests for the tracking route payload."""

import pytest

from app.modules.tracking.schemas import RouteOut, RoutePoint


# Override the session-scoped autouse fixture so this module does not need a
# live database connection (these are pure schema/serialisation tests).
@pytest.fixture(autouse=True)
async def _clean_tables() -> None:  # type: ignore[override]
    return None


def test_route_out_serializes_expected_keys_and_rounds_distance() -> None:
    payload = RouteOut(
        origin=RoutePoint(label="Centro de Distribuição", latitude=-23.3558, longitude=-46.8769),
        destination=RoutePoint(
            label="Endereço de entrega", latitude=-23.561414, longitude=-46.655881
        ),
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
