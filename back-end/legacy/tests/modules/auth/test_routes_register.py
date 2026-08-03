from httpx import AsyncClient


class TestRegisterEndpoint:
    async def test_happy_path_returns_201_with_user_and_tokens(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post("/api/auth/register", json=register_payload)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["user"]["email"] == "maria@example.com"
        assert body["user"]["phone"] == "11999998888"
        assert body["user"]["education_level"] == "Vestibulando"
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]
        assert body["tokens"]["token_type"] == "bearer"
        # Password hash must never leak
        assert "password_hash" not in body["user"]
        assert "password" not in body["user"]

    async def test_duplicate_email_returns_409(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        await client.post("/api/auth/register", json=register_payload)
        r = await client.post("/api/auth/register", json=register_payload)
        assert r.status_code == 409

    async def test_invalid_email_returns_422(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post("/api/auth/register", json={**register_payload, "email": "not-email"})
        assert r.status_code == 422

    async def test_short_password_returns_422(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post(
            "/api/auth/register", json={**register_payload, "password": "Short!1"}
        )
        assert r.status_code == 422

    async def test_password_without_special_char_returns_422(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post(
            "/api/auth/register", json={**register_payload, "password": "NoSpecial123"}
        )
        assert r.status_code == 422

    async def test_unknown_education_level_returns_422(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={**register_payload, "education_level": "Astronauta"},
        )
        assert r.status_code == 422

    async def test_accepts_formatted_phone(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={**register_payload, "phone": "(11) 99999-8888"},
        )
        assert r.status_code == 201
        assert r.json()["user"]["phone"] == "11999998888"

    async def test_accepts_iso_birth_date(
        self,
        client: AsyncClient,
        register_payload: dict[str, object],
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={**register_payload, "birth_date": "1995-06-15"},
        )
        assert r.status_code == 201
