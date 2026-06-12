import uuid

from httpx import AsyncClient

from app.modules.products.models import Product


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/orders")
        assert r.status_code == 401

    async def test_create_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/api/orders")
        assert r.status_code == 401


class TestCreateOrder:
    async def test_checkout_from_cart_returns_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        filled_cart: list[Product],
    ) -> None:
        r = await client.post(
            "/api/orders", json={"payment_method": "Visa ••••1234"}, headers=auth_headers
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["total"] == "149.00"
        assert body["payment_method"] == "Visa ••••1234"
        assert len(body["items"]) == 2
        assert body["items"][0]["unit_price"] in {"100.00", "24.50"}

    async def test_checkout_empty_body_defaults_payment(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        filled_cart: list[Product],
    ) -> None:
        r = await client.post("/api/orders", headers=auth_headers)
        assert r.status_code == 201, r.text
        assert r.json()["payment_method"] == ""

    async def test_checkout_empty_cart_returns_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/api/orders", headers=auth_headers)
        assert r.status_code == 400

    async def test_cart_is_empty_after_checkout(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        filled_cart: list[Product],
    ) -> None:
        await client.post("/api/orders", headers=auth_headers)
        r = await client.get("/api/cart", headers=auth_headers)
        assert r.json()["items"] == []


class TestListOrders:
    async def test_lists_created_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        filled_cart: list[Product],
    ) -> None:
        await client.post("/api/orders", headers=auth_headers)
        r = await client.get("/api/orders", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestRebuy:
    async def test_rebuy_repopulates_cart(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        filled_cart: list[Product],
    ) -> None:
        order = (await client.post("/api/orders", headers=auth_headers)).json()

        r = await client.post(f"/api/orders/{order['id']}/rebuy", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["total"] == "149.00"

    async def test_rebuy_unknown_order_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(f"/api/orders/{uuid.uuid4()}/rebuy", headers=auth_headers)
        assert r.status_code == 404
