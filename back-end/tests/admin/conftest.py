from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.auth.security import hash_password


async def _make_user(
    session: AsyncSession,
    *,
    email: str,
    is_admin: bool,
    is_active: bool = True,
    password: str = "Secret!1",
) -> User:
    user = User(
        name="Admin User",
        email=email,
        phone="11999998888",
        birth_date=date(1995, 6, 15),
        education_level="Vestibulando",
        password_hash=hash_password(password),
        is_active=is_active,
        is_verified=True,
        is_admin=is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="admin@example.com", is_admin=True)


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="user@example.com", is_admin=False)


@pytest.fixture
async def inactive_admin(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="ghost@example.com", is_admin=True, is_active=False)
