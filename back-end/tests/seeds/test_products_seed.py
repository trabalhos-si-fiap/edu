from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models import Product, Review
from app.seeds.products import SEED_PRODUCTS, seed_products


class TestProductsSeed:
    async def test_inserts_full_catalog(self, db_session: AsyncSession) -> None:
        inserted = await seed_products(db_session)
        assert inserted == len(SEED_PRODUCTS)

        total = (
            await db_session.execute(select(func.count()).select_from(Product))
        ).scalar_one()
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
                select(func.count())
                .select_from(Review)
                .where(Review.product_id == product.id)
            )
        ).scalar_one()
        assert review_count == 2

    async def test_is_idempotent(self, db_session: AsyncSession) -> None:
        first = await seed_products(db_session)
        second = await seed_products(db_session)
        assert first == len(SEED_PRODUCTS)
        assert second == 0

        total = (
            await db_session.execute(select(func.count()).select_from(Product))
        ).scalar_one()
        assert total == len(SEED_PRODUCTS)
