from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.auth.security import create_access_token, create_refresh_token


class TestMeEndpoint:
    async def test_returns_current_user(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        created_user: User,
    ) -> None:
        r = await client.get("/auth/me", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == created_user.email
        assert body["name"] == created_user.name
        assert "password_hash" not in body

    async def test_missing_auth_returns_401(self, client: AsyncClient) -> None:
        r = await client.get("/auth/me")
        assert r.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient) -> None:
        r = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
        assert r.status_code == 401

    async def test_refresh_token_cannot_be_used_as_access(
        self,
        client: AsyncClient,
        created_user: User,
    ) -> None:
        refresh = create_refresh_token(created_user.id)
        r = await client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
        assert r.status_code == 401

    async def test_expired_token_returns_401(
        self,
        client: AsyncClient,
        created_user: User,
    ) -> None:
        past = datetime.now(UTC) - timedelta(minutes=5)
        token = create_access_token(created_user.id, expires_at=past)
        r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    async def test_inactive_user_returns_401(
        self,
        client: AsyncClient,
        created_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        created_user.is_active = False
        await db_session.commit()
        r = await client.get("/auth/me", headers=auth_headers)
        assert r.status_code == 401
