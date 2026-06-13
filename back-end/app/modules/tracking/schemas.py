from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.tracking.enums import RouteStatus, TrackingStepStatus, TrafficLevel

# Geographic bounds used to reject impossible coordinates at the edge of the
# system (security rule #4 — every input is bounded).
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LNG_MIN, _LNG_MAX = -180.0, 180.0


# --- Order tracking screen ---------------------------------------------------
# These mirror, field for field, the JSON the Flutter `OrderModel.fromJson`
# expects (lib/features/order_tracking/domain/order_model.dart). The contract
# is owned by the app; the backend conforms to it.


class TrackingStepOut(BaseModel):
    """A single step of the order progress (e.g. Processed, In transit)."""

    code: str = Field(..., max_length=40, description="Stable step id used by the app for icons.")
    title: str = Field(..., max_length=80)
    status: TrackingStepStatus
    timestamp: datetime | None = None


class TrackingLocationOut(BaseModel):
    """Last known location of the parcel."""

    name: str = Field(..., max_length=120)
    city: str = Field(..., max_length=80)
    state: str = Field(..., max_length=2)
    updated_at: datetime | None = None


class KitItemOut(BaseModel):
    """An item included in the order/kit."""

    name: str = Field(..., max_length=160)
    subtitle: str | None = Field(default=None, max_length=160)


class OrderTrackingOut(BaseModel):
    """Full payload rendered by the order-tracking screen."""

    id: str = Field(..., max_length=64)
    headline: str = Field(..., max_length=120)
    description: str = Field(..., max_length=400)
    estimated_arrival: datetime
    steps: list[TrackingStepOut]
    location: TrackingLocationOut
    kit: list[KitItemOut]
    carrier: str = Field(..., max_length=120)
    map_url: str | None = Field(default=None, max_length=512)


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


# --- Route prediction (POST /orders/{id}/predict-eta) ------------------------


class GeoPoint(BaseModel):
    """A single WGS-84 coordinate."""

    latitude: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(..., ge=_LNG_MIN, le=_LNG_MAX)


class CourierLocationIn(BaseModel):
    """Current position of the courier, sent by the app to ask for an ETA."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ..., ge=_LAT_MIN, le=_LAT_MAX, description="Courier current latitude in decimal degrees."
    )
    longitude: float = Field(
        ..., ge=_LNG_MIN, le=_LNG_MAX, description="Courier current longitude in decimal degrees."
    )


class ETAPredictionOut(BaseModel):
    """Result of the route-prediction service for a courier position."""

    eta_minutes: int = Field(..., ge=0, description="Estimated minutes until arrival.")
    eta_text: str = Field(..., description='Human-friendly ETA, e.g. "15 min".')
    distance_km: float = Field(..., ge=0, description="Estimated travelled distance in km.")
    straight_line_distance_km: float = Field(
        ..., ge=0, description="Great-circle distance courier->destination in km."
    )
    average_speed_kmh: float = Field(..., gt=0)
    traffic_level: TrafficLevel
    route_status: RouteStatus
    courier_location: GeoPoint
    destination_location: GeoPoint

    @field_serializer("distance_km", "straight_line_distance_km", "average_speed_kmh")
    def _round(self, value: float) -> float:
        return round(value, 3)
