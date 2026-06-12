import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

# Composition seam: rebuy repopulates the cart from a past order. Done at the
# route layer so orders.services stays decoupled from cart writes.
from app.modules.cart import services as cart_services
from app.modules.cart.exceptions import CartProductNotFound
from app.modules.cart.schemas import CartItemIn, CartOut
from app.modules.orders import services
from app.modules.orders.exceptions import EmptyCart, OrderNotFound
from app.modules.orders.schemas import OrderCreateIn, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
async def list_orders(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrderOut]:
    orders = await services.list_orders(session, user.id, limit=limit, offset=offset)
    return [OrderOut.model_validate(o) for o in orders]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: OrderCreateIn | None = None,
) -> OrderOut:
    payment_method = payload.payment_method if payload is not None else ""
    try:
        order = await services.create_order_from_cart(session, user.id, payment_method)
    except EmptyCart as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        ) from exc
    return OrderOut.model_validate(order)


@router.post("/{order_id}/rebuy", response_model=CartOut)
async def rebuy(
    order_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CartOut:
    try:
        order = await services.get_order(session, user.id, order_id)
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        ) from exc

    cart: CartOut | None = None
    for item in order.items:
        try:
            cart = await cart_services.add_item(
                session, user.id, CartItemIn(product_id=item.product_id, quantity=item.quantity)
            )
        except CartProductNotFound:
            # Product no longer in the catalog — skip it rather than fail rebuy.
            continue

    if cart is None:
        # None of the order's products still exist; return the current cart.
        cart = await cart_services.get_cart(session, user.id)
    return cart
