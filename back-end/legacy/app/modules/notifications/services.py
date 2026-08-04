import uuid

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import firebase
from app.modules.notifications.exceptions import DeviceTokenNotFound
from app.modules.notifications.models import DeviceToken, Notification
from app.modules.notifications.schemas import DeviceTokenIn


async def register_device_token(
    session: AsyncSession, user_id: uuid.UUID, data: DeviceTokenIn
) -> DeviceToken:
    """Idempotently register an FCM token for a user.

    A token is globally unique (one physical device). If it already exists we
    reassign it to the current user and refresh the platform — never create a
    duplicate that would keep delivering pushes to a previous owner.
    """
    stmt = select(DeviceToken).where(DeviceToken.token == data.token)
    device = (await session.execute(stmt)).scalar_one_or_none()

    if device is None:
        device = DeviceToken(
            user_id=user_id,
            token=data.token,
            platform=data.platform.value,
        )
        session.add(device)
    else:
        device.user_id = user_id
        device.platform = data.platform.value

    await session.commit()
    await session.refresh(device)
    logger.info("notifications: device token registered user={} id={}", user_id, device.id)
    return device


async def list_tokens_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    stmt = select(DeviceToken.token).where(DeviceToken.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def delete_token(session: AsyncSession, user_id: uuid.UUID, token: str) -> None:
    stmt = select(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user_id)
    device = (await session.execute(stmt)).scalar_one_or_none()
    if device is None:
        raise DeviceTokenNotFound()
    await session.delete(device)
    await session.commit()


async def _purge_tokens(session: AsyncSession, tokens: list[str]) -> None:
    if not tokens:
        return
    await session.execute(delete(DeviceToken).where(DeviceToken.token.in_(tokens)))
    await session.commit()


async def create_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> Notification:
    """Persist a single notification for a user's in-app history."""
    notification = Notification(user_id=user_id, title=title, body=body, data=data)
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def list_notifications(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


async def notify_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> Notification:
    """Record a notification and best-effort deliver it as a push.

    Persistence is unconditional: the in-app history must survive even when the
    user has no device token (or FCM delivery fails), so we always store first
    and only then attempt the push.
    """
    notification = await create_notification(session, user_id, title, body, data)
    await send_push_to_user(session, user_id, title, body, data)
    return notification


async def send_push_to_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Send a push to every device a user has registered.

    Returns the number of successful deliveries. Tokens FCM reports as
    permanently invalid are purged so dead tokens never accumulate. Idempotent
    at the data layer: re-sending only re-delivers, it never mutates ownership.
    """
    tokens = await list_tokens_for_user(session, user_id)
    if not tokens:
        logger.info("notifications: no device tokens for user={}, skipping push", user_id)
        return 0

    results = firebase.send_multicast(tokens, title=title, body=body, data=data)

    invalid = [r.token for r in results if r.invalid]
    await _purge_tokens(session, invalid)

    return sum(1 for r in results if r.success)
