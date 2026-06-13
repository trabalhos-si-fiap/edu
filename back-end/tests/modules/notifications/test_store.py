from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.notifications import services


class TestCreateNotification:
    async def test_persists_notification(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        notification = await services.create_notification(
            db_session, created_user.id, "Título", "Corpo", {"k": "v"}
        )
        assert notification.id is not None
        assert notification.user_id == created_user.id
        assert notification.title == "Título"
        assert notification.body == "Corpo"
        assert notification.data == {"k": "v"}
        assert notification.read_at is None

    async def test_data_is_optional(self, db_session: AsyncSession, created_user: User) -> None:
        notification = await services.create_notification(
            db_session, created_user.id, "Oi", "corpo"
        )
        assert notification.data is None


class TestListNotifications:
    async def test_returns_only_owner_notifications(
        self, db_session: AsyncSession, created_user: User, other_user: User
    ) -> None:
        await services.create_notification(db_session, created_user.id, "mine", "x")
        await services.create_notification(db_session, other_user.id, "theirs", "x")

        items = await services.list_notifications(db_session, created_user.id, limit=20, offset=0)
        assert [n.title for n in items] == ["mine"]

    async def test_is_paginated_and_newest_first(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        for i in range(3):
            await services.create_notification(db_session, created_user.id, f"n{i}", "x")

        page = await services.list_notifications(db_session, created_user.id, limit=2, offset=0)
        assert len(page) == 2
        # Newest created last → first in the descending-by-created_at listing.
        assert page[0].title == "n2"
