from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import services
from app.modules.auth.exceptions import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidToken,
    UserInactive,
)
from app.modules.auth.schemas import RegisterIn
from app.modules.auth.security import create_access_token, create_refresh_token


def _register_data(**overrides: object) -> RegisterIn:
    base: dict[str, object] = {
        "name": "Maria Silva",
        "email": "maria@example.com",
        "phone": "11999998888",
        "birth_date": date(1995, 6, 15),
        "education_level": "Vestibulando",
        "password": "Secret!1",
    }
    base.update(overrides)
    return RegisterIn(**base)


class TestRegister:
    async def test_creates_user_and_hashes_password(self, db_session: AsyncSession) -> None:
        user = await services.register(db_session, _register_data())
        assert user.id is not None
        assert user.email == "maria@example.com"
        assert user.password_hash != "Secret!1"
        assert user.password_hash.startswith("$2")

    async def test_duplicate_email_raises(self, db_session: AsyncSession) -> None:
        await services.register(db_session, _register_data())
        with pytest.raises(EmailAlreadyRegistered):
            await services.register(db_session, _register_data())


class TestAuthenticate:
    async def test_success(self, db_session: AsyncSession) -> None:
        await services.register(db_session, _register_data())
        user = await services.authenticate(db_session, "maria@example.com", "Secret!1")
        assert user.email == "maria@example.com"

    async def test_wrong_password_raises_invalid_credentials(
        self, db_session: AsyncSession
    ) -> None:
        await services.register(db_session, _register_data())
        with pytest.raises(InvalidCredentials):
            await services.authenticate(db_session, "maria@example.com", "Wrong!1")

    async def test_missing_user_raises_invalid_credentials(self, db_session: AsyncSession) -> None:
        with pytest.raises(InvalidCredentials):
            await services.authenticate(db_session, "nobody@example.com", "Secret!1")

    async def test_email_matching_is_case_insensitive(self, db_session: AsyncSession) -> None:
        await services.register(db_session, _register_data())
        user = await services.authenticate(db_session, "MARIA@EXAMPLE.COM", "Secret!1")
        assert user.email == "maria@example.com"

    async def test_inactive_user_raises_user_inactive(self, db_session: AsyncSession) -> None:
        user = await services.register(db_session, _register_data())
        user.is_active = False
        await db_session.commit()
        with pytest.raises(UserInactive):
            await services.authenticate(db_session, "maria@example.com", "Secret!1")


class TestRefreshTokens:
    async def test_issues_new_access_and_refresh(self, db_session: AsyncSession) -> None:
        user = await services.register(db_session, _register_data())
        refresh = create_refresh_token(user.id)
        pair = await services.refresh_tokens(db_session, refresh)
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"

    async def test_access_token_is_rejected(self, db_session: AsyncSession) -> None:
        user = await services.register(db_session, _register_data())
        access = create_access_token(user.id)
        with pytest.raises(InvalidToken):
            await services.refresh_tokens(db_session, access)

    async def test_malformed_token_is_rejected(self, db_session: AsyncSession) -> None:
        with pytest.raises(InvalidToken):
            await services.refresh_tokens(db_session, "not.a.token")

    async def test_inactive_user_rejected(self, db_session: AsyncSession) -> None:
        user = await services.register(db_session, _register_data())
        user.is_active = False
        await db_session.commit()
        refresh = create_refresh_token(user.id)
        with pytest.raises(InvalidToken):
            await services.refresh_tokens(db_session, refresh)
