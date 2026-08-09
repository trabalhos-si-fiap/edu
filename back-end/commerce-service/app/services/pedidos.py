import uuid
from decimal import Decimal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import EmptyCartError, OrderNotFoundError
from app.models.carrinho import Cart, CartItem
from app.models.pedido import Order, OrderItem, PedidoStatusHistorico
from app.models.produto import Product
from app.services.status_pedido import StatusPedido


def endereco_formatado(order: Order) -> str:
    """Monta a string que `endereco_entrega` guardava, a partir de sete dos
    oito campos `ship_*` do snapshot (ver app/models/pedido.py::Order).
    `ship_label` fica de fora de propósito: é um apelido escolhido pelo
    aluno ("Casa", "Trabalho"), não parte do endereço postal — não faz
    sentido dentro de uma string para geocodificar nem para a operação ler
    como endereço. Correção de fix round 2 (code review): a versão
    anterior deste docstring dizia "oito campos", contado errado — o corpo
    da função só lê `ship_street`, `ship_number`, `ship_complement`,
    `ship_neighborhood`, `ship_city`, `ship_state` e `ship_zip_code`.

    A coluna morreu porque um endereço em texto livre não dá para
    geocodificar (`GET /orders/{id}/route` precisa dos campos separados) nem
    para renderizar por parte. Mas a operação de staff lia essa string —
    então ela continua existindo, agora derivada (`PedidoStaffOut.de_order`).

    O FORMATO abaixo é invenção desta task, não algo herdado do legacy:
    `grep -rn "endereco_formatado" back-end/legacy/` não devolve nada (medido
    em 2026-08-09). O legacy tem `_destination_query`
    (`back-end/legacy/app/modules/tracking/services.py:117-127`), mas é uma
    string para GEOCODIFICAR (termina em `", Brazil"`, junta tudo com `", "`
    sem compor rua+número+complemento numa mesma parte), não uma string para
    a operação LER — formatos diferentes, propósitos diferentes.

    Pedido sem snapshot nenhum (criação com corpo vazio, ver
    `PedidoCreateIn`) devolve string vazia, não "None, None - None": cada
    parte só entra na composição se o campo correspondente não for None.
    """
    linha = ", ".join(p for p in (order.ship_street, order.ship_number, order.ship_complement) if p)
    if order.ship_neighborhood:
        linha = f"{linha} - {order.ship_neighborhood}" if linha else order.ship_neighborhood

    cidade_estado = " - ".join(p for p in (order.ship_city, order.ship_state) if p)

    partes = [linha, cidade_estado, order.ship_zip_code]
    return ", ".join(p for p in partes if p)


async def criar_pedido_do_carrinho(
    db: AsyncSession,
    user_id: uuid.UUID,
    payment_method: str,
    *,
    address: dict | None = None,
) -> Order:
    """Cria o pedido a partir do carrinho do aluno, numa transação só.

    O PREÇO VEM DO CATÁLOGO, nunca do cliente. A rota anterior compunha
    `valor_total` a partir do `preco_unitario` que veio na requisição e nunca
    importava o model de produto — qualquer aluno comprava qualquer coisa por
    um centavo. Essa rota é substituída inteira aqui, não remendada.

    O carrinho é travado com `with_for_update()` para que um checkout
    duplicado (duplo toque, retry do app) não construa dois pedidos do mesmo
    carrinho: o segundo o encontra já esvaziado e recebe `EmptyCartError`.

    `address` é o dict que `auth_client.get_address` devolveu — a validação
    de existência e de dono já aconteceu lá, no serviço que é dono do dado.
    """
    cart = (
        await db.execute(select(Cart).where(Cart.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if cart is None:
        raise EmptyCartError()

    cart_items = list(
        (await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))).scalars().all()
    )
    if not cart_items:
        raise EmptyCartError()

    products = {
        p.id: p
        for p in (
            await db.execute(
                select(Product).where(Product.id.in_([i.product_id for i in cart_items]))
            )
        )
        .scalars()
        .all()
    }

    order = Order(
        user_id=user_id,
        status=StatusPedido.CRIADO.value,
        payment_method=payment_method,
        total=Decimal("0.00"),
        ship_label=address["label"] if address else None,
        ship_zip_code=address["zip_code"] if address else None,
        ship_street=address["street"] if address else None,
        ship_number=address["number"] if address else None,
        ship_complement=address["complement"] if address else None,
        ship_neighborhood=address["neighborhood"] if address else None,
        ship_city=address["city"] if address else None,
        ship_state=address["state"] if address else None,
    )

    total = Decimal("0.00")
    for cart_item in cart_items:
        product = products.get(cart_item.product_id)
        if product is None:
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
        raise EmptyCartError()

    order.total = total
    db.add(order)
    # `Order.id` é um default Python (`new_uuid`), avaliado só no FLUSH, não
    # na construção do objeto — sem este flush, `order.id` ainda seria
    # `None` na linha de baixo e `PedidoStatusHistorico` nasceria com FK
    # nula. Medido (task-C6-report.md, seção "Bug do Step 3"): rodando o
    # código do plano como escrito, `historico[0].order_id` veio `None`
    # enquanto `order.id` já era um UUID de verdade. A rota que esta função
    # substitui já sabia disso (`app/routers/pedidos.py`,
    # `db.add(pedido); await db.flush()` antes de montar itens/histórico).
    await db.flush()
    db.add(PedidoStatusHistorico(order_id=order.id, status=StatusPedido.CRIADO.value))

    for cart_item in cart_items:
        await db.delete(cart_item)

    await db.commit()
    logger.info("orders: pedido criado id={} user={} total={}", order.id, user_id, total)

    refreshed = await _buscar_com_itens(db, user_id, order.id)
    assert refreshed is not None  # acabou de ser criado nesta transação
    # `advance_order_status_task.delay(...)` do legacy NÃO é portado aqui:
    # não há simulador de avanço de status na fase 2 (carve-out declarado,
    # constraint 22 do plano). O pedido fica em CRIADO/pending até um admin
    # confirmar o pagamento via `PATCH /admin/orders/{id}/confirm-payment`.
    return refreshed


async def _buscar_com_itens(
    db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID
) -> Order | None:
    """Único lugar que sabe filtrar pedido por dono (regra 2 do CLAUDE.md) —
    `listar_pedidos` e `buscar_pedido` nunca montam esse `where` sozinhos."""
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def listar_pedidos(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def buscar_pedido(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await _buscar_com_itens(db, user_id, order_id)
    if order is None:
        raise OrderNotFoundError()
    return order
