"""Testes de paridade de `/cart` — porte de
`legacy/tests/modules/cart/test_routes.py` (task B8 do bloco B). Ver
`task-B8-report.md` para a lista completa de asserções adaptadas e para as
provas de ownership e de lock que este arquivo acrescenta (o legacy não tem
nenhuma das duas).
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.produto import Product

STUDENT_A = "00000000-0000-0000-0000-0000000000a1"
STUDENT_B = "00000000-0000-0000-0000-0000000000b2"


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
    """Porte de `legacy/tests/modules/cart/conftest.py::seeded_products`,
    adaptando só o import de `Product` (`app.modules.products.models` →
    `app.models.produto`)."""
    products = [
        Product(
            name="Cálculo Volume 1",
            type="Livro",
            subtype="Matemática",
            description="Cálculo",
            price=Decimal("100.00"),
        ),
        Product(
            name="Caderno",
            type="Material",
            subtype="Papelaria",
            description="200 folhas",
            price=Decimal("24.50"),
        ),
    ]
    db_session.add_all(products)
    await db_session.commit()
    for p in products:
        await db_session.refresh(p)
    return products


class TestAuthRequired:
    async def test_get_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/cart")
        # 403, não 401: ver a divergência registrada na task B0 do plano do bloco B.
        # O `edu-common` responde 403 para header ausente e 401 para token
        # inválido/expirado; o legacy responde 401 nos dois.
        assert r.status_code == 403

    async def test_add_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/cart/items", json={"product_id": str(uuid.uuid4())})
        # 403, não 401: mesma divergência de test_get_requires_auth acima.
        assert r.status_code == 403


class TestCartFlow:
    async def test_empty_cart(self, client: AsyncClient) -> None:
        r = await client.get("/cart", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["items"] == []
        assert body["total"] == "0.00"

    async def test_add_item_returns_cart_with_string_money(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]  # 100.00
        r = await client.post(
            "/cart/items",
            json={"product_id": str(product.id), "quantity": 2},
            headers=headers_for("student"),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["total"] == "200.00"
        item = body["items"][0]
        assert item["product_id"] == str(product.id)
        assert item["price"] == "100.00"
        assert item["subtotal"] == "200.00"
        assert item["quantity"] == 2
        assert item["name"] == product.name

    async def test_add_unknown_product_returns_404(self, client: AsyncClient) -> None:
        r = await client.post(
            "/cart/items",
            json={"product_id": str(uuid.uuid4()), "quantity": 1},
            headers=headers_for("student"),
        )
        assert r.status_code == 404
        # Acréscimo da B8: nem o legacy nem a primeira versão portada deste
        # arquivo checavam o TEXTO da mensagem — só o status code. O Step 3
        # do brief lista `404 "Product not found"` como comportamento a
        # preservar; sem esta linha, nada travava o texto.
        assert r.json()["detail"] == "Product not found"

    async def test_total_sums_multiple_products(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        await client.post(
            "/cart/items",
            json={"product_id": str(seeded_products[0].id), "quantity": 1},
            headers=headers_for("student"),
        )
        r = await client.post(
            "/cart/items",
            json={"product_id": str(seeded_products[1].id), "quantity": 2},
            headers=headers_for("student"),
        )
        # 100.00 + 2 * 24.50 = 149.00
        assert r.json()["total"] == "149.00"

    async def test_delete_decrements_then_removes(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await client.post(
            "/cart/items",
            json={"product_id": str(product.id), "quantity": 3},
            headers=headers_for("student"),
        )
        r = await client.delete(
            f"/cart/items/{product.id}?quantity=1", headers=headers_for("student")
        )
        assert r.status_code == 200
        assert r.json()["items"][0]["quantity"] == 2

        r = await client.delete(f"/cart/items/{product.id}", headers=headers_for("student"))
        assert r.status_code == 200
        assert r.json()["items"] == []

    async def test_delete_absent_item_returns_404(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.delete(
            f"/cart/items/{seeded_products[0].id}", headers=headers_for("student")
        )
        assert r.status_code == 404
        # Acréscimo da B8: mesma razão do teste equivalente em TestCartFlow
        # acima — o Step 3 do brief lista `404 "Item not in cart"` como
        # comportamento a preservar; nada checava o texto até aqui.
        assert r.json()["detail"] == "Item not in cart"


class TestCartCatalogDrift:
    """Acréscimo da B8: nenhum teste, no legacy ou na primeira versão
    portada, cobria o comportamento de borda mais fácil de perder do Step 3
    do brief: `montar_cart_out` OMITE o item cujo produto saiu do catálogo,
    em vez de estourar 500 (medido: `grep -rn "saiu do catálogo\\|produto is
    None" ../legacy/tests/modules/cart/` não acha nada — o legacy também não
    testa isso, só a implementação trata o caso, ver `services.py:68-70` do
    legacy e `montar_cart_out` aqui)."""

    async def test_item_whose_product_left_the_catalog_is_omitted_not_500(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        seeded_products: list[Product],
    ) -> None:
        produto_que_vai_sumir = seeded_products[0]
        produto_que_fica = seeded_products[1]

        r = await client.post(
            "/cart/items",
            json={"product_id": str(produto_que_vai_sumir.id), "quantity": 1},
            headers=headers_for("student"),
        )
        assert r.status_code == 201, r.text
        r = await client.post(
            "/cart/items",
            json={"product_id": str(produto_que_fica.id), "quantity": 1},
            headers=headers_for("student"),
        )
        assert r.status_code == 201, r.text

        # O produto sai do catálogo (delete direto no banco) sem que o item
        # do carrinho seja tocado — não há FK física entre cart_items e
        # products de propósito (ver docstring de CartItem em
        # app/models/carrinho.py), então a linha de cart_items sobrevive
        # apontando para um product_id que não existe mais.
        produto_no_banco = await db_session.get(Product, produto_que_vai_sumir.id)
        await db_session.delete(produto_no_banco)
        await db_session.commit()

        r = await client.get("/cart", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert [i["product_id"] for i in body["items"]] == [str(produto_que_fica.id)]
        # seeded_products[1] ("Caderno") custa 24.50 — ver a fixture acima.
        assert body["total"] == "24.50"


class TestCartImagePresign:
    async def test_get_cart_item_image_url_is_presigned(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        product = Product(
            name="Produto com imagem",
            type="Livro",
            subtype="Mat",
            description="",
            price=Decimal("50.00"),
            image_url="products/test-presign.png",
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)

        await client.post(
            "/cart/items",
            json={"product_id": str(product.id), "quantity": 1},
            headers=headers_for("student"),
        )

        r = await client.get("/cart", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert len(items) == 1
        image_url = items[0]["image_url"]
        assert "X-Amz-Signature" in image_url or "X-Amz-Credential" in image_url


class TestCartOwnership:
    """Não existe no legacy (confirmado: `grep -rn "def test" ../legacy/tests/modules/cart/`
    não tem nenhum teste com dois usuários). Acrescentado pela task B8 —
    regra 2 do CLAUDE.md (controle de acesso e ownership explícitos) e o
    CONTEXTO DO CONTROLADOR do brief, que exige prova nas três rotas.

    O carrinho é resolvido por `uuid.UUID(user["sub"])`; cada teste usa dois
    `sub` diferentes (`STUDENT_A`, `STUDENT_B`) para provar que nenhum enxerga
    ou modifica o carrinho do outro.
    """

    async def test_get_only_sees_own_cart(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        # A adiciona um item ao próprio carrinho.
        r = await client.post(
            "/cart/items",
            json={"product_id": str(seeded_products[0].id), "quantity": 1},
            headers=headers_for("student", sub=STUDENT_A),
        )
        assert r.status_code == 201, r.text

        # B nunca tocou o carrinho — GET dele tem que vir vazio, não com o
        # item de A.
        r = await client.get("/cart", headers=headers_for("student", sub=STUDENT_B))
        assert r.status_code == 200, r.text
        assert r.json()["items"] == []

    async def test_add_item_goes_to_own_cart_not_the_others(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        # A adiciona o produto 0; B adiciona o produto 1.
        await client.post(
            "/cart/items",
            json={"product_id": str(seeded_products[0].id), "quantity": 1},
            headers=headers_for("student", sub=STUDENT_A),
        )
        await client.post(
            "/cart/items",
            json={"product_id": str(seeded_products[1].id), "quantity": 1},
            headers=headers_for("student", sub=STUDENT_B),
        )

        cart_a = (await client.get("/cart", headers=headers_for("student", sub=STUDENT_A))).json()
        cart_b = (await client.get("/cart", headers=headers_for("student", sub=STUDENT_B))).json()

        assert [i["product_id"] for i in cart_a["items"]] == [str(seeded_products[0].id)]
        assert [i["product_id"] for i in cart_b["items"]] == [str(seeded_products[1].id)]

    async def test_delete_does_not_reach_the_others_cart(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        produto = seeded_products[0]
        # Só A tem o produto no carrinho.
        r = await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for("student", sub=STUDENT_A),
        )
        assert r.status_code == 201, r.text

        # B tenta remover o MESMO product_id — como B não tem esse item no
        # próprio carrinho (carrinhos são isolados por usuário), a rota tem
        # que devolver 404 "Item not in cart", não afetar o carrinho de A.
        hijack_response = await client.delete(
            f"/cart/items/{produto.id}", headers=headers_for("student", sub=STUDENT_B)
        )
        assert hijack_response.status_code == 404

        # O carrinho de A continua intacto.
        cart_a = (await client.get("/cart", headers=headers_for("student", sub=STUDENT_A))).json()
        assert len(cart_a["items"]) == 1
        assert cart_a["items"][0]["product_id"] == str(produto.id)


def _e_select_lock_carrinho(stmt: object) -> bool:
    """Identifica, pela FORMA da query, o `select(Cart.id).where(Cart.id ==
    cart.id)` de `adicionar_item`/`remover_item` — só ele seleciona
    unicamente a coluna `id` de `Cart` (`get_or_create_cart` seleciona o
    objeto inteiro, 4 colunas). Medido com `str(stmt)` (ver
    task-B8-report.md).

    De propósito NÃO exige `FOR UPDATE` no texto: o experimento de mutação
    (Step 5/prova de lock) remove só o `.with_for_update()` da linha e
    precisa que o detector continue reconhecendo a MESMA instrução — se ele
    dependesse de `FOR UPDATE`, o sinal nunca dispararia sob mutação e o
    teste travaria esperando um evento que nunca chega, em vez de ir
    vermelho pelo motivo certo.
    """
    return str(stmt).startswith("SELECT carts.id \n")


class TestCartLockConcurrency:
    """Prova os dois `.with_for_update()` de `app/services/carrinho.py`
    (constraint do task-B8-brief.md: "os dois with_for_update() são o
    coração da task"; regra 3 do CLAUDE.md).

    O legacy não tem teste de concorrência para o carrinho — medido com
    `grep -rn "asyncio.Event\\|concurrent" ../legacy/tests/modules/cart/`,
    sem resultado. Os dois testes abaixo são novos, escritos para esta task.

    O primeiro teste (item novo) usa sinal forçado — identifica a instrução
    SQL pela FORMA compilada (não por posição numérica de chamada, e não
    exigindo `FOR UPDATE`, ver `_e_select_lock_carrinho`), porque cada
    requisição faz vários `execute` antes do commit e a ordem de
    intercalação não é determinística (medido: uma primeira versão contava
    chamadas por posição numérica e travava em deadlock — o alvo nunca era
    alcançado porque o lock do carrinho já bloqueava a segunda requisição
    antes dela disparar a chamada contada). O sinal dispara quando a
    instrução-alvo é DISPARADA (antes do `await` resolver), e a espera fica
    no PRIMEIRO `commit` — mesmo padrão de
    `test_products_parity.py::TestReviewConcurrency` (task B7).

    O segundo teste (item já existente) usa concorrência NATURAL, sem sinal
    forçado — ver o docstring dele para a razão medida: forçar o sinal no
    lock do ITEM deadlocka quando o lock do CARRINHO também está presente
    (ele bloqueia a segunda requisição antes dela alcançar o lock do item).
    A prova isolada do lock do item está no relatório da task B8 (mutação
    com o lock do carrinho temporariamente removido), não neste arquivo.

    Limitação declarada (mesma do bloco A/B7): um teste destes, num único
    processo/event loop, prova a ORDEM LÓGICA das operações e exercita um
    lock de linha real do Postgres entre duas conexões distintas (duas
    `AsyncSession`) — não prova contenção entre processos ou réplicas
    distintas do serviço.
    """

    async def test_concurrent_add_of_a_new_product_does_not_lose_the_lock(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        seeded_products: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Duas requisições SIMULTÂNEAS adicionando o MESMO produto (que
        ainda não está no carrinho) não podem resultar em duas linhas de
        `CartItem` para o mesmo `(cart_id, product_id)` nem em quantidade
        perdida — o total tem que ser a soma das duas quantidades.

        Prova o lock do CARRINHO: sem ele, as duas requisições fariam o
        SELECT do item concorrentemente, as duas veriam `item is None`
        (nenhuma commitou ainda) e as duas tentariam inserir uma `CartItem`
        nova para o mesmo `(cart_id, product_id)` — a segunda a commitar bate
        no `UNIQUE(cart_id, product_id)` e estoura `IntegrityError` (500), em
        vez de acumular a quantidade.

        Pré-cria o carrinho com um GET antes da corrida: sem isso,
        `get_or_create_cart` faz seu PRÓPRIO commit (o de criar o carrinho)
        antes de qualquer lock ser disparado — esse commit seria o
        "primeiro commit" que o instrumento abaixo intercepta, e ele ficaria
        esperando um sinal que só dispara depois (deadlock, medido: a
        primeira versão deste teste sem o GET travava com `TimeoutError`
        na espera do sinal).
        """
        produto = seeded_products[0]
        await client.get("/cart", headers=headers_for("student"))

        segundo_lock_disparado = asyncio.Event()
        estado = {"locks_carrinho": 0, "commits": 0}

        execute_real = AsyncSession.execute
        commit_real = AsyncSession.commit

        async def _execute_que_avisa(self: AsyncSession, *args: object, **kwargs: object):
            if args and _e_select_lock_carrinho(args[0]):
                estado["locks_carrinho"] += 1
                if estado["locks_carrinho"] == 2:
                    segundo_lock_disparado.set()
            return await execute_real(self, *args, **kwargs)

        async def _commit_que_espera(self: AsyncSession, *args: object, **kwargs: object):
            estado["commits"] += 1
            if estado["commits"] == 1:
                await asyncio.wait_for(segundo_lock_disparado.wait(), timeout=5)
                await asyncio.sleep(0.01)
            return await commit_real(self, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "execute", _execute_que_avisa)
        monkeypatch.setattr(AsyncSession, "commit", _commit_que_espera)

        body = {"product_id": str(produto.id), "quantity": 2}
        r1, r2 = await asyncio.gather(
            client.post("/cart/items", json=body, headers=headers_for("student")),
            client.post("/cart/items", json=body, headers=headers_for("student")),
        )

        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text

        r = await client.get("/cart", headers=headers_for("student"))
        items = r.json()["items"]
        assert len(items) == 1, f"esperava 1 item, achou {len(items)}: {items}"
        assert items[0]["quantity"] == 4, (
            f"perdeu quantidade: quantity={items[0]['quantity']} (as duas leram "
            "'sem item' e cada uma tentou criar a própria linha)"
        )

    async def test_concurrent_add_to_existing_item_does_not_lose_the_increment(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        """Com o item JÁ existente no carrinho, duas requisições SIMULTÂNEAS
        acrescentando quantidade não podem perder um incremento — mesma
        classe de bug que `TestReviewConcurrency` provou para
        `rating_count` na B7, aqui para `CartItem.quantity`.

        SEM sinal forçado, de propósito (ao contrário do teste acima e do
        padrão da B7): medido que instrumentar um sinal em "a 2ª vez que o
        lock do ITEM dispara" TRAVA em deadlock enquanto o lock do CARRINHO
        também está presente — o carrinho é adquirido ANTES do item em
        `adicionar_item`, e fica retido até o commit, então a segunda
        requisição nunca alcança seu próprio lock de item antes de a
        primeira commitar; o sinal esperado nunca chega. Isso não é bug do
        teste, é a CONSEQUÊNCIA do lock do carrinho serializar tudo — ver
        `task-B8-report.md`, seção da prova de lock, para a discussão
        completa e para a prova isolada do lock do item (mutação com o lock
        do carrinho temporariamente removido, só então esta mesma asserção
        vira um teste que distingue o lock do item).

        Como o lock do carrinho, sozinho, já serializa esta requisição de
        ponta a ponta, este teste sem instrumentação é determinístico
        (não depende de sorte de agendamento) sob o código como está: prova
        que a soma não se perde, sem isolar qual dos dois locks é
        responsável — só a mutação no relatório isola isso.
        """
        produto = seeded_products[0]
        r = await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for("student"),
        )
        assert r.status_code == 201, r.text

        body = {"product_id": str(produto.id), "quantity": 3}
        r1, r2 = await asyncio.gather(
            client.post("/cart/items", json=body, headers=headers_for("student")),
            client.post("/cart/items", json=body, headers=headers_for("student")),
        )

        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text

        r = await client.get("/cart", headers=headers_for("student"))
        items = r.json()["items"]
        assert items[0]["quantity"] == 7, (
            f"perdeu incremento: quantity={items[0]['quantity']} (esperado 1 (seed) + 3 + 3 = 7)"
        )
