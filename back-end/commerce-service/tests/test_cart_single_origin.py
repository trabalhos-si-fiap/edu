"""Origem única no carrinho. Pedido misto é PROIBIDO, não adiado.

A regra vive no SERVIÇO, sob o mesmo lock de linha do carrinho que a adição
já toma (`select(Cart.id)...with_for_update()` em
`app/services/carrinho.py::adicionar_item`). Pô-la na tela deixaria duas
adições simultâneas montarem um carrinho misto — regra 3 do CLAUDE.md:
leitura seguida de escrita em recurso compartilhado é atômica ou não é regra.
"""

import asyncio
import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.carrinho import Cart, CartItem
from app.models.produto import Estoque, Fornecedor, Product
from app.services.carrinho import _fornecedor_do_produto, _origem_do_carrinho

_ALUNO = "00000000-0000-0000-0000-0000000000bb"


def headers_for(sub: str = _ALUNO) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, 'student', settings.jwt_secret)}"}


async def _parceiro(db_session, nome: str) -> Fornecedor:
    f = Fornecedor(nome=nome, origem_rotulo=f"{nome}, SP")
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)
    return f


async def _produto(db_session, *, nome: str, fornecedor: Fornecedor | None) -> Product:
    p = Product(name=nome, type="mobiliario", price=Decimal("10.00"), sku=nome[:60])
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    if fornecedor is not None:
        db_session.add(Estoque(produto_id=p.id, fornecedor_id=fornecedor.id, quantidade=50))
        await db_session.commit()
    return p


async def test_two_items_from_the_same_partner_are_accepted(client, db_session):
    leroy = await _parceiro(db_session, "Leroy Merlin")
    a = await _produto(db_session, nome="Luminária", fornecedor=leroy)
    b = await _produto(db_session, nome="Cadeira", fornecedor=leroy)

    for produto in (a, b):
        response = await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for(),
        )
        assert response.status_code == 201, produto.name

    assert len((await client.get("/cart", headers=headers_for())).json()["items"]) == 2


async def test_an_item_from_another_partner_is_409_with_a_displayable_message(client, db_session):
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    conflito = await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )

    assert conflito.status_code == 409
    detail = conflito.json()["detail"]
    assert "outro parceiro" in detail
    # A mensagem é para exibir sem reescrever: nada de código de erro cru,
    # nada de nome de tabela, nada de id.
    assert "Fornecedor" not in detail and "409" not in detail


async def test_the_rejected_item_never_lands_in_the_cart(client, db_session):
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )

    itens = (await client.get("/cart", headers=headers_for())).json()["items"]
    assert [i["name"] for i in itens] == ["Apostila"]


async def test_emptying_the_cart_releases_the_origin(client, db_session):
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    await client.delete(f"/cart/items/{apostila.id}", headers=headers_for())

    depois = await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )
    assert depois.status_code == 201


async def test_concurrent_adds_from_two_partners_never_build_a_mixed_cart(
    client, db_session, monkeypatch
):
    """A prova de que a regra está sob o lock, e não na tela.

    Sem `with_for_update()` na linha do carrinho antes da checagem, as duas
    requisições leem um carrinho vazio, as duas concluem "não há origem
    ainda", e as duas gravam — carrinho misto, sem erro nenhum aparecer.

    Puro `asyncio.gather()` NÃO basta para provar isso — achado da task 5
    deste mesmo plano: um teste de concorrência assim escrito passou 5/5
    mesmo com o `with_for_update()` apagado do código, porque o caminho
    trancado tinha poucos round-trips demais para a corrida perder de forma
    confiável (falso verde). O encontro abaixo (mesmo idioma de
    `test_concurrent_resolves_apply_the_price_delta_once`, em
    `tests/test_occurrences_routes.py`, e
    `test_concurrent_closes_apply_the_resolution_once`, em
    `tests/test_carrier_occurrences.py`) força as duas transações a se
    sobreporem de verdade no Postgres: a PRIMEIRA sessão de rota a chegar no
    commit espera a SEGUNDA sessão de rota abrir antes de seguir, dando à
    segunda a chance real de tentar o `SELECT ... FOR UPDATE` na mesma linha
    de carrinho enquanto a primeira ainda não soltou o lock.

    O carrinho é pré-criado fora do lock medido: sem isso, a corrida de
    `get_or_create_cart` (INSERT + commit do carrinho em si, para o mesmo
    `user_id` das duas requisições) se misturaria à medição e o teste
    deixaria de medir só o lock de `adicionar_item`.
    """
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    db_session.add(Cart(user_id=uuid.UUID(_ALUNO)))
    await db_session.commit()

    execute_real = AsyncSession.execute
    commit_real = AsyncSession.commit
    sessoes_vistas = {id(db_session)}
    a_segunda_abriu = asyncio.Event()
    estado = {"ja_esperou": False}

    async def execute_espiao(self, *args, **kwargs):
        if id(self) not in sessoes_vistas:
            sessoes_vistas.add(id(self))
            if len(sessoes_vistas) == 3:  # db_session + as duas sessões de rota
                a_segunda_abriu.set()
        return await execute_real(self, *args, **kwargs)

    async def commit_espiao(self):
        if id(self) != id(db_session) and not estado["ja_esperou"]:
            estado["ja_esperou"] = True
            await asyncio.wait_for(a_segunda_abriu.wait(), timeout=5)
            await asyncio.sleep(0.05)
        return await commit_real(self)

    monkeypatch.setattr(AsyncSession, "execute", execute_espiao)
    monkeypatch.setattr(AsyncSession, "commit", commit_espiao)

    async def _add(produto):
        return await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for(),
        )

    respostas = await asyncio.gather(_add(apostila), _add(luminaria))

    monkeypatch.undo()

    codigos = sorted(r.status_code for r in respostas)
    assert codigos == [201, 409], f"{respostas[0].text} / {respostas[1].text}"

    total_itens = (
        await db_session.execute(select(func.count()).select_from(CartItem))
    ).scalar_one()
    assert total_itens == 1


async def test_a_product_without_a_stock_row_is_treated_as_originless_and_allowed(
    client, db_session
):
    """Os seis produtos já semeados no banco do usuário não têm linha de
    estoque (medido: `app/seeds/products.py` nunca toca em `Estoque`). Até a
    task 11 dar-lhes um fornecedor, um produto sem origem não pode travar o
    carrinho de ninguém — ele não CONFLITA com nada porque não tem origem
    para conflitar.

    A task 11 elimina esse caso do banco; este teste garante que o caminho
    existe e é benigno enquanto ele durar, em vez de virar 500 ou 409 falso.
    """
    edu = await _parceiro(db_session, "Edu")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    orfao = await _produto(db_session, nome="Órfão", fornecedor=None)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post(
        "/cart/items", json={"product_id": str(orfao.id), "quantity": 1}, headers=headers_for()
    )
    assert response.status_code == 201


async def test_adding_more_of_an_item_already_in_the_cart_still_works(client, db_session):
    leroy = await _parceiro(db_session, "Leroy Merlin")
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)
    for _ in range(2):
        response = await client.post(
            "/cart/items",
            json={"product_id": str(luminaria.id), "quantity": 1},
            headers=headers_for(),
        )
        assert response.status_code == 201
    itens = (await client.get("/cart", headers=headers_for())).json()["items"]
    assert itens[0]["quantity"] == 2


async def test_a_product_stocked_by_two_suppliers_is_added_without_a_500(client, db_session):
    """Defeito na literal do brief: `_fornecedor_do_produto` filtrava só por
    `produto_id` e usava `scalar_one_or_none()`. `Estoque` tem
    `uq_produto_fornecedor` na PAR (produto_id, fornecedor_id), não em
    `produto_id` sozinho — um produto com dois fornecedores gera duas
    linhas, e `scalar_one_or_none()` estouraria `MultipleResultsFound` (500)
    em vez de resolver para uma. Mesmo defeito que a task 3 já teve em
    `obter_estoque_do_produto` (`app/services/estoque.py`), corrigido lá com
    `order_by(Estoque.id).limit(1)` — replicado aqui para que as duas
    funções resolvam o MESMO fornecedor para o MESMO produto.
    """
    fornecedor_a = await _parceiro(db_session, "Fornecedor A")
    fornecedor_b = await _parceiro(db_session, "Fornecedor B")
    produto = await _produto(db_session, nome="Cadeira Dupla", fornecedor=fornecedor_a)
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor_b.id, quantidade=20))
    await db_session.commit()

    response = await client.post(
        "/cart/items", json={"product_id": str(produto.id), "quantity": 1}, headers=headers_for()
    )
    assert response.status_code == 201


async def test_origem_do_carrinho_agrees_with_fornecedor_do_produto_for_the_same_product(
    db_session,
):
    """`_origem_do_carrinho` não tinha `order_by(Estoque.id)` — fix round 1.

    `uq_produto_fornecedor` é um índice único composto em
    `(produto_id, fornecedor_id)`. Uma consulta por igualdade em
    `produto_id` percorrida por esse índice devolve os `fornecedor_id`
    casados em ORDEM DE ÍNDICE (por `fornecedor_id`), não em ordem de
    `Estoque.id`. `_fornecedor_do_produto` tem `order_by(Estoque.id)`
    explícito e por isso é imune a isso; `_origem_do_carrinho`, sem
    `order_by`, deixava a ordem do `LIMIT 1` a critério do plano.

    Este teste grava as duas linhas de estoque do produto DELIBERADAMENTE
    fora de ordem entre as duas chaves (a linha do fornecedor com
    `fornecedor_id` MENOR é gravada DEPOIS, então ganha o `Estoque.id`
    MAIOR) e desliga `enable_seqscan`/`enable_bitmapscan` só NA TRANSAÇÃO
    do teste (`SET LOCAL` — nunca `ALTER DATABASE`/`ALTER SYSTEM`, e nunca
    no banco de desenvolvimento: esta sessão fala com `commerce_test`) para
    forçar de forma determinística, em tabela de teste minúscula, o mesmo
    plano guiado por índice que o revisor mediu manualmente contra
    `commerce_test`. Medido (sem a correção, chamando as funções
    diretamente): `_fornecedor_do_produto` resolve para o fornecedor B
    (menor `Estoque.id`, 2 no exemplo medido), `_origem_do_carrinho` sem
    `order_by` resolve para o fornecedor A (1) sob o plano guiado por
    índice — divergência confirmada, teste falha antes da correção.

    Consequência em produção: um estudante adiciona este produto (validado
    contra o fornecedor B); ao adicionar de novo o MESMO produto,
    `_origem_do_carrinho` informa a origem do carrinho como A — 409 falso
    num item genuinamente do mesmo parceiro. Espelhado, admite em silêncio
    um item de outro parceiro: o próprio carrinho misto que esta task existe
    para impedir.

    Chamar as duas funções PRIVADAS diretamente (não via `POST /cart/items`)
    é deliberado: a rota abre uma sessão nova por requisição (dependência
    `get_db` sobrescrita em `conftest.py`), fora do alcance de um `SET
    LOCAL` emitido a partir do teste. Tentar forçar o mesmo plano através do
    roundtrip HTTP exigiria remendar a fábrica de sessões da app só para
    este teste — desproporcional ao problema. Testar as funções de serviço
    diretamente, na mesma sessão que também prepara os dados, é o jeito
    honesto de forçar o plano sem inventar infraestrutura nova de teste.

    Depois da correção (`.order_by(Estoque.id)` em `_origem_do_carrinho`),
    esta asserção passa INDEPENDENTE do plano: `ORDER BY` é honrado pelo
    Postgres não importa o método de acesso escolhido, com ou sem os `SET
    LOCAL` acima — é a invariante que interessa, não a implementação.
    """
    fornecedor_a = await _parceiro(db_session, "Fornecedor A")  # fornecedor_id menor
    fornecedor_b = await _parceiro(db_session, "Fornecedor B")  # fornecedor_id maior
    produto = await _produto(db_session, nome="Dupla Origem", fornecedor=None)

    # Estoque do fornecedor B (fornecedor_id MAIOR) gravado PRIMEIRO -> Estoque.id MENOR.
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor_b.id, quantidade=1))
    await db_session.commit()
    # Estoque do fornecedor A (fornecedor_id MENOR) gravado DEPOIS -> Estoque.id MAIOR.
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor_a.id, quantidade=1))
    await db_session.commit()

    cart = Cart(user_id=uuid.UUID(_ALUNO))
    db_session.add(cart)
    await db_session.commit()
    await db_session.refresh(cart)
    db_session.add(CartItem(cart_id=cart.id, product_id=produto.id, quantity=1))
    await db_session.commit()

    canonical = await _fornecedor_do_produto(db_session, produto.id)
    assert canonical == fornecedor_b.id  # menor Estoque.id vence, por construção

    await db_session.execute(text("SET LOCAL enable_seqscan = off"))
    await db_session.execute(text("SET LOCAL enable_bitmapscan = off"))

    origem = await _origem_do_carrinho(db_session, cart.id)
    assert origem == canonical


# ── Revisão final de branch, finding 3 ─────────────────────────────────────
#
# `POST /orders/{id}/rebuy` é o SEGUNDO chamador de
# `cart_services.adicionar_item`, e capturava só `CartProductNotFoundError`.
# A regra de origem única (task 8) levanta `CarrinhoOrigemMistaError` do mesmo
# ponto — que escapava sem handler, 500 onde `POST /cart/items` devolve 409.
#
# A suíte herdada não via isto porque `test_orders_parity.py` monta carrinho e
# pedido a partir de produtos SEM linha de estoque — um estado que o seed da
# spec B torna impossível em produção. Este teste é o mínimo que exercita o
# caminho com estoque real, sem tocar nas fixtures de paridade.


async def test_rebuying_into_a_cart_of_another_partner_is_409_not_500(client, db_session):
    from app.models.pedido import Order, OrderItem

    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    # Pedido passado de ORIGEM ÚNICA — nada de exótico, o caso comum.
    pedido = Order(user_id=uuid.UUID(_ALUNO), status="CRIADO", total=Decimal("10.00"))
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    db_session.add(
        OrderItem(
            order_id=pedido.id,
            product_id=apostila.id,
            product_name=apostila.name,
            unit_price=Decimal("10.00"),
            quantity=1,
        )
    )
    await db_session.commit()

    # O carrinho de hoje já tem item de OUTRO parceiro.
    atual = await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )
    assert atual.status_code == 201

    response = await client.post(f"/orders/{pedido.id}/rebuy", headers=headers_for())

    assert response.status_code == 409
    assert "outro parceiro" in response.json()["detail"]
