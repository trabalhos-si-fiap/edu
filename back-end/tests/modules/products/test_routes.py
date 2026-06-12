import uuid

from httpx import AsyncClient

from app.modules.products.models import Product


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/products")
        assert r.status_code == 401

    async def test_create_review_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post(f"/api/products/{uuid.uuid4()}/reviews", json={"rating": 5})
        assert r.status_code == 401


class TestListProducts:
    async def test_returns_items_and_pagination_envelope(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        r = await client.get("/api/products", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 3
        assert body["limit"] == 20
        assert body["offset"] == 0
        assert len(body["items"]) == 3

    async def test_price_serialized_as_string(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        r = await client.get("/api/products?q=Cálculo", headers=auth_headers)
        item = r.json()["items"][0]
        assert item["price"] == "129.90"
        assert isinstance(item["price"], str)

    async def test_limit_over_max_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/products?limit=500", headers=auth_headers)
        assert r.status_code == 422


class TestCategories:
    async def test_lists_categories(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        r = await client.get("/api/products/categories", headers=auth_headers)
        assert r.status_code == 200, r.text
        items = {c["type"]: c["count"] for c in r.json()["items"]}
        assert items == {"Livro": 2, "Material": 1}


class TestProductDetail:
    async def test_returns_product(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        target = seeded_products[0]
        r = await client.get(f"/api/products/{target.id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == target.name

    async def test_unknown_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.get(f"/api/products/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404


class TestReviews:
    async def test_create_then_list_reflects_aggregate(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        product = seeded_products[0]

        r = await client.post(
            f"/api/products/{product.id}/reviews",
            json={"rating": 5, "comment": "Excelente"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["author"] == "Maria Silva"
        assert created["rating"] == 5

        r = await client.get(f"/api/products/{product.id}/reviews", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["rating_count"] == 1
        assert body["rating_avg"] == 5.0
        assert body["items"][0]["comment"] == "Excelente"

    async def test_invalid_rating_returns_422(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        product = seeded_products[0]
        r = await client.post(
            f"/api/products/{product.id}/reviews",
            json={"rating": 9},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_reviews_for_unknown_product_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.get(f"/api/products/{uuid.uuid4()}/reviews", headers=auth_headers)
        assert r.status_code == 404
