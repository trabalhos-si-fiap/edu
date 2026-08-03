"""Maps a persisted :class:`~app.modules.orders.models.Order` onto the tracking
payload the Flutter screen renders.

This is the single place that turns the real, forward-only order status into the
timeline the app shows. It is a pure function (no I/O) so the status->timeline
logic is unit-testable without a database. The service layer owns loading the
order and enforcing ownership; this owns the shape.
"""

from datetime import datetime, timedelta

from app.modules.orders.enums import OrderStatus
from app.modules.orders.lifecycle import ORDER_FLOW
from app.modules.orders.models import Order
from app.modules.tracking.enums import TrackingStepStatus
from app.modules.tracking.schemas import (
    KitItemOut,
    OrderTrackingOut,
    TrackingLocationOut,
    TrackingStepOut,
)

_CARRIER = "Logistics Intel Express"
# Rough delivery window shown while the order is still in flight. The demo
# pipeline finishes in minutes; in production this comes from the logistics ETA.
_DELIVERY_WINDOW = timedelta(days=4)

# The four visible timeline steps, in progression order. PENDING is transient
# (the pipeline leaves it within seconds) so it is collapsed onto CONFIRMED.
# Each `code` is the stable id the app maps to an icon (tracking_timeline.dart).
_STEPS: tuple[tuple[str, str, OrderStatus], ...] = (
    ("confirmed", "Confirmado", OrderStatus.CONFIRMED),
    ("separating", "Em separação", OrderStatus.SEPARATING),
    ("out_for_delivery", "Saiu para entrega", OrderStatus.OUT_FOR_DELIVERY),
    ("delivered", "Entregue", OrderStatus.DELIVERED),
)

# Headline + description shown at the top of the screen, per current status.
_COPY: dict[OrderStatus, tuple[str, str]] = {
    OrderStatus.PENDING: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    OrderStatus.CONFIRMED: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    OrderStatus.SEPARATING: (
        "Em separação",
        "Estamos separando os itens do seu pedido com carinho.",
    ),
    OrderStatus.OUT_FOR_DELIVERY: (
        "Saiu para entrega",
        "Seu pedido está a caminho do seu endereço. Chega já já!",
    ),
    OrderStatus.DELIVERED: (
        "Pedido entregue",
        "Seu pedido foi entregue. Bons estudos!",
    ),
}

# Last-known-location label per status. The city/state are derived from the
# order's delivery-address snapshot once it's out for delivery (see
# build_order_tracking); this dict only drives the location card's name text.
_LOCATION_NAME: dict[OrderStatus, str] = {
    OrderStatus.OUT_FOR_DELIVERY: "Em rota de entrega",
    OrderStatus.DELIVERED: "Entregue no endereço",
}
_DEFAULT_LOCATION_NAME = "Centro de Distribuição"


def _step_status(order_status: OrderStatus, step_status: OrderStatus) -> TrackingStepStatus:
    """Where a single timeline step sits relative to the order's real status."""
    if order_status == OrderStatus.DELIVERED:
        return TrackingStepStatus.DONE

    order_idx = ORDER_FLOW.index(order_status)
    step_idx = ORDER_FLOW.index(step_status)
    if step_idx < order_idx:
        return TrackingStepStatus.DONE
    if step_idx == order_idx:
        return TrackingStepStatus.CURRENT
    # PENDING (idx 0) has no visible step of its own: surface CONFIRMED as the
    # active one so the screen never shows an all-pending timeline.
    if order_idx == 0 and step_status == OrderStatus.CONFIRMED:
        return TrackingStepStatus.CURRENT
    return TrackingStepStatus.PENDING


def _step_timestamp(
    code: str,
    step_status: TrackingStepStatus,
    *,
    created_at: datetime,
    status_updated_at: datetime,
) -> datetime | None:
    """Real timestamps where we have them, ``None`` otherwise.

    We only persist the latest transition time (``status_updated_at``), so the
    active step shows that, and the first step is anchored to creation. Older
    intermediate steps have no recorded time and stay blank (the app hides them).
    """
    if step_status == TrackingStepStatus.CURRENT or code == "delivered":
        return status_updated_at
    if code == "confirmed":
        return created_at
    return None


def build_order_tracking(order: Order) -> OrderTrackingOut:
    """Build the tracking screen payload from a real order's current status."""
    status = OrderStatus(order.status)
    created_at = order.created_at
    # Defensive: pre-migration rows could be missing this; fall back to creation.
    status_updated_at = order.status_updated_at or created_at

    steps = []
    for code, title, step_order_status in _STEPS:
        step_status = _step_status(status, step_order_status)
        steps.append(
            TrackingStepOut(
                code=code,
                title=title,
                status=step_status,
                timestamp=_step_timestamp(
                    code,
                    step_status,
                    created_at=created_at,
                    status_updated_at=status_updated_at,
                ),
            )
        )

    headline, description = _COPY[status]
    estimated_arrival = (
        status_updated_at if status == OrderStatus.DELIVERED else created_at + _DELIVERY_WINDOW
    )

    # Once the parcel is out for delivery / delivered, the last-known location is
    # the destination city; before that it sits at the distribution center.
    at_destination = status in (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED)
    location_city = order.ship_city if (at_destination and order.ship_city) else "Cajamar"
    location_state = order.ship_state if (at_destination and order.ship_state) else "SP"

    return OrderTrackingOut(
        id=str(order.id),
        headline=headline,
        description=description,
        estimated_arrival=estimated_arrival,
        steps=steps,
        location=TrackingLocationOut(
            name=_LOCATION_NAME.get(status, _DEFAULT_LOCATION_NAME),
            city=location_city,
            state=location_state,
            updated_at=status_updated_at,
        ),
        kit=[KitItemOut(name=item.product_name) for item in order.items],
        carrier=_CARRIER,
        map_url=None,
    )
