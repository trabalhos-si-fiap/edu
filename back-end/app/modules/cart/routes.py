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
from app.modules.cart import services
from app.modules.cart.exceptions import CartItemNotFound, CartProductNotFound
from app.modules.cart.schemas import CartItemIn, CartOut

router = APIRouter(prefix="/cart", tags=["cart"])


async def _presign_cart(cart: CartOut, *, storage: ObjectStorage, redis: aioredis.Redis) -> CartOut:
    for item in cart.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return cart


@router.get("", response_model=CartOut)
async def get_cart(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> CartOut:
    cart = await services.get_cart(session, user.id)
    return await _presign_cart(cart, storage=storage, redis=redis)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    payload: CartItemIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> CartOut:
    try:
        cart = await services.add_item(session, user.id, payload)
        return await _presign_cart(cart, storage=storage, redis=redis)
    except CartProductNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc


@router.delete("/items/{product_id}", response_model=CartOut)
async def remove_item(
    product_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    quantity: Annotated[int | None, Query(ge=1)] = None,
) -> CartOut:
    try:
        cart = await services.remove_item(session, user.id, product_id, quantity)
        return await _presign_cart(cart, storage=storage, redis=redis)
    except CartItemNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart"
        ) from exc
