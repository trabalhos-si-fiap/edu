"""Unit tests for the pure route-prediction logic."""

import math

import pytest

from app.modules.tracking.enums import RouteStatus, TrafficLevel
from app.modules.tracking.routing import (
    estimate_route_status,
    estimate_traffic,
    format_eta,
    haversine_km,
    predict_route,
)

# Two reference points in São Paulo roughly 1.1 km apart.
_PAULISTA = (-23.561414, -46.655881)
_NEARBY = (-23.5615, -46.6660)  # ~1.0 km west on the same avenue


def test_haversine_zero_distance() -> None:
    assert haversine_km(_PAULISTA, _PAULISTA) == pytest.approx(0.0, abs=1e-6)


def test_haversine_is_symmetric() -> None:
    assert haversine_km(_PAULISTA, _NEARBY) == pytest.approx(haversine_km(_NEARBY, _PAULISTA))


def test_haversine_known_distance() -> None:
    # ~1 degree of latitude ≈ 111 km.
    assert haversine_km((0.0, 0.0), (1.0, 0.0)) == pytest.approx(111.19, abs=0.5)


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [
        (0.5, TrafficLevel.LIGHT),
        (2.0, TrafficLevel.LIGHT),
        (2.01, TrafficLevel.MODERATE),
        (7.0, TrafficLevel.MODERATE),
        (7.01, TrafficLevel.HEAVY),
        (50.0, TrafficLevel.HEAVY),
    ],
)
def test_estimate_traffic_bands(distance_km: float, expected: TrafficLevel) -> None:
    assert estimate_traffic(distance_km) is expected


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [
        (0.0, RouteStatus.ARRIVED),
        (0.05, RouteStatus.ARRIVED),
        (0.2, RouteStatus.NEARBY),
        (0.5, RouteStatus.NEARBY),
        (3.0, RouteStatus.EN_ROUTE),
    ],
)
def test_estimate_route_status(distance_km: float, expected: RouteStatus) -> None:
    assert estimate_route_status(distance_km) is expected


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (0, "chegando"),
        (5, "5 min"),
        (59, "59 min"),
        (60, "1 h"),
        (75, "1 h 15 min"),
    ],
)
def test_format_eta(minutes: int, expected: str) -> None:
    assert format_eta(minutes) == expected


def test_predict_route_applies_urban_factor() -> None:
    prediction = predict_route(_PAULISTA, _NEARBY, average_speed_kmh=30.0, urban_route_factor=1.4)
    straight = haversine_km(_PAULISTA, _NEARBY)
    assert prediction.straight_line_distance_km == pytest.approx(round(straight, 3))
    assert prediction.distance_km == pytest.approx(round(straight * 1.4, 3))
    assert prediction.eta_minutes >= 1


def test_predict_route_arrived_has_zero_eta() -> None:
    prediction = predict_route(_PAULISTA, _PAULISTA, average_speed_kmh=30.0, urban_route_factor=1.4)
    assert prediction.route_status is RouteStatus.ARRIVED
    assert prediction.eta_minutes == 0
    assert prediction.eta_text == "chegando"


def test_predict_route_heavy_traffic_slows_eta() -> None:
    # Same distance, but heavy traffic must never produce a faster ETA than light.
    far = (-23.50, -46.60)  # several km away → heavy
    heavy = predict_route(_PAULISTA, far, average_speed_kmh=30.0, urban_route_factor=1.4)
    assert heavy.traffic_level is TrafficLevel.HEAVY
    assert heavy.effective_speed_kmh < 30.0


def test_predict_route_eta_grows_with_distance() -> None:
    close = predict_route(_PAULISTA, _NEARBY, average_speed_kmh=30.0, urban_route_factor=1.4)
    far = predict_route(_PAULISTA, (-23.50, -46.60), average_speed_kmh=30.0, urban_route_factor=1.4)
    assert far.eta_minutes > close.eta_minutes


@pytest.mark.parametrize("speed", [0.0, -10.0])
def test_predict_route_rejects_non_positive_speed(speed: float) -> None:
    with pytest.raises(ValueError, match="average_speed_kmh"):
        predict_route(_PAULISTA, _NEARBY, average_speed_kmh=speed, urban_route_factor=1.4)


def test_predict_route_rejects_factor_below_one() -> None:
    with pytest.raises(ValueError, match="urban_route_factor"):
        predict_route(_PAULISTA, _NEARBY, average_speed_kmh=30.0, urban_route_factor=0.9)


def test_eta_minutes_matches_manual_formula() -> None:
    prediction = predict_route(_PAULISTA, _NEARBY, average_speed_kmh=30.0, urban_route_factor=1.4)
    expected = math.ceil(prediction.distance_km / prediction.effective_speed_kmh * 60)
    assert prediction.eta_minutes == expected
