from app.modules.orders import lifecycle
from app.modules.orders.enums import OrderStatus


class TestNextStatus:
    def test_walks_the_flow_in_order(self) -> None:
        assert lifecycle.next_status(OrderStatus.PENDING) == OrderStatus.CONFIRMED
        assert lifecycle.next_status(OrderStatus.CONFIRMED) == OrderStatus.SEPARATING
        assert lifecycle.next_status(OrderStatus.SEPARATING) == OrderStatus.OUT_FOR_DELIVERY
        assert lifecycle.next_status(OrderStatus.OUT_FOR_DELIVERY) == OrderStatus.DELIVERED

    def test_delivered_is_terminal(self) -> None:
        assert lifecycle.next_status(OrderStatus.DELIVERED) is None


class TestCanAdvanceTo:
    def test_allows_only_the_immediate_successor(self) -> None:
        assert lifecycle.can_advance_to(OrderStatus.PENDING, OrderStatus.CONFIRMED)
        assert lifecycle.can_advance_to(OrderStatus.SEPARATING, OrderStatus.OUT_FOR_DELIVERY)

    def test_rejects_skipping_a_step(self) -> None:
        assert not lifecycle.can_advance_to(OrderStatus.PENDING, OrderStatus.SEPARATING)

    def test_rejects_going_backwards(self) -> None:
        assert not lifecycle.can_advance_to(OrderStatus.CONFIRMED, OrderStatus.PENDING)

    def test_rejects_re_applying_the_same_status(self) -> None:
        # A replay of the task that set CONFIRMED must be a no-op.
        assert not lifecycle.can_advance_to(OrderStatus.CONFIRMED, OrderStatus.CONFIRMED)

    def test_rejects_advancing_past_terminal(self) -> None:
        assert not lifecycle.can_advance_to(OrderStatus.DELIVERED, OrderStatus.DELIVERED)


class TestNotificationCopy:
    def test_every_status_after_pending_has_copy(self) -> None:
        for status in OrderStatus:
            if status is OrderStatus.PENDING:
                assert status not in lifecycle.STATUS_NOTIFICATION
            else:
                title, body = lifecycle.STATUS_NOTIFICATION[status]
                assert title and body
