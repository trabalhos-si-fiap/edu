"""Dívida de schema #1 do commerce, decisão do usuário (2026-08-09, task
C10): `order_items.product_id` não pode ter FK para `products.id`. Um
pedido é registro histórico (snapshot — ver comentário em
`app/models/pedido.py` acima de `product_id`); o catálogo tem que poder
mudar por baixo, inclusive apagar um produto. Com a FK presente, apagar um
produto referenciado por qualquer pedido levanta `IntegrityError`
(violação de FK), e o caminho "produto saiu do catálogo é pulado" da
recompra (C7) fica inalcançável em produção — o legacy nunca teve essa FK
(`back-end/legacy/app/modules/orders/models.py:84`).

Migration própria: `alembic/versions/73f26f88d679_drop_order_items_product_fk.py`,
encadeada a partir de `099099b0c1a8`.
"""

import uuid
from decimal import Decimal

from sqlalchemy import delete, select

from app.models.pedido import Order, OrderItem
from app.models.produto import Product


async def _seed_pedido(db_session) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status="CRIADO",
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_produto(db_session) -> Product:
    produto = Product(name="Caderno", price=Decimal("19.90"), type="papelaria")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)
    return produto


async def test_deleting_a_referenced_product_does_not_raise(db_session):
    """Um pedido é snapshot histórico — apagar o produto que ele
    referenciou não pode quebrar o catálogo. Hoje (FK presente) apaga: este
    teste prova o RED contra o código atual antes da migration remover o
    `ForeignKey`.

    Não basta "não levantar" — achado da revisão (fix round 1, Minor #3):
    um FK futuro com `ondelete="CASCADE"` também não levantaria, mas
    apagaria a linha do `OrderItem` em silêncio, exatamente o oposto do que
    esta dívida existe para impedir (o item é o registro histórico do que
    foi comprado; sumir junto com o produto apagaria a compra da história).
    Por isso a asserção final confere que o item SOBREVIVE, com o MESMO
    `product_id` que apontava para o produto agora apagado — uma FK com
    CASCADE reprovaria esta linha (o `scalar_one()` levantaria
    `NoResultFound`, a linha já não existiria)."""
    pedido = await _seed_pedido(db_session)
    produto = await _seed_produto(db_session)
    item = OrderItem(
        order_id=pedido.id,
        product_id=produto.id,
        product_name=produto.name,
        unit_price=produto.price,
        quantity=1,
    )
    db_session.add(item)
    await db_session.commit()
    item_id = item.id
    produto_id = produto.id

    # Apagar o produto que o item referencia não pode levantar — o item é
    # um snapshot, não uma referência viva ao catálogo.
    await db_session.execute(delete(Product).where(Product.id == produto_id))
    await db_session.commit()

    db_session.expire_all()
    result = await db_session.execute(select(OrderItem).where(OrderItem.id == item_id))
    sobrevivente = result.scalar_one()
    assert sobrevivente.product_id == produto_id
