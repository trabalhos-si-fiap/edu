import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import CartItemNotFoundError, CartProductNotFoundError
from app.redis_client import get_redis
from app.schemas.carrinho import CartItemIn, CartOut
from app.services import carrinho as services
from app.services.media import presigned_image_url
from app.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/cart", tags=["cart"])


async def _presign_cart(cart: CartOut, *, storage: ObjectStorage, redis: aioredis.Redis) -> CartOut:
    for item in cart.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return cart


@router.get("", response_model=CartOut)
async def obter_carrinho(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> CartOut:
    cart = await services.obter_carrinho(db, uuid.UUID(user["sub"]))
    return await _presign_cart(cart, storage=storage, redis=redis)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def adicionar_item(
    payload: CartItemIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> CartOut:
    try:
        cart = await services.adicionar_item(db, uuid.UUID(user["sub"]), payload)
        return await _presign_cart(cart, storage=storage, redis=redis)
    except CartProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc


@router.delete("/items/{product_id}", response_model=CartOut)
async def remover_item(
    product_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    quantity: int | None = Query(default=None, ge=1),
) -> CartOut:
    try:
        cart = await services.remover_item(db, uuid.UUID(user["sub"]), product_id, quantity)
        return await _presign_cart(cart, storage=storage, redis=redis)
    except CartItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart"
        ) from exc
