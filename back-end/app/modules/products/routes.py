import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.media import presigned_image_url
from app.core.redis_client import get_redis
from app.core.storage import ObjectStorage, get_storage
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.products import services
from app.modules.products.exceptions import ProductNotFound
from app.modules.products.models import Product
from app.modules.products.schemas import (
    CategoryList,
    CategoryOut,
    ProductList,
    ProductOut,
    ReviewIn,
    ReviewList,
    ReviewOut,
)

router = APIRouter(prefix="/products", tags=["products"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


async def _product_out(
    product: Product, *, storage: ObjectStorage, redis: aioredis.Redis
) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.image_url = await presigned_image_url(product.image_url, storage=storage, redis=redis)
    return out


@router.get("", response_model=ProductList)
async def list_products(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductList:
    items, total = await services.list_products(session, q=q, limit=limit, offset=offset)
    return ProductList(
        items=[await _product_out(p, storage=storage, redis=redis) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/categories", response_model=CategoryList)
async def list_categories(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryList:
    rows = await services.list_categories(session)
    return CategoryList(items=[CategoryOut(type=t, count=c) for t, c in rows])


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: uuid.UUID,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> ProductOut:
    try:
        product = await services.get_product(session, product_id)
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return await _product_out(product, storage=storage, redis=redis)


@router.get("/{product_id}/reviews", response_model=ReviewList)
async def list_reviews(
    product_id: uuid.UUID,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewList:
    try:
        product = await services.get_product(session, product_id)
        items, total = await services.list_reviews(session, product_id, limit=limit, offset=offset)
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return ReviewList(
        items=[ReviewOut.model_validate(r) for r in items],
        total=total,
        rating_avg=float(product.rating_avg),
        rating_count=product.rating_count,
    )


@router.post(
    "/{product_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    product_id: uuid.UUID,
    payload: ReviewIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReviewOut:
    try:
        review = await services.create_review(
            session,
            product_id,
            user_id=user.id,
            author=user.name,
            data=payload,
        )
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return ReviewOut.model_validate(review)
