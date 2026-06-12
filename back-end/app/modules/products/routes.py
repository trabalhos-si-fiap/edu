import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.products import services
from app.modules.products.exceptions import ProductNotFound
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


@router.get("", response_model=ProductList)
async def list_products(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductList:
    items, total = await services.list_products(session, q=q, limit=limit, offset=offset)
    return ProductList(
        items=[ProductOut.model_validate(p) for p in items],
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
) -> ProductOut:
    try:
        product = await services.get_product(session, product_id)
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return ProductOut.model_validate(product)


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
        items, total = await services.list_reviews(
            session, product_id, limit=limit, offset=offset
        )
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
