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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.carrinho import Cart, CartItem
from app.models.produto import Estoque, Fornecedor, Product

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
