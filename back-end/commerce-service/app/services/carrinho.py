import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import CartItemNotFoundError, CartProductNotFoundError
from app.models.carrinho import Cart, CartItem
from app.models.produto import Product
from app.schemas.carrinho import CartItemIn, CartItemOut, CartOut


async def get_or_create_cart(db: AsyncSession, user_id: uuid.UUID) -> Cart:
    cart = (await db.execute(select(Cart).where(Cart.user_id == user_id))).scalar_one_or_none()
    if cart is not None:
        return cart

    cart = Cart(user_id=user_id)
    db.add(cart)
    try:
        await db.commit()
    except IntegrityError:
        # Primeiro toque concorrente já criou o carrinho — cai para ele.
        await db.rollback()
        cart = (await db.execute(select(Cart).where(Cart.user_id == user_id))).scalar_one()
    await db.refresh(cart)
    return cart


async def _carregar_produtos(
    db: AsyncSession, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Product]:
    if not product_ids:
        return {}
    rows = (await db.execute(select(Product).where(Product.id.in_(product_ids)))).scalars().all()
    return {p.id: p for p in rows}


async def montar_cart_out(db: AsyncSession, cart_id: uuid.UUID) -> CartOut:
    items = list(
        (
            await db.execute(
                select(CartItem).where(CartItem.cart_id == cart_id).order_by(CartItem.created_at)
            )
        )
        .scalars()
        .all()
    )
    produtos = await _carregar_produtos(db, [i.product_id for i in items])

    out_items: list[CartItemOut] = []
    total = Decimal("0.00")
    for item in items:
        produto = produtos.get(item.product_id)
        if produto is None:
            # Produto saiu do catálogo; omite da view em vez de 500.
            continue
        subtotal = produto.price * item.quantity
        total += subtotal
        out_items.append(
            CartItemOut(
                product_id=produto.id,
                name=produto.name,
                type=produto.type,
                subtype=produto.subtype,
                price=produto.price,
                quantity=item.quantity,
                subtotal=subtotal,
                image_url=produto.image_url,
                rating_avg=float(produto.rating_avg),
                rating_count=produto.rating_count,
            )
        )
    return CartOut(items=out_items, total=total)


async def obter_carrinho(db: AsyncSession, user_id: uuid.UUID) -> CartOut:
    cart = await get_or_create_cart(db, user_id)
    return await montar_cart_out(db, cart.id)


async def adicionar_item(db: AsyncSession, user_id: uuid.UUID, data: CartItemIn) -> CartOut:
    produto = (
        await db.execute(select(Product).where(Product.id == data.product_id))
    ).scalar_one_or_none()
    if produto is None:
        raise CartProductNotFoundError()

    cart = await get_or_create_cart(db, user_id)

    # Lock na linha do carrinho para serializar todas as mutações do carrinho
    # deste usuário, tornando o read->write da quantidade do item atômico
    # (regra 3 do CLAUDE.md).
    await db.execute(select(Cart.id).where(Cart.id == cart.id).with_for_update())

    item = (
        await db.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart.id, CartItem.product_id == data.product_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if item is not None:
        item.quantity += data.quantity
    else:
        db.add(CartItem(cart_id=cart.id, product_id=data.product_id, quantity=data.quantity))

    await db.commit()
    return await montar_cart_out(db, cart.id)


async def remover_item(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: int | None = None,
) -> CartOut:
    cart = (await db.execute(select(Cart).where(Cart.user_id == user_id))).scalar_one_or_none()
    if cart is None:
        raise CartItemNotFoundError()

    await db.execute(select(Cart.id).where(Cart.id == cart.id).with_for_update())

    item = (
        await db.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None:
        raise CartItemNotFoundError()

    if quantity is None or quantity >= item.quantity:
        await db.delete(item)
    else:
        item.quantity -= quantity

    await db.commit()
    return await montar_cart_out(db, cart.id)
