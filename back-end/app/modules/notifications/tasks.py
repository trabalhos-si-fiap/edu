import asyncio
import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery_app import celery_app
from app.core.config import settings
from app.modules.notifications import services


async def _send(user_id: uuid.UUID, title: str, body: str, data: dict[str, str] | None) -> int:
    # A fresh, pool-less engine per task run: Celery prefork workers reuse the
    # process across tasks, and asyncpg connections are bound to the event loop
    # that created them. asyncio.run() makes a new loop each call, so sharing
    # the module-level engine would raise "attached to a different loop".
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await services.send_push_to_user(session, user_id, title, body, data)
    finally:
        await engine.dispose()


@celery_app.task(
    name="notifications.send_push_to_user",
    time_limit=settings.FCM_SEND_TIME_LIMIT,
    soft_time_limit=settings.FCM_SEND_SOFT_TIME_LIMIT,
)
def send_push_to_user_task(
    user_id: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Fire-and-forget push to all of a user's devices.

    Idempotent: re-running only re-delivers the same notification and purges
    dead tokens; it never mutates token ownership. ``user_id`` is passed as a
    string because Celery serialises arguments as JSON.
    """
    sent = asyncio.run(_send(uuid.UUID(user_id), title, body, data))
    logger.info("notifications: push task delivered count={} user={}", sent, user_id)
    return sent
