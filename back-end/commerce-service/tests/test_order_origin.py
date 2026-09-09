"""A origem de expedição é resolvida na CRIAÇÃO do pedido e congelada nele.

A spec C lê estas colunas para simular a rota e NÃO recalcula a origem — o
estoque pode mudar de fornecedor depois que o pedido saiu. Mesmo espírito do
snapshot `ship_*`: um pedido é registro histórico.

`order_items.supplier_id` existe desde a fase 2 e nunca foi escrito
(`app/models/pedido.py` registra isso em comentário). Aqui ele passa a ser
preenchido.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.carrinho import Cart, CartItem
from app.models.pedido import Order, OrderItem
from app.models.produto import Estoque, Fornecedor, Product
from app.services.carrinho import _fornecedor_do_produto
from app.services.pedidos import criar_pedido_do_carrinho

_ALUNO = "00000000-0000-0000-0000-0000000000cc"


def headers_for(sub: str = _ALUNO) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, 'student', settings.jwt_secret)}"}


async def _catalogo(db_session, *, parceiro: str, rotulo: str, lat, lng, produto: str):
    f = Fornecedor(nome=parceiro, origem_rotulo=rotulo, origem_lat=lat, origem_lng=lng)
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)

    p = Product(name=produto, type="mobiliario", price=Decimal("10.00"), sku=produto[:60])
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    db_session.add(Estoque(produto_id=p.id, fornecedor_id=f.id, quantidade=50))
    await db_session.commit()
    return f, p


async def test_the_order_freezes_the_partner_origin(client, db_session):
    _f, p = await _catalogo(
        db_session,
        parceiro="Leroy Merlin",
        rotulo="Cajamar, SP",
        lat=Decimal("-23.355800"),
        lng=Decimal("-46.876400"),
        produto="Luminária",
    )
    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 2}, headers=headers_for()
    )

    response = await client.post("/orders", json={"payment_method": "PIX"}, headers=headers_for())
    assert response.status_code == 201

    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo == "Cajamar, SP"
    assert pedido.origem_lat == Decimal("-23.355800")
    assert pedido.origem_lng == Decimal("-46.876400")


async def test_the_items_carry_the_supplier_id(client, db_session):
    f, p = await _catalogo(
        db_session, parceiro="Edu", rotulo="Aclimação, SP", lat=None, lng=None, produto="Apostila"
    )
    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post("/orders", json={"payment_method": "PIX"}, headers=headers_for())

    itens = (
        (
            await db_session.execute(
                select(OrderItem).where(OrderItem.order_id == uuid.UUID(response.json()["id"]))
            )
        )
        .scalars()
        .all()
    )
    assert [i.supplier_id for i in itens] == [f.id]


async def test_a_partner_without_coordinates_still_freezes_the_label(client, db_session):
    await _catalogo(
        db_session, parceiro="Edu", rotulo="Aclimação, SP", lat=None, lng=None, produto="Apostila"
    )
    produto = (await db_session.execute(select(Product))).scalars().first()
    await client.post(
        "/cart/items", json={"product_id": str(produto.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post("/orders", json={"payment_method": "PIX"}, headers=headers_for())
    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo == "Aclimação, SP"
    assert pedido.origem_lat is None


async def test_a_cart_of_originless_products_yields_an_order_without_origin(client, db_session):
    """Nenhum 500. Um produto sem linha de estoque (os seis semeados, até a
    task 11) produz pedido sem origem — que é exatamente o que a coluna
    nullable significa."""
    p = Product(name="Órfão", type="apostila", price=Decimal("1.00"), sku="ORFAO-9")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post("/orders", json={"payment_method": "PIX"}, headers=headers_for())

    assert response.status_code == 201
    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo is None


async def test_changing_the_stock_supplier_afterwards_does_not_move_the_order(client, db_session):
    """O congelamento é o ponto da coluna. A spec C lê o pedido, não o
    estoque, justamente porque o estoque pode mudar depois."""
    f, p = await _catalogo(
        db_session,
        parceiro="Leroy Merlin",
        rotulo="Cajamar, SP",
        lat=Decimal("-23.355800"),
        lng=Decimal("-46.876400"),
        produto="Luminária",
    )
    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post("/orders", json={"payment_method": "PIX"}, headers=headers_for())

    f.origem_rotulo = "Outro Lugar, MG"
    await db_session.commit()

    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    await db_session.refresh(pedido)
    assert pedido.origem_rotulo == "Cajamar, SP"


async def test_the_order_agrees_with_fornecedor_do_produto_for_a_two_supplier_product(
    db_session,
):
    """Defeito na literal do brief: `vinculos` era um dict comprehension SEM
    `order_by(Estoque.id)`, então a ÚLTIMA linha devolvida pela query (ordem
    do plano, não determinística) vencia. `Estoque` tem `uq_produto_fornecedor`
    na PAR (produto_id, fornecedor_id) — um produto com dois fornecedores gera
    duas linhas aqui, exatamente o caso deste teste.

    As outras três funções que já resolvem "o fornecedor de um produto" nesta
    base — `app/services/estoque.py::obter_estoque_do_produto` e
    `app/services/carrinho.py::_fornecedor_do_produto`/`_origem_do_carrinho`
    — concordam todas na linha de MENOR `Estoque.id`. Se `criar_pedido_do_
    carrinho` resolvesse por outro critério, o mesmo produto poderia sair do
    carrinho com um parceiro e chegar no pedido com outro — o `supplier_id`
    e a origem gravados seriam do fornecedor ERRADO, num registro histórico
    que a spec C lê para montar a rota.

    Este teste grava a linha de estoque do fornecedor B (`fornecedor_id`
    maior) PRIMEIRO — logo com `Estoque.id` MENOR — e a do fornecedor A
    DEPOIS, com `Estoque.id` maior. Sem `order_by`, um plano de varredura
    sequencial (o padrão para uma tabela deste tamanho, sem índice
    utilizável para filtrar por `produto_id` sozinho de forma seletiva o
    bastante para o planner preferir index scan) devolve as linhas na ordem
    física de inserção — fornecedor B primeiro, fornecedor A por último — e
    o dict comprehension do brief, que fica com a ÚLTIMA linha, resolveria
    para o fornecedor A: o oposto do que `_fornecedor_do_produto` resolve
    (fornecedor B, menor `Estoque.id`). Com `order_by(Estoque.id)` +
    `setdefault` (a PRIMEIRA linha vence), o pedido concorda com
    `_fornecedor_do_produto` não importa o plano escolhido.
    """
    fornecedor_a = Fornecedor(nome="Fornecedor A", origem_rotulo="A, SP")
    fornecedor_b = Fornecedor(nome="Fornecedor B", origem_rotulo="B, SP")
    db_session.add_all([fornecedor_a, fornecedor_b])
    await db_session.commit()
    await db_session.refresh(fornecedor_a)
    await db_session.refresh(fornecedor_b)

    produto = Product(
        name="Dupla Origem Pedido", type="mobiliario", price=Decimal("10.00"), sku="DUPLA-9"
    )
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    # Fornecedor B gravado PRIMEIRO -> Estoque.id MENOR.
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor_b.id, quantidade=10))
    await db_session.commit()
    # Fornecedor A gravado DEPOIS -> Estoque.id MAIOR.
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor_a.id, quantidade=10))
    await db_session.commit()

    canonical = await _fornecedor_do_produto(db_session, produto.id)
    assert canonical == fornecedor_b.id  # menor Estoque.id vence, por construção

    aluno_id = uuid.UUID(_ALUNO)
    cart = Cart(user_id=aluno_id)
    db_session.add(cart)
    await db_session.commit()
    await db_session.refresh(cart)
    db_session.add(CartItem(cart_id=cart.id, product_id=produto.id, quantity=1))
    await db_session.commit()

    order = await criar_pedido_do_carrinho(db_session, aluno_id, "PIX")

    assert order.items[0].supplier_id == canonical
    fornecedor_canonico = await db_session.get(Fornecedor, canonical)
    assert order.origem_rotulo == fornecedor_canonico.origem_rotulo
