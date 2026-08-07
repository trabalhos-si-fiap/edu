"""Testes de paridade de `/products`, `/products/categories` e
`/products/{id}` — porte de `legacy/tests/modules/products/test_routes.py`
(task B6 do bloco B). Ver `task-B6-report.md` para a lista completa de
asserções adaptadas e de testes removidos.
"""

import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from httpx import AsyncClient

from app.config import settings
from app.models.produto import Product


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_products(db_session) -> list[Product]:
    """Porte de `legacy/tests/modules/products/conftest.py::seeded_products`,
    adaptando só o import de `Product` (`app.modules.products.models` →
    `app.models.produto`)."""
    products = [
        Product(
            name="Cálculo Volume 1",
            type="Livro",
            subtype="Matemática",
            description="Cálculo diferencial e integral",
            price=Decimal("129.90"),
            image_url="products/calc.png",
        ),
        Product(
            name="Física para Cientistas",
            type="Livro",
            subtype="Física",
            description="Mecânica e termodinâmica",
            price=Decimal("99.00"),
        ),
        Product(
            name="Caderno Universitário",
            type="Material",
            subtype="Papelaria",
            description="200 folhas",
            price=Decimal("24.50"),
        ),
    ]
    db_session.add_all(products)
    await db_session.commit()
    for p in products:
        await db_session.refresh(p)
    return products


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/products")
        # 403, não 401: ver a divergência registrada na task B0 do plano do bloco B.
        # O `edu-common` responde 403 para header ausente e 401 para token
        # inválido/expirado; o legacy responde 401 nos dois.
        assert r.status_code == 403


class TestListProducts:
    async def test_returns_items_and_pagination_envelope(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products", headers=headers_for("student"))
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
    ) -> None:
        r = await client.get("/products?q=Cálculo", headers=headers_for("student"))
        item = r.json()["items"][0]
        assert item["price"] == "129.90"
        assert isinstance(item["price"], str)

    async def test_limit_over_max_returns_422(self, client: AsyncClient) -> None:
        r = await client.get("/products?limit=500", headers=headers_for("student"))
        assert r.status_code == 422


class TestCategories:
    async def test_lists_categories(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products/categories", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        items = {c["type"]: c["count"] for c in r.json()["items"]}
        assert items == {"Livro": 2, "Material": 1}


class TestProductDetail:
    async def test_returns_product(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        target = seeded_products[0]
        r = await client.get(f"/products/{target.id}", headers=headers_for("student"))
        assert r.status_code == 200
        assert r.json()["name"] == target.name

    async def test_unknown_returns_404(self, client: AsyncClient) -> None:
        r = await client.get(f"/products/{uuid.uuid4()}", headers=headers_for("student"))
        assert r.status_code == 404


class TestImagePresign:
    async def test_image_url_is_presigned_when_key_present(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products?q=Cálculo", headers=headers_for("student"))
        item = r.json()["items"][0]
        assert "X-Amz-Signature" in item["image_url"] or "X-Amz-Credential" in item["image_url"]

    async def test_image_url_empty_when_no_key(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products?q=Física", headers=headers_for("student"))
        assert r.json()["items"][0]["image_url"] == ""
