import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


def _make_user(**overrides: object) -> User:
    data: dict[str, object] = {
        "name": "Maria Silva",
        "email": "maria@example.com",
        "phone": "11999998888",
        "birth_date": date(1995, 6, 15),
        "education_level": "Vestibulando",
        "password_hash": "$2b$12$dummyhashvaluenotreal000000000000000000000000000000000",
    }
    data.update(overrides)
    return User(**data)


def test_user_tablename_has_auth_prefix() -> None:
    assert User.__tablename__ == "auth_users"


async def test_user_can_be_persisted(db_session: AsyncSession) -> None:
    user = _make_user()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True
    assert user.is_verified is False
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_user_email_unique_constraint(db_session: AsyncSession) -> None:
    db_session.add(_make_user(email="dup@example.com"))
    await db_session.commit()

    db_session.add(_make_user(email="dup@example.com"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_user_education_level_check_constraint(db_session: AsyncSession) -> None:
    db_session.add(_make_user(education_level="Astronauta"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_user_id_is_uuidv7_time_ordered(db_session: AsyncSession) -> None:
    u1 = _make_user(email="a@example.com")
    db_session.add(u1)
    await db_session.flush()

    # Small delay so the millisecond component of UUIDv7 differs.
    await asyncio.sleep(0.005)

    u2 = _make_user(email="b@example.com")
    db_session.add(u2)
    await db_session.flush()

    # UUIDv7 sets version nibble to 7 in bits 76..79 of the 128-bit value.
    assert (u1.id.int >> 76) & 0xF == 7
    assert (u2.id.int >> 76) & 0xF == 7
    # Time-ordered: the later-generated UUID sorts greater.
    assert u2.id.int > u1.id.int
