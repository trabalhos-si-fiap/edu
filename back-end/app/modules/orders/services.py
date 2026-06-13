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
from app.modules.notifications import services as notifications_services
from app.modules.orders import lifecycle
from app.modules.orders.enums import OrderStatus
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
        (await session.execute(select(CartItem).where(CartItem.cart_id == cart.id))).scalars().all()
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

    # Kick off the (simulated) delivery lifecycle: the order is PENDING now and
    # the pipeline immediately advances it to CONFIRMED, then onward on timers.
    # Local import keeps orders.services <-> orders.tasks decoupled at load time.
    from app.modules.orders.tasks import advance_order_status_task

    advance_order_status_task.delay(str(refreshed.id), OrderStatus.CONFIRMED.value)
    return refreshed


async def advance_order_status(
    session: AsyncSession, order_id: uuid.UUID, to_status: OrderStatus
) -> bool:
    """Atomically move an order to ``to_status`` and notify its owner.

    Forward-only and idempotent (CLAUDE.md rules #3/#10): the row is locked with
    ``FOR UPDATE`` and the move only happens when ``to_status`` is the immediate
    successor of the current status. A replay or out-of-order delivery finds the
    order is not exactly one step behind and no-ops, so the notification is never
    sent twice. Returns ``True`` only when it actually advanced.
    """
    order = (
        await session.execute(select(Order).where(Order.id == order_id).with_for_update())
    ).scalar_one_or_none()
    if order is None:
        return False

    if not lifecycle.can_advance_to(OrderStatus(order.status), to_status):
        return False

    user_id = order.user_id  # capture before commit
    order.status = to_status.value
    await session.commit()

    title, body = lifecycle.STATUS_NOTIFICATION[to_status]
    await notifications_services.notify_user(
        session,
        user_id,
        title,
        body,
        data={"type": "order_status", "order_id": str(order_id), "status": to_status.value},
    )
    return True


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
