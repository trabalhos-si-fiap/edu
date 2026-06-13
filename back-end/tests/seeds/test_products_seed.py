from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models import Product, Review
from app.seeds.products import SEED_PRODUCTS, seed_products


class TestProductsSeed:
    async def test_inserts_full_catalog(self, db_session: AsyncSession) -> None:
        inserted = await seed_products(db_session)
        assert inserted == len(SEED_PRODUCTS)

        total = (await db_session.execute(select(func.count()).select_from(Product))).scalar_one()
        assert total == len(SEED_PRODUCTS)

    async def test_seeds_sample_reviews_and_headline_aggregates(
        self, db_session: AsyncSession
    ) -> None:
        await seed_products(db_session)

        product = (
            await db_session.execute(
                select(Product).where(Product.name == "Guia de Redação Nota 1000")
            )
        ).scalar_one()
        assert product.rating_count == 128
        assert float(product.rating_avg) == 4.5

        review_count = (
            await db_session.execute(
                select(func.count()).select_from(Review).where(Review.product_id == product.id)
            )
        ).scalar_one()
        assert review_count == 2

    async def test_is_idempotent(self, db_session: AsyncSession) -> None:
        first = await seed_products(db_session)
        second = await seed_products(db_session)
        assert first == len(SEED_PRODUCTS)
        assert second == 0

        total = (await db_session.execute(select(func.count()).select_from(Product))).scalar_one()
        assert total == len(SEED_PRODUCTS)


def test_solid_png_is_a_valid_image() -> None:
    from app.core.media import validate_image_bytes
    from app.seeds.products import _solid_png

    png = _solid_png(8, 8, (10, 20, 30))
    ext, content_type = validate_image_bytes(png, declared_type="image/png")
    assert ext == "png"
    assert content_type == "image/png"


class _RecordingStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str]] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        self.puts.append((key, content_type))


async def test_seed_uploads_image_and_sets_key_when_storage_given(
    db_session: AsyncSession,
) -> None:
    storage = _RecordingStorage()
    inserted = await seed_products(db_session, storage=storage)
    assert inserted == len(SEED_PRODUCTS)
    assert len(storage.puts) == len(SEED_PRODUCTS)
    assert all(k.startswith("products/seed-") and ct == "image/png" for k, ct in storage.puts)

    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    assert product.image_url.startswith("products/seed-")
