import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Composition seam: the cart reads product display data live from the products
# catalog. This is the single cross-module read (no Python import of products
# *services*); when the cart becomes a standalone microservice, swap this for an
# HTTP/event call to the products service.
from app.modules.cart.exceptions import CartItemNotFound, CartProductNotFound
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.schemas import CartItemIn, CartItemOut, CartOut
from app.modules.products.models import Product


async def get_or_create_cart(session: AsyncSession, user_id: uuid.UUID) -> Cart:
    cart = (
        await session.execute(select(Cart).where(Cart.user_id == user_id))
    ).scalar_one_or_none()
    if cart is not None:
        return cart

    cart = Cart(user_id=user_id)
    session.add(cart)
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent first-touch created the cart — fall back to it.
        await session.rollback()
        cart = (
            await session.execute(select(Cart).where(Cart.user_id == user_id))
        ).scalar_one()
    await session.refresh(cart)
    return cart


async def _load_products(
    session: AsyncSession, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Product]:
    if not product_ids:
        return {}
    rows = (
        await session.execute(select(Product).where(Product.id.in_(product_ids)))
    ).scalars().all()
    return {p.id: p for p in rows}


async def build_cart_out(session: AsyncSession, cart_id: uuid.UUID) -> CartOut:
    items = list(
        (
            await session.execute(
                select(CartItem)
                .where(CartItem.cart_id == cart_id)
                .order_by(CartItem.created_at)
            )
        )
        .scalars()
        .all()
    )
    products = await _load_products(session, [i.product_id for i in items])

    out_items: list[CartItemOut] = []
    total = Decimal("0.00")
    for item in items:
        product = products.get(item.product_id)
        if product is None:
            # Product left the catalog; omit it from the view rather than 500.
            continue
        subtotal = product.price * item.quantity
        total += subtotal
        out_items.append(
            CartItemOut(
                product_id=product.id,
                name=product.name,
                type=product.type,
                subtype=product.subtype,
                price=product.price,
                quantity=item.quantity,
                subtotal=subtotal,
                image_url=product.image_url,
                rating_avg=float(product.rating_avg),
                rating_count=product.rating_count,
            )
        )
    return CartOut(items=out_items, total=total)


async def get_cart(session: AsyncSession, user_id: uuid.UUID) -> CartOut:
    cart = await get_or_create_cart(session, user_id)
    return await build_cart_out(session, cart.id)


async def add_item(session: AsyncSession, user_id: uuid.UUID, data: CartItemIn) -> CartOut:
    product = (
        await session.execute(select(Product).where(Product.id == data.product_id))
    ).scalar_one_or_none()
    if product is None:
        raise CartProductNotFound()

    cart = await get_or_create_cart(session, user_id)

    # Lock the cart row to serialize all mutations on this user's cart, making
    # the read→write on item quantity atomic (security rule #3).
    await session.execute(select(Cart.id).where(Cart.id == cart.id).with_for_update())

    item = (
        await session.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart.id, CartItem.product_id == data.product_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if item is not None:
        item.quantity += data.quantity
    else:
        session.add(CartItem(cart_id=cart.id, product_id=data.product_id, quantity=data.quantity))

    await session.commit()
    return await build_cart_out(session, cart.id)


async def remove_item(
    session: AsyncSession,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: int | None = None,
) -> CartOut:
    cart = (
        await session.execute(select(Cart).where(Cart.user_id == user_id))
    ).scalar_one_or_none()
    if cart is None:
        raise CartItemNotFound()

    await session.execute(select(Cart.id).where(Cart.id == cart.id).with_for_update())

    item = (
        await session.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None:
        raise CartItemNotFound()

    if quantity is None or quantity >= item.quantity:
        await session.delete(item)
    else:
        item.quantity -= quantity

    await session.commit()
    return await build_cart_out(session, cart.id)
