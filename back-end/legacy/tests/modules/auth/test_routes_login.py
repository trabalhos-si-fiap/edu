from httpx import AsyncClient


class TestLoginEndpoint:
    async def test_happy_path(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        await client.post("/api/auth/register", json=register_payload)
        r = await client.post(
            "/api/auth/login",
            json={"email": "maria@example.com", "password": "Secret!1"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == "maria@example.com"
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]

    async def test_wrong_password_returns_401(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        await client.post("/api/auth/register", json=register_payload)
        r = await client.post(
            "/api/auth/login",
            json={"email": "maria@example.com", "password": "Wrong!1"},
        )
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid credentials"}

    async def test_unknown_user_returns_same_401(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "Secret!1"},
        )
        assert r.status_code == 401
        # Same error shape as wrong password — no user enumeration.
        assert r.json() == {"detail": "Invalid credentials"}

    async def test_case_insensitive_email(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        await client.post("/api/auth/register", json=register_payload)
        r = await client.post(
            "/api/auth/login",
            json={"email": "MARIA@EXAMPLE.COM", "password": "Secret!1"},
        )
        assert r.status_code == 200

    async def test_rate_limit_after_five_failures(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        await client.post("/api/auth/register", json=register_payload)
        for _ in range(5):
            r = await client.post(
                "/api/auth/login",
                json={"email": "maria@example.com", "password": "Wrong!1"},
            )
            assert r.status_code == 401
        r = await client.post(
            "/api/auth/login",
            json={"email": "maria@example.com", "password": "Wrong!1"},
        )
        assert r.status_code == 429
        assert "retry-after" in {k.lower() for k in r.headers}
        assert int(r.headers["retry-after"]) > 0
