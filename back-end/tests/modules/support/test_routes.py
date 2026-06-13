from httpx import AsyncClient


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        assert r.status_code == 401

    async def test_send_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/api/support", json={"body": "olá"})
        assert r.status_code == 401


class TestSupportFlow:
    async def test_empty_history(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/support", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json() == []

    async def test_send_returns_updated_list(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/support", json={"body": "Não consigo pagar"}, headers=auth_headers
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert len(body) == 1
        assert body[0]["body"] == "Não consigo pagar"
        assert body[0]["sender"] == "user"
        assert "id" in body[0]
        assert "created_at" in body[0]

    async def test_messages_accumulate_in_order(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post("/api/support", json={"body": "primeira"}, headers=auth_headers)
        r = await client.post(
            "/api/support", json={"body": "segunda"}, headers=auth_headers
        )
        bodies = [m["body"] for m in r.json()]
        assert bodies == ["primeira", "segunda"]

    async def test_empty_body_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/api/support", json={"body": ""}, headers=auth_headers)
        assert r.status_code == 422

    async def test_messages_are_per_user(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session
    ) -> None:
        from datetime import date

        from app.modules.auth import services as auth_services
        from app.modules.auth.schemas import RegisterIn
        from app.modules.auth.security import create_access_token

        await client.post("/api/support", json={"body": "minha"}, headers=auth_headers)

        other = await auth_services.register(
            db_session,
            RegisterIn(
                name="Outro",
                email="outro@example.com",
                phone="11888887777",
                birth_date=date(1990, 1, 1),
                education_level="Vestibulando",
                password="Secret!1",
            ),
        )
        other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}

        r = await client.get("/api/support", headers=other_headers)
        assert r.json() == []
