from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.notifications import services

_BASE = "/api/notifications/devices"
_LIST = "/api/notifications"


class TestAuthRequired:
    async def test_register_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post(_BASE, json={"token": "abc", "platform": "android"})
        assert r.status_code == 401

    async def test_delete_requires_auth(self, client: AsyncClient) -> None:
        r = await client.delete(f"{_BASE}/abc")
        assert r.status_code == 401


class TestRegister:
    async def test_register_returns_201_without_token_value(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            _BASE, json={"token": "fcm-abc", "platform": "android"}, headers=auth_headers
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["platform"] == "android"
        assert "id" in body
        # The raw token must never be echoed back to the client.
        assert "token" not in body

    async def test_register_is_idempotent(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = await client.post(_BASE, json={"token": "fcm-abc"}, headers=auth_headers)
        second = await client.post(_BASE, json={"token": "fcm-abc"}, headers=auth_headers)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

    async def test_platform_defaults_to_android(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(_BASE, json={"token": "fcm-abc"}, headers=auth_headers)
        assert r.json()["platform"] == "android"

    async def test_empty_token_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(_BASE, json={"token": ""}, headers=auth_headers)
        assert r.status_code == 422


class TestDelete:
    async def test_delete_owned_token_returns_204(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(_BASE, json={"token": "fcm-abc"}, headers=auth_headers)
        r = await client.delete(f"{_BASE}/fcm-abc", headers=auth_headers)
        assert r.status_code == 204

    async def test_delete_unknown_token_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.delete(f"{_BASE}/nope", headers=auth_headers)
        assert r.status_code == 404


class TestListNotifications:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get(_LIST)
        assert r.status_code == 401

    async def test_returns_owner_notifications_newest_first(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        created_user: User,
        db_session: AsyncSession,
    ) -> None:
        await services.create_notification(db_session, created_user.id, "old", "x")
        await services.create_notification(
            db_session, created_user.id, "new", "y", {"type": "order_status"}
        )

        r = await client.get(_LIST, headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert [n["title"] for n in body] == ["new", "old"]
        assert body[0]["data"] == {"type": "order_status"}
        assert body[0]["read_at"] is None

    async def test_does_not_leak_other_users(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user: User,
        db_session: AsyncSession,
    ) -> None:
        await services.create_notification(db_session, other_user.id, "theirs", "x")
        r = await client.get(_LIST, headers=auth_headers)
        assert r.json() == []
