import uuid

from httpx import AsyncClient

from tests.modules.addresses.conftest import make_address


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/addresses")
        assert r.status_code == 401


class TestCreate:
    async def test_first_address_is_favorite_by_default(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/api/auth/addresses", json=make_address(), headers=auth_headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["is_favorite"] is True
        assert body["city"] == "São Paulo"
        assert "id" in body

    async def test_second_favorite_unsets_first(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = (
            await client.post("/api/auth/addresses", json=make_address(), headers=auth_headers)
        ).json()
        await client.post(
            "/api/auth/addresses",
            json=make_address(label="Trabalho", is_favorite=True),
            headers=auth_headers,
        )

        listing = (await client.get("/api/auth/addresses", headers=auth_headers)).json()
        favorites = [a for a in listing if a["is_favorite"]]
        assert len(favorites) == 1
        assert favorites[0]["label"] == "Trabalho"
        first_now = next(a for a in listing if a["id"] == first["id"])
        assert first_now["is_favorite"] is False

    async def test_missing_required_field_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        payload = make_address()
        del payload["street"]
        r = await client.post("/api/auth/addresses", json=payload, headers=auth_headers)
        assert r.status_code == 422

    async def test_invalid_state_length_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/addresses", json=make_address(state="SaoPaulo"), headers=auth_headers
        )
        assert r.status_code == 422


class TestListOrdering:
    async def test_favorite_listed_first(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post("/api/auth/addresses", json=make_address(label="A"), headers=auth_headers)
        await client.post(
            "/api/auth/addresses",
            json=make_address(label="B", is_favorite=True),
            headers=auth_headers,
        )
        listing = (await client.get("/api/auth/addresses", headers=auth_headers)).json()
        assert listing[0]["is_favorite"] is True
        assert listing[0]["label"] == "B"


class TestPatch:
    async def test_partial_update(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        created = (
            await client.post("/api/auth/addresses", json=make_address(), headers=auth_headers)
        ).json()
        r = await client.patch(
            f"/api/auth/addresses/{created['id']}",
            json={"number": "2000", "complement": ""},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["number"] == "2000"
        assert r.json()["street"] == "Av. Paulista"  # untouched

    async def test_setting_favorite_moves_it(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = (
            await client.post("/api/auth/addresses", json=make_address(), headers=auth_headers)
        ).json()
        second = (
            await client.post(
                "/api/auth/addresses", json=make_address(label="B"), headers=auth_headers
            )
        ).json()

        await client.patch(
            f"/api/auth/addresses/{second['id']}",
            json={"is_favorite": True},
            headers=auth_headers,
        )
        listing = (await client.get("/api/auth/addresses", headers=auth_headers)).json()
        favorites = {a["id"] for a in listing if a["is_favorite"]}
        assert favorites == {second["id"]}
        assert first["id"] not in favorites

    async def test_patch_unknown_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.patch(
            f"/api/auth/addresses/{uuid.uuid4()}", json={"number": "9"}, headers=auth_headers
        )
        assert r.status_code == 404


class TestDelete:
    async def test_delete_then_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        created = (
            await client.post("/api/auth/addresses", json=make_address(), headers=auth_headers)
        ).json()
        r = await client.delete(f"/api/auth/addresses/{created['id']}", headers=auth_headers)
        assert r.status_code == 204

        r = await client.delete(f"/api/auth/addresses/{created['id']}", headers=auth_headers)
        assert r.status_code == 404
