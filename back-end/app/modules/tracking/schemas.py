import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.tracking.enums import OrderStatus, RouteStatus, TrafficLevel

# Geographic bounds used to reject impossible coordinates at the edge of the
# system (security rule #4 — every input is bounded).
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LNG_MIN, _LNG_MAX = -180.0, 180.0


class GeoPoint(BaseModel):
    """A single WGS-84 coordinate."""

    latitude: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(..., ge=_LNG_MIN, le=_LNG_MAX)


class CourierLocationIn(BaseModel):
    """Current position of the courier, sent by the mobile app to ask for an ETA."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        ge=_LAT_MIN,
        le=_LAT_MAX,
        description="Courier current latitude in decimal degrees.",
    )
    longitude: float = Field(
        ...,
        ge=_LNG_MIN,
        le=_LNG_MAX,
        description="Courier current longitude in decimal degrees.",
    )


class DeliveryAddress(BaseModel):
    """Destination where the order must be delivered."""

    label: str = Field(..., max_length=60)
    street: str = Field(..., max_length=160)
    number: str = Field(..., max_length=20)
    complement: str = Field(default="", max_length=80)
    district: str = Field(..., max_length=80)
    city: str = Field(..., max_length=80)
    state: str = Field(..., max_length=2)
    zip_code: str = Field(..., max_length=9)
    location: GeoPoint


class TrackingEvent(BaseModel):
    """A single entry in the order's tracking timeline."""

    status: OrderStatus
    description: str = Field(..., max_length=200)
    occurred_at: datetime


class OrderTrackingItem(BaseModel):
    """An item line as displayed on the tracking screen."""

    product_id: uuid.UUID
    product_name: str = Field(..., max_length=160)
    quantity: int = Field(..., ge=1)
    unit_price: Decimal
    image_url: str = Field(default="", max_length=512)

    @field_serializer("unit_price")
    def _price_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class OrderTrackingOut(BaseModel):
    """Full payload needed to render the order-tracking screen."""

    order_id: uuid.UUID
    current_status: OrderStatus
    total: Decimal
    courier_name: str = Field(..., max_length=120)
    items: list[OrderTrackingItem]
    events: list[TrackingEvent]
    destination: DeliveryAddress
    placed_at: datetime
    estimated_delivery_at: datetime | None = None

    @field_serializer("total")
    def _total_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class ETAPredictionOut(BaseModel):
    """Result of the route-prediction service for a courier position."""

    eta_minutes: int = Field(..., ge=0, description="Estimated minutes until arrival.")
    eta_text: str = Field(..., description='Human-friendly ETA, e.g. "15 min".')
    distance_km: float = Field(..., ge=0, description="Estimated travelled distance in km.")
    straight_line_distance_km: float = Field(
        ..., ge=0, description="Great-circle distance courier→destination in km."
    )
    average_speed_kmh: float = Field(..., gt=0)
    traffic_level: TrafficLevel
    route_status: RouteStatus
    courier_location: GeoPoint
    destination_location: GeoPoint
