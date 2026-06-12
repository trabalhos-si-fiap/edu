import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.support.models import SupportMessage


async def list_messages(session: AsyncSession, user_id: uuid.UUID) -> list[SupportMessage]:
    stmt = (
        select(SupportMessage)
        .where(SupportMessage.user_id == user_id)
        .order_by(SupportMessage.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def send_message(
    session: AsyncSession, user_id: uuid.UUID, body: str
) -> list[SupportMessage]:
    message = SupportMessage(user_id=user_id, sender="user", body=body)
    session.add(message)
    await session.commit()
    logger.info("support: message sent id={} user={}", message.id, user_id)
    return await list_messages(session, user_id)
