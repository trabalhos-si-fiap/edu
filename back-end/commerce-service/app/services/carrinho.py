import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import CarrinhoOrigemMistaError, CartItemNotFoundError, CartProductNotFoundError
from app.models.carrinho import Cart, CartItem
from app.models.produto import Estoque, Product
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


async def _fornecedor_do_produto(db: AsyncSession, product_id: uuid.UUID) -> int | None:
    """De qual parceiro este produto é. `None` quando não há linha de estoque.

    Produto pertence ao parceiro ATRAVÉS do estoque — a mesma travessia que
    `services.produtos.listar_produtos` faz para o filtro `partner_id`.

    Correção ao brief da task 8: `Estoque` tem `uq_produto_fornecedor` na
    PAR (produto_id, fornecedor_id), não em `produto_id` sozinho — um
    produto com mais de um fornecedor gera mais de uma linha aqui.
    `scalar_one_or_none()` estouraria `MultipleResultsFound` nesse caso (500
    em `POST /cart/items` para um catálogo perfeitamente comum).
    `order_by(Estoque.id).limit(1)` resolve de forma determinística para a
    linha mais antiga — mesma correção e mesmo critério de desempate que a
    task 3 já aplicou em `obter_estoque_do_produto`
    (`app/services/estoque.py`), para as duas funções concordarem sobre qual
    é o fornecedor de um mesmo produto. Ver
    test_a_product_stocked_by_two_suppliers_is_added_without_a_500.
    """
    result = await db.execute(
        select(Estoque.fornecedor_id)
        .where(Estoque.produto_id == product_id)
        .order_by(Estoque.id)
        .limit(1)
    )
    return result.scalars().first()


async def _origem_do_carrinho(db: AsyncSession, cart_id: uuid.UUID) -> int | None:
    """O fornecedor dos itens que já estão no carrinho, ou `None` se o
    carrinho está vazio (ou só tem itens sem origem).

    LIMIT 1 basta: a regra que esta função serve é o que garante que nunca há
    mais de um fornecedor aqui. Mas LIMIT 1 sem ORDER BY deixa a ordem a
    critério do plano — fix round 1: `uq_produto_fornecedor` é um índice
    único composto em `(produto_id, fornecedor_id)`, e um plano guiado por
    esse índice devolve os `fornecedor_id` casados em ordem de índice
    (por `fornecedor_id`), não por `Estoque.id`. Sem `order_by(Estoque.id)`
    aqui, esta função podia resolver um fornecedor DIFERENTE do que
    `_fornecedor_do_produto` resolve para o MESMO produto — um estudante
    que adiciona de novo um item já no carrinho podia levar um 409 falso, e
    o espelho disso é um carrinho misto aceito em silêncio: o próprio bug
    que esta task existe para impedir. `order_by(Estoque.id)` alinha esta
    função com `_fornecedor_do_produto` e com
    `app/services/estoque.py::obter_estoque_do_produto` — as três
    concordam sobre qual fornecedor um produto resolve, sempre a linha de
    menor `Estoque.id`, não importa o plano escolhido. Ver
    test_origem_do_carrinho_agrees_with_fornecedor_do_produto_for_the_same_product.
    """
    return (
        await db.execute(
            select(Estoque.fornecedor_id)
            .join(CartItem, CartItem.product_id == Estoque.produto_id)
            .where(CartItem.cart_id == cart_id)
            .order_by(Estoque.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def adicionar_item(db: AsyncSession, user_id: uuid.UUID, data: CartItemIn) -> CartOut:
    produto = (
        await db.execute(select(Product).where(Product.id == data.product_id))
    ).scalar_one_or_none()
    # Produto INATIVO é recusado como produto inexistente, e de propósito
    # reusando `CartProductNotFoundError` em vez de uma quinta forma de erro:
    # para o cliente, um produto que `GET /products` não lista mais NÃO está no
    # catálogo, e "Product not found" é exatamente o que a rota já responde
    # nesse caso. Duas consequências que valem escrever:
    #
    # 1. `POST /orders/{id}/rebuy` já captura esta exceção e faz `continue`
    #    (`app/routers/pedidos.py`), então a recompra de um pedido antigo cujo
    #    produto foi desativado devolve o RESTO do pedido em vez de um erro —
    #    o comportamento certo, sem um segundo caminho de código. `adicionar_item`
    #    tem DOIS chamadores, e foi ignorar isso que produziu o finding 3.
    # 2. A recusa acontece ANTES de qualquer escrita — nenhuma linha de
    #    carrinho é criada —, que é a propriedade de que aquele `continue`
    #    depende para não deixar a sessão suja.
    #
    # NADA é retroativo: carrinho já montado e pedido já feito não são tocados
    # (ver tests/test_inactive_product_rule.py). Remover item de carrinho alheio
    # por desativação de catálogo seria regra de negócio que ninguém pediu.
    if produto is None or not produto.active:
        raise CartProductNotFoundError()

    cart = await get_or_create_cart(db, user_id)

    # Lock na linha do carrinho para serializar todas as mutações do carrinho
    # deste usuário, tornando o read->write da quantidade do item atômico
    # (regra 3 do CLAUDE.md).
    await db.execute(select(Cart.id).where(Cart.id == cart.id).with_for_update())

    # A checagem de origem fica DENTRO do lock de linha do carrinho que a
    # linha acima acabou de tomar. Fora dele, duas adições simultâneas leem um
    # carrinho vazio, as duas concluem "não há origem ainda", e as duas
    # gravam — carrinho misto sem nenhum erro aparecer. Regra 3 do CLAUDE.md.
    fornecedor_do_item = await _fornecedor_do_produto(db, data.product_id)
    origem_atual = await _origem_do_carrinho(db, cart.id)
    if (
        fornecedor_do_item is not None
        and origem_atual is not None
        and fornecedor_do_item != origem_atual
    ):
        raise CarrinhoOrigemMistaError()

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
