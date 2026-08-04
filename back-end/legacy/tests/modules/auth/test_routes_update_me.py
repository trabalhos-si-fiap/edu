from httpx import AsyncClient

from app.modules.auth.models import User


class TestUpdateMeEndpoint:
    async def test_updates_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        created_user: User,
    ) -> None:
        r = await client.patch(
            "/api/auth/me", json={"name": "Maria Souza"}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Maria Souza"
        assert body["email"] == created_user.email  # untouched
        assert "password_hash" not in body

    async def test_updates_phone_normalizes_digits(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.patch(
            "/api/auth/me", json={"phone": "(11) 98888-7777"}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["phone"] == "11988887777"

    async def test_updates_birth_date_ddmmyyyy(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.patch(
            "/api/auth/me", json={"birth_date": "01/02/1990"}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["birth_date"] == "1990-02-01"

    async def test_empty_body_is_noop(
        self, client: AsyncClient, auth_headers: dict[str, str], created_user: User
    ) -> None:
        r = await client.patch("/api/auth/me", json={}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == created_user.name

    async def test_invalid_phone_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.patch("/api/auth/me", json={"phone": "123"}, headers=auth_headers)
        assert r.status_code == 422

    async def test_cannot_change_email_via_patch(
        self, client: AsyncClient, auth_headers: dict[str, str], created_user: User
    ) -> None:
        # email is not a patchable field; extra keys are ignored, email stays.
        r = await client.patch(
            "/api/auth/me", json={"email": "hacker@example.com"}, headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["email"] == created_user.email

    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.patch("/api/auth/me", json={"name": "X"})
        assert r.status_code == 401
