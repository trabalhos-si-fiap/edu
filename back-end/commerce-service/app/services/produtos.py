import uuid

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ProductNotFoundError
from app.models.produto import Product
from app.models.review import Review
from app.schemas.review import ReviewIn


async def listar_produtos(
    db: AsyncSession, *, q: str | None = None, limit: int, offset: int
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    if q:
        # `ilike` com parâmetro bound — o pattern vai como valor, nunca
        # concatenado na string SQL (regra 1 do CLAUDE.md).
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))

    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def listar_categorias(db: AsyncSession) -> list[tuple[str, int]]:
    stmt = (
        select(Product.type, func.count().label("count"))
        .group_by(Product.type)
        .order_by(Product.type)
    )
    return [(row.type, row.count) for row in (await db.execute(stmt)).all()]


async def buscar_produto(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError()
    return product


async def listar_reviews(
    db: AsyncSession, product_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Review], int]:
    # Valida que o produto existe (404 caso contrário) antes de listar.
    await buscar_produto(db, product_id)

    stmt = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count()).select_from(Review).where(Review.product_id == product_id)
        )
    ).scalar_one()
    return items, total


async def criar_review(
    db: AsyncSession,
    product_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    author: str,
    data: ReviewIn,
) -> Review:
    # Lock na linha do produto para que reviews concorrentes atualizem os
    # agregados desnormalizados atomicamente (regra 3 do CLAUDE.md). O
    # SELECT ... FOR UPDATE e o UPDATE dividem a transação da sessão e
    # commitam juntos; o lock vale até o commit.
    product = (
        await db.execute(select(Product).where(Product.id == product_id).with_for_update())
    ).scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError()

    review = Review(
        product_id=product_id,
        user_id=user_id,
        author=author,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)

    new_count = product.rating_count + 1
    new_avg = (float(product.rating_avg) * product.rating_count + data.rating) / new_count
    product.rating_count = new_count
    product.rating_avg = round(new_avg, 2)

    await db.commit()
    await db.refresh(review)
    logger.info("products: review criada id={} product={}", review.id, product_id)
    return review
