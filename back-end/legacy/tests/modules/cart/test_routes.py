import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models import Product


class TestAuthRequired:
    async def test_get_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/cart")
        assert r.status_code == 401

    async def test_add_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/api/cart/items", json={"product_id": str(uuid.uuid4())})
        assert r.status_code == 401


class TestCartFlow:
    async def test_empty_cart(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        r = await client.get("/api/cart", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["items"] == []
        assert body["total"] == "0.00"

    async def test_add_item_returns_cart_with_string_money(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]  # 100.00
        r = await client.post(
            "/api/cart/items",
            json={"product_id": str(product.id), "quantity": 2},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["total"] == "200.00"
        item = body["items"][0]
        assert item["product_id"] == str(product.id)
        assert item["price"] == "100.00"
        assert item["subtotal"] == "200.00"
        assert item["quantity"] == 2
        assert item["name"] == product.name

    async def test_add_unknown_product_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/cart/items",
            json={"product_id": str(uuid.uuid4()), "quantity": 1},
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_total_sums_multiple_products(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_products: list[Product],
    ) -> None:
        await client.post(
            "/api/cart/items",
            json={"product_id": str(seeded_products[0].id), "quantity": 1},
            headers=auth_headers,
        )
        r = await client.post(
            "/api/cart/items",
            json={"product_id": str(seeded_products[1].id), "quantity": 2},
            headers=auth_headers,
        )
        # 100.00 + 2 * 24.50 = 149.00
        assert r.json()["total"] == "149.00"

    async def test_delete_decrements_then_removes(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await client.post(
            "/api/cart/items",
            json={"product_id": str(product.id), "quantity": 3},
            headers=auth_headers,
        )
        r = await client.delete(f"/api/cart/items/{product.id}?quantity=1", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["items"][0]["quantity"] == 2

        r = await client.delete(f"/api/cart/items/{product.id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["items"] == []

    async def test_delete_absent_item_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_products: list[Product],
    ) -> None:
        r = await client.delete(f"/api/cart/items/{seeded_products[0].id}", headers=auth_headers)
        assert r.status_code == 404


class TestCartImagePresign:
    async def test_get_cart_item_image_url_is_presigned(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        product = Product(
            name="Produto com imagem",
            type="Livro",
            subtype="Mat",
            description="",
            price=Decimal("50.00"),
            image_url="products/test-presign.png",
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)

        await client.post(
            "/api/cart/items",
            json={"product_id": str(product.id), "quantity": 1},
            headers=auth_headers,
        )

        r = await client.get("/api/cart", headers=auth_headers)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert len(items) == 1
        image_url = items[0]["image_url"]
        assert "X-Amz-Signature" in image_url or "X-Amz-Credential" in image_url
