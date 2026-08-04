import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.addresses.exceptions import AddressNotFound
from app.modules.addresses.models import Address
from app.modules.addresses.schemas import AddressIn, AddressPatch


async def list_addresses(session: AsyncSession, user_id: uuid.UUID) -> list[Address]:
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_favorite.desc(), Address.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_address(
    session: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID
) -> Address:
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    address = (await session.execute(stmt)).scalar_one_or_none()
    if address is None:
        raise AddressNotFound()
    return address


async def _clear_other_favorites(
    session: AsyncSession, user_id: uuid.UUID, keep_id: uuid.UUID | None
) -> None:
    stmt = (
        update(Address)
        .where(Address.user_id == user_id, Address.is_favorite.is_(True))
        .values(is_favorite=False)
    )
    if keep_id is not None:
        stmt = stmt.where(Address.id != keep_id)
    await session.execute(stmt)


async def create_address(
    session: AsyncSession, user_id: uuid.UUID, data: AddressIn
) -> Address:
    address = Address(user_id=user_id, **data.model_dump())
    # First address becomes the favorite by default; otherwise honor the flag.
    existing = await list_addresses(session, user_id)
    if not existing:
        address.is_favorite = True

    if address.is_favorite:
        # Enforce single favorite per user within this transaction.
        await _clear_other_favorites(session, user_id, keep_id=None)

    session.add(address)
    await session.commit()
    await session.refresh(address)
    return address


async def update_address(
    session: AsyncSession,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
    patch: AddressPatch,
) -> Address:
    address = await get_address(session, user_id, address_id)

    changes = patch.model_dump(exclude_unset=True)
    if changes.get("is_favorite") is True:
        await _clear_other_favorites(session, user_id, keep_id=address.id)

    for field, value in changes.items():
        setattr(address, field, value)

    await session.commit()
    await session.refresh(address)
    return address


async def delete_address(
    session: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID
) -> None:
    address = await get_address(session, user_id, address_id)
    await session.delete(address)
    await session.commit()
