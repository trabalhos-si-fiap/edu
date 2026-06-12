import uuid

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.exceptions import ProductNotFound
from app.modules.products.models import Product, Review
from app.modules.products.schemas import ReviewIn


async def list_products(
    session: AsyncSession,
    *,
    q: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    if q:
        # ilike with bound parameter — never string-built SQL (security rule #1).
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))

    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    items = list((await session.execute(stmt)).scalars().all())
    total = (await session.execute(count_stmt)).scalar_one()
    return items, total


async def list_categories(session: AsyncSession) -> list[tuple[str, int]]:
    stmt = (
        select(Product.type, func.count().label("count"))
        .group_by(Product.type)
        .order_by(Product.type)
    )
    rows = (await session.execute(stmt)).all()
    return [(row.type, row.count) for row in rows]


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise ProductNotFound()
    return product


async def list_reviews(
    session: AsyncSession,
    product_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Review], int]:
    # Validates the product exists (404 otherwise) before listing.
    await get_product(session, product_id)

    stmt = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.execute(stmt)).scalars().all())
    total = (
        await session.execute(
            select(func.count()).select_from(Review).where(Review.product_id == product_id)
        )
    ).scalar_one()
    return items, total


async def create_review(
    session: AsyncSession,
    product_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    author: str,
    data: ReviewIn,
) -> Review:
    # Lock the product row so concurrent reviews update the denormalized
    # aggregates atomically (security rule #3: no unguarded read→write). The
    # SELECT ... FOR UPDATE and the UPDATE share the session's transaction and
    # commit together; the lock is held until commit.
    product = (
        await session.execute(select(Product).where(Product.id == product_id).with_for_update())
    ).scalar_one_or_none()
    if product is None:
        raise ProductNotFound()

    review = Review(
        product_id=product_id,
        user_id=user_id,
        author=author,
        rating=data.rating,
        comment=data.comment,
    )
    session.add(review)

    new_count = product.rating_count + 1
    new_avg = (float(product.rating_avg) * product.rating_count + data.rating) / new_count
    product.rating_count = new_count
    product.rating_avg = round(new_avg, 2)

    await session.commit()
    await session.refresh(review)
    logger.info("products: review created id={} product={}", review.id, product_id)
    return review
