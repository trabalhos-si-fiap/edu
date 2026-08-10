"""Serviço local de previsão de rota.

Este módulo é um substituto de um provedor de roteirização de verdade
(Google Maps Directions, OSRM, …) — usado só por `predict-eta`, que ainda
não tem consumidor no app (ver `app/services/rastreio.py::_MOCK_DESTINATION`).
A ETA é estimada pela distância em linha reta (Haversine) entre o entregador
e o destino, corrigida por um *fator de rota urbana* que aproxima a
distância extra de ruas, curvas e desvios reais, e por uma penalidade de
trânsito aplicada à velocidade média.

Todas as funções aqui são puras e determinísticas — mesma entrada, mesma
saída — o que as torna trivialmente testáveis sem I/O. O nível de trânsito é
derivado da distância (quanto mais longa a rota, mais cruzamentos e avenidas
um entregador tende a cruzar); trocar isso por um feed ao vivo no futuro só
muda `estimate_traffic`, sem tocar no resto do pipeline.

Porte de `legacy/app/modules/tracking/routing.py` (task C9). Sem mudança de
lógica: só o import dos enums `TrafficLevel`/`RouteStatus`, que aqui moram
em `app.schemas.rastreio` (a C8 os deixou de fora de propósito, sem
consumidor até esta task).
"""

import math
from dataclasses import dataclass

from app.schemas.rastreio import RouteStatus, TrafficLevel

_EARTH_RADIUS_KM = 6371.0088

# Faixas de distância (em km de rota) usadas para classificar o congestionamento.
_LIGHT_TRAFFIC_MAX_KM = 2.0
_MODERATE_TRAFFIC_MAX_KM = 7.0

# Fração da velocidade média de fato alcançável em cada nível de trânsito.
_TRAFFIC_SPEED_FACTOR: dict[TrafficLevel, float] = {
    TrafficLevel.LIGHT: 1.0,
    TrafficLevel.MODERATE: 0.8,
    TrafficLevel.HEAVY: 0.6,
}

# Limiares de proximidade (em linha reta, km) para o estado entregador->destino.
_ARRIVED_MAX_KM = 0.05
_NEARBY_MAX_KM = 0.5


@dataclass(frozen=True)
class RoutePrediction:
    """Resultado de uma estimativa de rota, em tipos de domínio simples."""

    straight_line_distance_km: float
    distance_km: float
    eta_minutes: int
    eta_text: str
    effective_speed_kmh: float
    traffic_level: TrafficLevel
    route_status: RouteStatus


def haversine_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    """Distância em linha reta entre dois pontos `(lat, lng)`, em quilômetros.

    Usa a fórmula de Haversine sobre uma aproximação esférica da Terra, que é
    precisa o bastante frente ao erro que o fator de rota urbana já introduz.
    """
    lat1, lng1 = origin
    lat2, lng2 = destination

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


def estimate_traffic(distance_km: float) -> TrafficLevel:
    """Classifica o congestionamento a partir da distância da rota.

    Um trecho curto costuma ser leve; rotas mais longas cruzam mais avenidas
    e cruzamentos, então ficam progressivamente mais pesadas.
    """
    if distance_km <= _LIGHT_TRAFFIC_MAX_KM:
        return TrafficLevel.LIGHT
    if distance_km <= _MODERATE_TRAFFIC_MAX_KM:
        return TrafficLevel.MODERATE
    return TrafficLevel.HEAVY


def estimate_route_status(straight_line_distance_km: float) -> RouteStatus:
    """Mapeia a proximidade do entregador para um estado grosseiro da rota."""
    if straight_line_distance_km <= _ARRIVED_MAX_KM:
        return RouteStatus.ARRIVED
    if straight_line_distance_km <= _NEARBY_MAX_KM:
        return RouteStatus.NEARBY
    return RouteStatus.EN_ROUTE


def format_eta(minutes: int) -> str:
    """Renderiza uma contagem de minutos como texto legível (pt-BR)."""
    if minutes <= 0:
        return "chegando"
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"{hours} h"
    return f"{hours} h {rest} min"


def predict_route(
    courier: tuple[float, float],
    destination: tuple[float, float],
    *,
    average_speed_kmh: float,
    urban_route_factor: float,
) -> RoutePrediction:
    """Estima distância e ETA para um entregador indo até um destino.

    Passos:
        1. Distância em linha reta (Haversine) entregador->destino.
        2. Distância real da rota = linha reta * `urban_route_factor`.
        3. Nível de trânsito derivado da distância da rota.
        4. Velocidade efetiva = `average_speed_kmh` * penalidade de trânsito.
        5. ETA = distância da rota / velocidade efetiva.
    """
    if average_speed_kmh <= 0:
        raise ValueError("average_speed_kmh must be positive")
    if urban_route_factor < 1:
        raise ValueError("urban_route_factor must be >= 1")

    straight_line = haversine_km(courier, destination)
    route_distance = straight_line * urban_route_factor

    traffic = estimate_traffic(route_distance)
    effective_speed = average_speed_kmh * _TRAFFIC_SPEED_FACTOR[traffic]

    eta_minutes = math.ceil(route_distance / effective_speed * 60)
    route_status = estimate_route_status(straight_line)
    if route_status is RouteStatus.ARRIVED:
        eta_minutes = 0

    return RoutePrediction(
        straight_line_distance_km=round(straight_line, 3),
        distance_km=round(route_distance, 3),
        eta_minutes=eta_minutes,
        eta_text=format_eta(eta_minutes),
        effective_speed_kmh=round(effective_speed, 2),
        traffic_level=traffic,
        route_status=route_status,
    )
