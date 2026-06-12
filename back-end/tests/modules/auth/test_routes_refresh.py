from httpx import AsyncClient

from app.modules.auth.models import User
from app.modules.auth.security import create_access_token, create_refresh_token


class TestRefreshEndpoint:
    async def test_happy_path(
        self,
        client: AsyncClient,
        created_user: User,
    ) -> None:
        refresh = create_refresh_token(created_user.id)
        r = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

    async def test_access_token_rejected(
        self,
        client: AsyncClient,
        created_user: User,
    ) -> None:
        access = create_access_token(created_user.id)
        r = await client.post("/api/auth/refresh", json={"refresh_token": access})
        assert r.status_code == 401

    async def test_malformed_token_rejected(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/refresh", json={"refresh_token": "garbage"})
        assert r.status_code == 401

    async def test_empty_body_returns_422(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/refresh", json={})
        assert r.status_code == 422
