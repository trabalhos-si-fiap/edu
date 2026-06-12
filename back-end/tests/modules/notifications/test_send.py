import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.firebase import PushResult
from app.modules.auth.models import User
from app.modules.notifications import services
from app.modules.notifications.schemas import DevicePlatform, DeviceTokenIn


async def _register(session: AsyncSession, user: User, token: str) -> None:
    await services.register_device_token(
        session, user.id, DeviceTokenIn(token=token, platform=DevicePlatform.ANDROID)
    )


class TestSendPushToUser:
    async def test_returns_zero_when_user_has_no_tokens(
        self, db_session: AsyncSession, created_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = False

        def _fail(*_args: object, **_kwargs: object) -> list[PushResult]:
            nonlocal called
            called = True
            return []

        monkeypatch.setattr(services.firebase, "send_multicast", _fail)
        sent = await services.send_push_to_user(db_session, created_user.id, "Oi", "corpo")
        assert sent == 0
        # The SDK must not even be invoked when there are no tokens.
        assert called is False

    async def test_sends_to_all_tokens_and_counts_successes(
        self, db_session: AsyncSession, created_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await _register(db_session, created_user, "a")
        await _register(db_session, created_user, "b")

        def _send(tokens: list[str], **_kwargs: object) -> list[PushResult]:
            return [PushResult(token=t, success=True, invalid=False) for t in tokens]

        monkeypatch.setattr(services.firebase, "send_multicast", _send)
        sent = await services.send_push_to_user(db_session, created_user.id, "Oi", "corpo")
        assert sent == 2

    async def test_purges_invalid_tokens(
        self, db_session: AsyncSession, created_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await _register(db_session, created_user, "good")
        await _register(db_session, created_user, "dead")

        def _send(tokens: list[str], **_kwargs: object) -> list[PushResult]:
            return [
                PushResult(token=t, success=(t == "good"), invalid=(t == "dead")) for t in tokens
            ]

        monkeypatch.setattr(services.firebase, "send_multicast", _send)
        sent = await services.send_push_to_user(db_session, created_user.id, "Oi", "corpo")
        assert sent == 1

        remaining = await services.list_tokens_for_user(db_session, created_user.id)
        assert remaining == ["good"]
