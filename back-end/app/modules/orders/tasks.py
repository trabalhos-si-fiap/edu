import asyncio
import random
import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery_app import celery_app
from app.core.config import settings
from app.modules.orders import lifecycle, services
from app.modules.orders.enums import OrderStatus


async def _advance(order_id: uuid.UUID, to_status: OrderStatus) -> bool:
    # Fresh, pool-less engine per run: asyncio.run() creates a new event loop
    # each call and asyncpg connections are loop-bound (see notifications.tasks).
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await services.advance_order_status(session, order_id, to_status)
    finally:
        await engine.dispose()


def _schedule_next(order_id: str, current: OrderStatus) -> None:
    nxt = lifecycle.next_status(current)
    if nxt is None:
        return
    # Non-cryptographic: this only jitters the simulated delivery timing.
    delay = random.randint(  # noqa: S311
        settings.ORDER_STATUS_MIN_DELAY_SECONDS, settings.ORDER_STATUS_MAX_DELAY_SECONDS
    )
    advance_order_status_task.apply_async((order_id, nxt.value), countdown=delay)


@celery_app.task(
    name="orders.advance_order_status",
    time_limit=settings.ORDER_STATUS_TASK_TIME_LIMIT,
    soft_time_limit=settings.ORDER_STATUS_TASK_SOFT_TIME_LIMIT,
)
def advance_order_status_task(order_id: str, to_status: str) -> bool:
    """Advance one order to ``to_status``; on success schedule the next
    transition after a short randomized delay (simulated logistics timing).

    Idempotent: a replay that finds the order already at/after ``to_status``
    no-ops and does not re-schedule, so the timer chain can never fork.
    ``order_id`` is a string because Celery serialises arguments as JSON.
    """
    status = OrderStatus(to_status)
    advanced = asyncio.run(_advance(uuid.UUID(order_id), status))
    if advanced:
        logger.info("orders: status advanced order={} status={}", order_id, to_status)
        _schedule_next(order_id, status)
    return advanced
