import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.cart import services
from app.modules.cart.exceptions import CartItemNotFound, CartProductNotFound
from app.modules.cart.schemas import CartItemIn
from app.modules.products.models import Product


class TestGetCart:
    async def test_empty_cart_has_zero_total(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        cart = await services.get_cart(db_session, created_user.id)
        assert cart.items == []
        assert cart.total == 0


class TestAddItem:
    async def test_adds_item_and_computes_subtotal_and_total(
        self,
        db_session: AsyncSession,
        created_user: User,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]  # price 100.00
        cart = await services.add_item(
            db_session, created_user.id, CartItemIn(product_id=product.id, quantity=2)
        )
        assert len(cart.items) == 1
        item = cart.items[0]
        assert item.quantity == 2
        assert item.subtotal == product.price * 2
        assert cart.total == product.price * 2

    async def test_adding_same_product_accumulates_quantity(
        self,
        db_session: AsyncSession,
        created_user: User,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.add_item(
            db_session, created_user.id, CartItemIn(product_id=product.id, quantity=1)
        )
        cart = await services.add_item(
            db_session, created_user.id, CartItemIn(product_id=product.id, quantity=3)
        )
        assert len(cart.items) == 1
        assert cart.items[0].quantity == 4

    async def test_unknown_product_raises(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        with pytest.raises(CartProductNotFound):
            await services.add_item(
                db_session, created_user.id, CartItemIn(product_id=uuid.uuid4(), quantity=1)
            )


class TestRemoveItem:
    async def test_remove_whole_item(
        self,
        db_session: AsyncSession,
        created_user: User,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.add_item(
            db_session, created_user.id, CartItemIn(product_id=product.id, quantity=3)
        )
        cart = await services.remove_item(db_session, created_user.id, product.id)
        assert cart.items == []
        assert cart.total == 0

    async def test_decrement_quantity(
        self,
        db_session: AsyncSession,
        created_user: User,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.add_item(
            db_session, created_user.id, CartItemIn(product_id=product.id, quantity=5)
        )
        cart = await services.remove_item(db_session, created_user.id, product.id, quantity=2)
        assert cart.items[0].quantity == 3

    async def test_decrement_to_zero_removes_item(
        self,
        db_session: AsyncSession,
        created_user: User,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.add_item(
            db_session, created_user.id, CartItemIn(product_id=product.id, quantity=2)
        )
        cart = await services.remove_item(db_session, created_user.id, product.id, quantity=5)
        assert cart.items == []

    async def test_remove_absent_item_raises(
        self,
        db_session: AsyncSession,
        created_user: User,
        seeded_products: list[Product],
    ) -> None:
        with pytest.raises(CartItemNotFound):
            await services.remove_item(db_session, created_user.id, seeded_products[0].id)
