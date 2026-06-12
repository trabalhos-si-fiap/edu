import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.cart import services as cart_services
from app.modules.cart.models import CartItem
from app.modules.cart.schemas import CartItemIn
from app.modules.orders import services
from app.modules.orders.exceptions import EmptyCart, OrderNotFound
from app.modules.products.models import Product


class TestCreateOrderFromCart:
    async def test_builds_order_and_empties_cart(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        order = await services.create_order_from_cart(db_session, created_user.id, "PIX")

        assert order.total == 100 * 1 + 24.50 * 2  # 149.00
        assert order.payment_method == "PIX"
        assert len(order.items) == 2

        # Cart is now empty.
        remaining = (
            await db_session.execute(select(func.count()).select_from(CartItem))
        ).scalar_one()
        assert remaining == 0

    async def test_snapshots_unit_price(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        order = await services.create_order_from_cart(db_session, created_user.id, "")
        by_name = {i.product_name: i for i in order.items}
        assert by_name["Cálculo"].unit_price == filled_cart[0].price

    async def test_empty_cart_raises(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        with pytest.raises(EmptyCart):
            await services.create_order_from_cart(db_session, created_user.id, "")

    async def test_second_checkout_on_emptied_cart_raises(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        await services.create_order_from_cart(db_session, created_user.id, "PIX")
        with pytest.raises(EmptyCart):
            await services.create_order_from_cart(db_session, created_user.id, "PIX")


class TestListAndGet:
    async def test_lists_user_orders_desc(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        await services.create_order_from_cart(db_session, created_user.id, "PIX")
        orders = await services.list_orders(db_session, created_user.id, limit=50, offset=0)
        assert len(orders) == 1
        assert orders[0].items

    async def test_get_unknown_raises(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        with pytest.raises(OrderNotFound):
            await services.get_order(db_session, created_user.id, uuid.uuid4())

    async def test_get_enforces_ownership(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        order = await services.create_order_from_cart(db_session, created_user.id, "PIX")
        other_user = uuid.uuid4()
        with pytest.raises(OrderNotFound):
            await services.get_order(db_session, other_user, order.id)


class TestRebuyRepopulatesCart:
    async def test_order_items_can_refill_cart(
        self,
        db_session: AsyncSession,
        created_user: User,
        filled_cart: list[Product],
    ) -> None:
        order = await services.create_order_from_cart(db_session, created_user.id, "PIX")
        # Cart emptied; refill from order via cart service (mirrors route rebuy).
        for item in order.items:
            await cart_services.add_item(
                db_session,
                created_user.id,
                CartItemIn(product_id=item.product_id, quantity=item.quantity),
            )
        cart = await cart_services.get_cart(db_session, created_user.id)
        assert cart.total == order.total
