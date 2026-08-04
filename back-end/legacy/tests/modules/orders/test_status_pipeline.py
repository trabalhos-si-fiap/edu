import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.notifications import services as notifications_services
from app.modules.orders import services, tasks
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order


async def _make_order(session: AsyncSession, user_id: uuid.UUID) -> Order:
    order = Order(user_id=user_id, payment_method="PIX", total=0)
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


@pytest.fixture(autouse=True)
def _mute_firebase(monkeypatch: pytest.MonkeyPatch) -> None:
    # notify_user persists then best-effort pushes; with no tokens the SDK is
    # never reached, but guard anyway so the suite never touches Firebase.
    monkeypatch.setattr(notifications_services.firebase, "send_multicast", lambda *a, **k: [])


class TestAdvanceOrderStatus:
    async def test_advances_one_step_and_notifies(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        order = await _make_order(db_session, created_user.id)

        advanced = await services.advance_order_status(db_session, order.id, OrderStatus.CONFIRMED)
        assert advanced is True

        await db_session.refresh(order)
        assert order.status == OrderStatus.CONFIRMED

        notes = await notifications_services.list_notifications(
            db_session, created_user.id, limit=20, offset=0
        )
        assert len(notes) == 1
        assert notes[0].title == "Pedido confirmado"
        assert notes[0].data == {
            "type": "order_status",
            "order_id": str(order.id),
            "status": "confirmed",
        }

    async def test_is_idempotent_on_replay(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        order = await _make_order(db_session, created_user.id)
        await services.advance_order_status(db_session, order.id, OrderStatus.CONFIRMED)

        # Replaying the same transition must no-op (no double notification).
        again = await services.advance_order_status(db_session, order.id, OrderStatus.CONFIRMED)
        assert again is False

        notes = await notifications_services.list_notifications(
            db_session, created_user.id, limit=20, offset=0
        )
        assert len(notes) == 1

    async def test_rejects_out_of_order_transition(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        order = await _make_order(db_session, created_user.id)
        # PENDING cannot jump straight to OUT_FOR_DELIVERY.
        advanced = await services.advance_order_status(
            db_session, order.id, OrderStatus.OUT_FOR_DELIVERY
        )
        assert advanced is False
        await db_session.refresh(order)
        assert order.status == OrderStatus.PENDING

    async def test_returns_false_for_unknown_order(self, db_session: AsyncSession) -> None:
        advanced = await services.advance_order_status(
            db_session, uuid.uuid4(), OrderStatus.CONFIRMED
        )
        assert advanced is False


class TestAdvanceOrderStatusTask:
    def test_has_time_limits_declared(self) -> None:
        # CLAUDE.md rules #4/#10: every Celery task must bound its runtime.
        assert tasks.advance_order_status_task.time_limit is not None
        assert tasks.advance_order_status_task.soft_time_limit is not None

    def test_schedules_next_only_when_advanced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        scheduled: list[tuple[tuple[str, str], int]] = []

        async def _advanced(*_args: object) -> bool:
            return True

        monkeypatch.setattr(tasks, "_advance", _advanced)
        monkeypatch.setattr(
            tasks.advance_order_status_task,
            "apply_async",
            lambda args, countdown: scheduled.append((args, countdown)),
        )

        result = tasks.advance_order_status_task(str(uuid.uuid4()), OrderStatus.CONFIRMED.value)
        assert result is True
        # CONFIRMED -> SEPARATING scheduled with a bounded delay.
        assert scheduled[0][0][1] == OrderStatus.SEPARATING.value
        assert 10 <= scheduled[0][1] <= 30

    def test_does_not_schedule_when_not_advanced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        scheduled: list[object] = []

        async def _not_advanced(*_args: object) -> bool:
            return False

        monkeypatch.setattr(tasks, "_advance", _not_advanced)
        monkeypatch.setattr(
            tasks.advance_order_status_task,
            "apply_async",
            lambda *a, **k: scheduled.append(a),
        )

        result = tasks.advance_order_status_task(str(uuid.uuid4()), OrderStatus.DELIVERED.value)
        assert result is False
        assert scheduled == []

    def test_terminal_status_does_not_schedule(self, monkeypatch: pytest.MonkeyPatch) -> None:
        scheduled: list[object] = []

        async def _advanced(*_args: object) -> bool:
            return True

        monkeypatch.setattr(tasks, "_advance", _advanced)
        monkeypatch.setattr(
            tasks.advance_order_status_task,
            "apply_async",
            lambda *a, **k: scheduled.append(a),
        )

        result = tasks.advance_order_status_task(str(uuid.uuid4()), OrderStatus.DELIVERED.value)
        assert result is True
        assert scheduled == []


class TestCheckoutTriggersPipeline:
    async def test_checkout_kicks_off_status_pipeline(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        filled_cart: list[object],
        captured_pipeline_kickoffs: list[tuple[str, str]],
    ) -> None:
        r = await client.post("/api/orders", headers=auth_headers)
        assert r.status_code == 201, r.text

        order_id = r.json()["id"]
        # The newly created order is PENDING and the pipeline is told to move it
        # to CONFIRMED.
        assert r.json()["status"] == "pending"
        assert captured_pipeline_kickoffs == [(order_id, OrderStatus.CONFIRMED.value)]
