import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import create_access_token
from app.modules.products.models import Product

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict[str, str]:
    from datetime import date

    from app.modules.auth import services as auth_services
    from app.modules.auth.schemas import RegisterIn

    admin = await auth_services.register(
        db_session,
        RegisterIn(
            name="Admin",
            email="admin@example.com",
            phone="11999991111",
            birth_date=date(1990, 1, 1),
            education_level="Vestibulando",
            password="Secret!1",
        ),
    )
    admin.is_admin = True
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


class TestImageUpload:
    async def test_non_admin_is_forbidden(
        self, client: AsyncClient, seeded_products: list[Product], auth_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[0].id
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=auth_headers,
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert r.status_code == 403

    async def test_admin_uploads_and_image_url_is_presigned(
        self, client: AsyncClient, seeded_products: list[Product], admin_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[1].id
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=admin_headers,
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "X-Amz-Signature" in body["image_url"] or "X-Amz-Credential" in body["image_url"]

    async def test_rejects_non_image_content_type(
        self, client: AsyncClient, seeded_products: list[Product], admin_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[1].id
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=admin_headers,
            files={"file": ("p.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400

    async def test_rejects_oversized_file(
        self, client: AsyncClient, seeded_products: list[Product], admin_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[1].id
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=admin_headers,
            files={"file": ("p.png", big, "image/png")},
        )
        assert r.status_code == 413

    async def test_unknown_product_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            f"/api/products/{uuid.uuid4()}/image",
            headers=admin_headers,
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert r.status_code == 404
