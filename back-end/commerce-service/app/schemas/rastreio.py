"""Schemas do rastreio de pedido — o objeto que a tela do app renderiza.

Espelham, campo a campo, o JSON que `OrderModel.fromJson` (Flutter) espera
(`front-end-flutter/lib/features/order_tracking/domain/order_model.dart`).
O contrato é do app, não do backend — o backend só o cumpre.

A C8 trouxe só o que ela usava: `TrackingStepStatus`, `TrackingStepOut`,
`TrackingLocationOut`, `KitItemOut` e `OrderTrackingOut` — de propósito, para
não embarcar schema sem consumidor. Os schemas de rota/ETA do legacy
(`RoutePoint`, `RouteOut`, `GeoPoint`, `CourierLocationIn`, `ETAPredictionOut`,
e os enums `TrafficLevel`/`RouteStatus`) são desta task (C9), que os
acrescenta abaixo, agora com consumidor: `GET /orders/{id}/route` e
`POST /orders/{id}/predict-eta`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Limites geográficos usados para rejeitar coordenadas impossíveis na borda
# do sistema (regra 4 do CLAUDE.md — todo input tem limite).
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LNG_MIN, _LNG_MAX = -180.0, 180.0


class TrackingStepStatus(StrEnum):
    """Estado de cada passo da timeline do rastreio (espelha o app)."""

    DONE = "done"
    CURRENT = "current"
    PENDING = "pending"


class TrackingStepOut(BaseModel):
    """Um passo do progresso do pedido (ex.: Confirmado, Em separação)."""

    code: str = Field(
        ..., max_length=40, description="Id estável do passo, usado pelo app para o ícone."
    )
    title: str = Field(..., max_length=80)
    status: TrackingStepStatus
    timestamp: datetime | None = None


class TrackingLocationOut(BaseModel):
    """Última localização conhecida do pedido."""

    name: str = Field(..., max_length=120)
    # 120, não 80: bate com `Order.ship_city` (app/models/pedido.py,
    # `String(120)`), a coluna que alimenta este campo — achado 5 da
    # revisão da task C8. Com 80, uma cidade de 81-120 caracteres era
    # armazenável no pedido e não serializável aqui, e o rastreio desse
    # pedido estourava 500. O legacy tem o mesmo mismatch (80 vs. 120 na
    # coluna equivalente); aqui foi corrigido, não copiado.
    city: str = Field(..., max_length=120)
    state: str = Field(..., max_length=2)
    updated_at: datetime | None = None


class KitItemOut(BaseModel):
    """Um item incluído no pedido/kit."""

    name: str = Field(..., max_length=160)
    subtitle: str | None = Field(default=None, max_length=160)


class OrderTrackingOut(BaseModel):
    """Payload completo renderizado pela tela de rastreio.

    `map_url` fica sempre `None` hoje: medido, o legacy
    (`app/modules/tracking/builders.py:159`) também nunca a preenche — e o
    Flutter já lê a chave com cast null-safe e default. O campo existe para
    o dia em que algo a popular, não porque há um preenchedor agora.
    """

    id: str = Field(..., max_length=64)
    headline: str = Field(..., max_length=120)
    description: str = Field(..., max_length=400)
    estimated_arrival: datetime
    steps: list[TrackingStepOut]
    location: TrackingLocationOut
    kit: list[KitItemOut]
    carrier: str = Field(..., max_length=120)
    map_url: str | None = Field(default=None, max_length=512)


# --- Rota no mapa (GET /orders/{id}/route) -----------------------------------


class TrafficLevel(StrEnum):
    """Congestionamento estimado na rota do entregador."""

    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


class RouteStatus(StrEnum):
    """Onde o entregador está em relação ao destino."""

    EN_ROUTE = "en_route"
    NEARBY = "nearby"
    ARRIVED = "arrived"


class RoutePoint(BaseModel):
    """Um extremo nomeado da rota de entrega (origem ou destino)."""

    label: str = Field(..., max_length=120)
    latitude: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(..., ge=_LNG_MIN, le=_LNG_MAX)


class RouteOut(BaseModel):
    """Rota de rua entre o centro de distribuição e o destino do pedido."""

    origin: RoutePoint
    destination: RoutePoint
    polyline: str = Field(..., description="Google overview_polyline (codificada).")
    distance_text: str = Field(..., max_length=40)
    distance_km: float = Field(..., ge=0)
    duration_text: str = Field(..., max_length=40)
    duration_minutes: int = Field(..., ge=0)

    @field_serializer("distance_km")
    def _round_distance(self, value: float) -> float:
        return round(value, 3)


# --- Previsão de rota (POST /orders/{id}/predict-eta) ------------------------


class GeoPoint(BaseModel):
    """Uma coordenada WGS-84 isolada."""

    latitude: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(..., ge=_LNG_MIN, le=_LNG_MAX)


class CourierLocationIn(BaseModel):
    """Posição atual do entregador, enviada pelo app para pedir a ETA."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        ge=_LAT_MIN,
        le=_LAT_MAX,
        description="Latitude atual do entregador, em graus decimais.",
    )
    longitude: float = Field(
        ...,
        ge=_LNG_MIN,
        le=_LNG_MAX,
        description="Longitude atual do entregador, em graus decimais.",
    )


class ETAPredictionOut(BaseModel):
    """Resultado do serviço de previsão de rota para uma posição do entregador."""

    eta_minutes: int = Field(..., ge=0, description="Minutos estimados até a chegada.")
    eta_text: str = Field(..., description='ETA em texto legível, ex.: "15 min".')
    distance_km: float = Field(..., ge=0, description="Distância estimada percorrida, em km.")
    straight_line_distance_km: float = Field(
        ..., ge=0, description="Distância em linha reta entregador->destino, em km."
    )
    average_speed_kmh: float = Field(..., gt=0)
    traffic_level: TrafficLevel
    route_status: RouteStatus
    courier_location: GeoPoint
    destination_location: GeoPoint

    @field_serializer("distance_km", "straight_line_distance_km", "average_speed_kmh")
    def _round(self, value: float) -> float:
        return round(value, 3)
