import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.cart import services
from app.modules.cart.exceptions import CartItemNotFound, CartProductNotFound
from app.modules.cart.schemas import CartItemIn, CartOut

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartOut)
async def get_cart(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CartOut:
    return await services.get_cart(session, user.id)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    payload: CartItemIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CartOut:
    try:
        return await services.add_item(session, user.id, payload)
    except CartProductNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc


@router.delete("/items/{product_id}", response_model=CartOut)
async def remove_item(
    product_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    quantity: Annotated[int | None, Query(ge=1)] = None,
) -> CartOut:
    try:
        return await services.remove_item(session, user.id, product_id, quantity)
    except CartItemNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart"
        ) from exc
