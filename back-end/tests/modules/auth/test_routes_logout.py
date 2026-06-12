from httpx import AsyncClient


class TestLogoutEndpoint:
    async def test_returns_ok_with_valid_token(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r = await client.post("/api/auth/logout", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == {"detail": "ok"}

    async def test_missing_auth_returns_401(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/logout")
        assert r.status_code == 401
