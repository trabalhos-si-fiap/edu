"""Testes unitários da matemática pura de previsão de rota (sem I/O).

Porte de `legacy/tests/test_tracking_routing.py` (task C9, arquivo
inteiro), sem adaptação de conteúdo: só os imports mudam — os enums
`TrafficLevel`/`RouteStatus` moram em `app.schemas.rastreio` (a C8 os
deixou de fora de propósito, por não terem consumidor ainda) e a função
pura mora em `app.services.rastreio_routing`, não em
`app.modules.tracking.routing`.

`predict_route` mantém a assinatura do legacy — `courier` e `destination`
posicionais, só `average_speed_kmh`/`urban_route_factor` keyword-only —
porque o Step 3 do brief manda copiar o arquivo "sem mudar a lógica" e é
essa a assinatura que os 13 testes abaixo (portados sem alteração) chamam.
"""

import math

import pytest

from app.schemas.rastreio import RouteStatus, TrafficLevel
from app.services.rastreio_routing import (
    estimate_route_status,
    estimate_traffic,
    format_eta,
    haversine_km,
    predict_route,
)

# Dois pontos de referência em São Paulo a ~1,1 km de distância.
_PAULISTA = (-23.561414, -46.655881)
_NEARBY = (-23.5615, -46.6660)  # ~1,0 km a oeste, na mesma avenida


def test_haversine_zero_distance() -> None:
    assert haversine_km(_PAULISTA, _PAULISTA) == pytest.approx(0.0, abs=1e-6)


def test_haversine_is_symmetric() -> None:
    assert haversine_km(_PAULISTA, _NEARBY) == pytest.approx(haversine_km(_NEARBY, _PAULISTA))


def test_haversine_known_distance() -> None:
    # ~1 grau de latitude ≈ 111 km.
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
    # Mesma distância, mas tráfego pesado nunca pode dar uma ETA mais rápida
    # que tráfego leve.
    far = (-23.50, -46.60)  # alguns km de distância → heavy
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
