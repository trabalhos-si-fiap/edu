import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.products import services
from app.modules.products.exceptions import ProductNotFound
from app.modules.products.models import Product
from app.modules.products.schemas import ReviewIn


class TestListProducts:
    async def test_returns_all_with_total(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        items, total = await services.list_products(db_session, limit=20, offset=0)
        assert total == 3
        assert len(items) == 3

    async def test_q_filters_by_name_case_insensitive(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        items, total = await services.list_products(db_session, q="física", limit=20, offset=0)
        assert total == 1
        assert items[0].name == "Física para Cientistas"

    async def test_pagination_limits_and_reports_full_total(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        items, total = await services.list_products(db_session, limit=2, offset=0)
        assert len(items) == 2
        assert total == 3


class TestListCategories:
    async def test_groups_by_type_with_counts(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        rows = await services.list_categories(db_session)
        as_dict = dict(rows)
        assert as_dict == {"Livro": 2, "Material": 1}


class TestGetProduct:
    async def test_returns_product(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        target = seeded_products[0]
        product = await services.get_product(db_session, target.id)
        assert product.id == target.id

    async def test_missing_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(ProductNotFound):
            await services.get_product(db_session, uuid.uuid4())


class TestCreateReview:
    async def test_creates_and_updates_aggregates(
        self,
        db_session: AsyncSession,
        seeded_products: list[Product],
        created_user: User,
    ) -> None:
        product = seeded_products[0]

        await services.create_review(
            db_session,
            product.id,
            user_id=created_user.id,
            author=created_user.name,
            data=ReviewIn(rating=4, comment="Bom"),
        )
        await services.create_review(
            db_session,
            product.id,
            user_id=created_user.id,
            author=created_user.name,
            data=ReviewIn(rating=2, comment="Ok"),
        )

        refreshed = await services.get_product(db_session, product.id)
        assert refreshed.rating_count == 2
        assert float(refreshed.rating_avg) == pytest.approx(3.0)

    async def test_review_carries_author_and_user(
        self,
        db_session: AsyncSession,
        seeded_products: list[Product],
        created_user: User,
    ) -> None:
        product = seeded_products[1]
        review = await services.create_review(
            db_session,
            product.id,
            user_id=created_user.id,
            author=created_user.name,
            data=ReviewIn(rating=5),
        )
        assert review.author == created_user.name
        assert review.user_id == created_user.id
        assert review.comment == ""

    async def test_missing_product_raises(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        with pytest.raises(ProductNotFound):
            await services.create_review(
                db_session,
                uuid.uuid4(),
                user_id=created_user.id,
                author=created_user.name,
                data=ReviewIn(rating=5),
            )
