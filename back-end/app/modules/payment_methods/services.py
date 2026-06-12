import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment_methods.exceptions import PaymentMethodNotFound
from app.modules.payment_methods.models import PaymentMethod
from app.modules.payment_methods.schemas import PaymentMethodIn, PaymentMethodPatch


async def list_methods(session: AsyncSession, user_id: uuid.UUID) -> list[PaymentMethod]:
    stmt = (
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user_id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_method(
    session: AsyncSession, user_id: uuid.UUID, method_id: uuid.UUID
) -> PaymentMethod:
    stmt = select(PaymentMethod).where(
        PaymentMethod.id == method_id, PaymentMethod.user_id == user_id
    )
    method = (await session.execute(stmt)).scalar_one_or_none()
    if method is None:
        raise PaymentMethodNotFound()
    return method


async def _clear_other_defaults(
    session: AsyncSession, user_id: uuid.UUID, keep_id: uuid.UUID | None
) -> None:
    stmt = (
        update(PaymentMethod)
        .where(PaymentMethod.user_id == user_id, PaymentMethod.is_default.is_(True))
        .values(is_default=False)
    )
    if keep_id is not None:
        stmt = stmt.where(PaymentMethod.id != keep_id)
    await session.execute(stmt)


async def create_method(
    session: AsyncSession, user_id: uuid.UUID, data: PaymentMethodIn
) -> PaymentMethod:
    method = PaymentMethod(
        user_id=user_id, type=data.type.value, **data.model_dump(exclude={"type"})
    )

    existing = await list_methods(session, user_id)
    if not existing:
        method.is_default = True

    if method.is_default:
        await _clear_other_defaults(session, user_id, keep_id=None)

    session.add(method)
    await session.commit()
    await session.refresh(method)
    return method


async def set_default(
    session: AsyncSession,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
    patch: PaymentMethodPatch,
) -> PaymentMethod:
    method = await get_method(session, user_id, method_id)
    if patch.is_default is True:
        await _clear_other_defaults(session, user_id, keep_id=method.id)
        method.is_default = True
    elif patch.is_default is False:
        method.is_default = False
    await session.commit()
    await session.refresh(method)
    return method


async def delete_method(
    session: AsyncSession, user_id: uuid.UUID, method_id: uuid.UUID
) -> None:
    method = await get_method(session, user_id, method_id)
    was_default = method.is_default
    await session.delete(method)
    await session.flush()

    # Promote the oldest remaining method to default so the user always has one.
    if was_default:
        remaining = await list_methods(session, user_id)
        if remaining:
            remaining[0].is_default = True
    await session.commit()
