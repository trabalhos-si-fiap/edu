import uuid
from decimal import Decimal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Transactional composition seam: checkout must read the cart, snapshot product
# data, create the order, and empty the cart in ONE locked transaction so it is
# atomic and idempotent (security rule #3). That correctness requirement
# outweighs module purity here, so orders reads the cart/products tables
# directly. When extracted, this becomes a saga/transactional outbox.
from app.modules.cart.models import Cart, CartItem
from app.modules.orders.exceptions import EmptyCart, OrderNotFound
from app.modules.orders.models import Order, OrderItem
from app.modules.products.models import Product


async def _get_order_with_items(
    session: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID
) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_order_from_cart(
    session: AsyncSession, user_id: uuid.UUID, payment_method: str
) -> Order:
    # Lock the cart row so a concurrent/duplicate checkout can't build two
    # orders from the same cart — the second finds it already emptied.
    cart = (
        await session.execute(select(Cart).where(Cart.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if cart is None:
        raise EmptyCart()

    cart_items = list(
        (
            await session.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        )
        .scalars()
        .all()
    )
    if not cart_items:
        raise EmptyCart()

    products = {
        p.id: p
        for p in (
            await session.execute(
                select(Product).where(Product.id.in_([i.product_id for i in cart_items]))
            )
        )
        .scalars()
        .all()
    }

    order = Order(user_id=user_id, payment_method=payment_method, total=Decimal("0.00"))
    total = Decimal("0.00")
    for cart_item in cart_items:
        product = products.get(cart_item.product_id)
        if product is None:
            # Product left the catalog between add and checkout; skip it.
            continue
        total += product.price * cart_item.quantity
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=cart_item.quantity,
                image_url=product.image_url,
                rating_avg=float(product.rating_avg),
                rating_count=product.rating_count,
            )
        )

    if not order.items:
        raise EmptyCart()

    order.total = total
    session.add(order)

    # Empty the cart in the same transaction.
    for cart_item in cart_items:
        await session.delete(cart_item)

    await session.commit()
    logger.info("orders: order created id={} user={} total={}", order.id, user_id, total)

    refreshed = await _get_order_with_items(session, user_id, order.id)
    assert refreshed is not None  # just created in this transaction
    return refreshed


async def list_orders(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_order(session: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await _get_order_with_items(session, user_id, order_id)
    if order is None:
        raise OrderNotFound()
    return order
