import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.notifications import services
from app.modules.notifications.exceptions import DeviceTokenNotFound
from app.modules.notifications.models import DeviceToken
from app.modules.notifications.schemas import DevicePlatform, DeviceTokenIn


def make_token_in(**overrides: object) -> DeviceTokenIn:
    base: dict[str, object] = {"token": "fcm-token-abc", "platform": DevicePlatform.ANDROID}
    base.update(overrides)
    return DeviceTokenIn(**base)


class TestRegisterDeviceToken:
    async def test_creates_new_token(self, db_session: AsyncSession, created_user: User) -> None:
        device = await services.register_device_token(db_session, created_user.id, make_token_in())
        assert device.token == "fcm-token-abc"
        assert device.user_id == created_user.id
        assert device.platform == "android"

    async def test_is_idempotent_for_same_user_and_token(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        first = await services.register_device_token(db_session, created_user.id, make_token_in())
        second = await services.register_device_token(db_session, created_user.id, make_token_in())
        assert first.id == second.id

        rows = (
            (
                await db_session.execute(
                    select(DeviceToken).where(DeviceToken.token == "fcm-token-abc")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    async def test_reassigns_token_to_new_owner(
        self, db_session: AsyncSession, created_user: User, other_user: User
    ) -> None:
        # Same physical device, different user logs in: the token must follow
        # the new owner, never create a duplicate that leaks pushes to the old one.
        await services.register_device_token(db_session, created_user.id, make_token_in())
        moved = await services.register_device_token(db_session, other_user.id, make_token_in())

        assert moved.user_id == other_user.id
        rows = (
            (
                await db_session.execute(
                    select(DeviceToken).where(DeviceToken.token == "fcm-token-abc")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


class TestListTokensForUser:
    async def test_returns_only_owner_tokens(
        self, db_session: AsyncSession, created_user: User, other_user: User
    ) -> None:
        await services.register_device_token(db_session, created_user.id, make_token_in(token="a"))
        await services.register_device_token(db_session, created_user.id, make_token_in(token="b"))
        await services.register_device_token(db_session, other_user.id, make_token_in(token="c"))

        tokens = await services.list_tokens_for_user(db_session, created_user.id)
        assert sorted(tokens) == ["a", "b"]


class TestDeleteToken:
    async def test_removes_owned_token(self, db_session: AsyncSession, created_user: User) -> None:
        await services.register_device_token(db_session, created_user.id, make_token_in())
        await services.delete_token(db_session, created_user.id, "fcm-token-abc")

        remaining = await services.list_tokens_for_user(db_session, created_user.id)
        assert remaining == []

    async def test_cannot_delete_token_owned_by_another_user(
        self, db_session: AsyncSession, created_user: User, other_user: User
    ) -> None:
        await services.register_device_token(db_session, created_user.id, make_token_in())
        with pytest.raises(DeviceTokenNotFound):
            await services.delete_token(db_session, other_user.id, "fcm-token-abc")

    async def test_delete_missing_token_raises(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        with pytest.raises(DeviceTokenNotFound):
            await services.delete_token(db_session, created_user.id, "nope")
