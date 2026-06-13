import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.firebase import PushResult
from app.modules.auth.models import User
from app.modules.notifications import services
from app.modules.notifications.schemas import DevicePlatform, DeviceTokenIn


class TestNotifyUser:
    async def test_persists_even_without_device_token(
        self, db_session: AsyncSession, created_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No tokens registered: FCM is never hit, but the in-app history must
        # still record the notification.
        def _fail(*_args: object, **_kwargs: object) -> list[PushResult]:
            raise AssertionError("send_multicast must not be called without tokens")

        monkeypatch.setattr(services.firebase, "send_multicast", _fail)

        notification = await services.notify_user(db_session, created_user.id, "Oi", "corpo")
        assert notification.id is not None

        stored = await services.list_notifications(db_session, created_user.id, limit=20, offset=0)
        assert [n.title for n in stored] == ["Oi"]

    async def test_persists_and_pushes_when_token_exists(
        self, db_session: AsyncSession, created_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await services.register_device_token(
            db_session, created_user.id, DeviceTokenIn(token="t", platform=DevicePlatform.ANDROID)
        )
        sent_to: list[list[str]] = []

        def _send(tokens: list[str], **_kwargs: object) -> list[PushResult]:
            sent_to.append(tokens)
            return [PushResult(token=t, success=True, invalid=False) for t in tokens]

        monkeypatch.setattr(services.firebase, "send_multicast", _send)

        await services.notify_user(db_session, created_user.id, "Oi", "corpo", {"k": "v"})

        assert sent_to == [["t"]]
        stored = await services.list_notifications(db_session, created_user.id, limit=20, offset=0)
        assert len(stored) == 1
