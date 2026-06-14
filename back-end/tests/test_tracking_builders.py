"""Unit tests for the pure order -> tracking-payload builder.

No DB here: the builder takes an Order instance and returns the OrderTrackingOut
the Flutter screen consumes. We assert the timeline reflects the real status.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.tracking.builders import build_order_tracking
from app.modules.tracking.enums import TrackingStepStatus

_CREATED = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
_UPDATED = _CREATED + timedelta(minutes=2)

# The four visible timeline steps, in order. PENDING is collapsed onto CONFIRMED.
_STEP_CODES = ["confirmed", "separating", "out_for_delivery", "delivered"]


def _order(status: OrderStatus, *, items: int = 2) -> Order:
    return Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total=Decimal("100.00"),
        payment_method="pix",
        status=status.value,
        created_at=_CREATED,
        status_updated_at=_UPDATED,
        items=[
            OrderItem(
                product_id=uuid.uuid4(),
                product_name=f"Item {i}",
                unit_price=Decimal("50.00"),
                quantity=1,
            )
            for i in range(items)
        ],
    )


def _statuses(order: Order) -> dict[str, TrackingStepStatus]:
    payload = build_order_tracking(order)
    return {s.code: s.status for s in payload.steps}


def test_steps_always_cover_the_four_visible_stages() -> None:
    payload = build_order_tracking(_order(OrderStatus.CONFIRMED))
    assert [s.code for s in payload.steps] == _STEP_CODES


def test_pending_surfaces_confirmed_as_current() -> None:
    statuses = _statuses(_order(OrderStatus.PENDING))
    assert statuses["confirmed"] == TrackingStepStatus.CURRENT
    assert statuses["separating"] == TrackingStepStatus.PENDING
    assert statuses["delivered"] == TrackingStepStatus.PENDING


def test_separating_marks_confirmed_done_and_separating_current() -> None:
    statuses = _statuses(_order(OrderStatus.SEPARATING))
    assert statuses["confirmed"] == TrackingStepStatus.DONE
    assert statuses["separating"] == TrackingStepStatus.CURRENT
    assert statuses["out_for_delivery"] == TrackingStepStatus.PENDING


def test_out_for_delivery_is_current() -> None:
    statuses = _statuses(_order(OrderStatus.OUT_FOR_DELIVERY))
    assert statuses["separating"] == TrackingStepStatus.DONE
    assert statuses["out_for_delivery"] == TrackingStepStatus.CURRENT
    assert statuses["delivered"] == TrackingStepStatus.PENDING


def test_delivered_marks_every_step_done() -> None:
    statuses = _statuses(_order(OrderStatus.DELIVERED))
    assert all(s == TrackingStepStatus.DONE for s in statuses.values())


def test_kit_is_built_from_order_items() -> None:
    payload = build_order_tracking(_order(OrderStatus.SEPARATING, items=3))
    assert [k.name for k in payload.kit] == ["Item 0", "Item 1", "Item 2"]


def test_current_step_carries_the_status_timestamp() -> None:
    payload = build_order_tracking(_order(OrderStatus.OUT_FOR_DELIVERY))
    current = next(s for s in payload.steps if s.status == TrackingStepStatus.CURRENT)
    assert current.timestamp == _UPDATED


def test_payload_id_is_the_order_uuid() -> None:
    order = _order(OrderStatus.CONFIRMED)
    payload = build_order_tracking(order)
    assert payload.id == str(order.id)


@pytest.mark.parametrize("status", list(OrderStatus))
def test_exactly_one_current_step_unless_delivered(status: OrderStatus) -> None:
    payload = build_order_tracking(_order(status))
    currents = [s for s in payload.steps if s.status == TrackingStepStatus.CURRENT]
    if status == OrderStatus.DELIVERED:
        assert currents == []
    else:
        assert len(currents) == 1
