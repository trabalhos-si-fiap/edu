"""Schemas do rastreio de pedido — o objeto que a tela do app renderiza.

Espelham, campo a campo, o JSON que `OrderModel.fromJson` (Flutter) espera
(`front-end-flutter/lib/features/order_tracking/domain/order_model.dart`).
O contrato é do app, não do backend — o backend só o cumpre.

Traz só o que a task C8 usa: `TrackingStepStatus`, `TrackingStepOut`,
`TrackingLocationOut`, `KitItemOut` e `OrderTrackingOut`. Os schemas de
rota/ETA do legacy (`RoutePoint`, `RouteOut`, `GeoPoint`, `CourierLocationIn`,
`ETAPredictionOut`, e os enums `TrafficLevel`/`RouteStatus`) são da task C9,
que os acrescenta neste mesmo arquivo — schema sem consumidor é código morto
que a revisão final teria que triar.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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
    city: str = Field(..., max_length=80)
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
