"""Testes de paridade de `/orders` — porte de
`legacy/tests/modules/orders/test_routes.py` (task C6).

Adaptações mecânicas: sem prefixo `/api`; `Product`/`Order` importados dos
models do commerce (`app.models.produto`/`app.models.pedido`); auth via
`headers_for` local — o commerce-service não tem módulo de auth nem tabela
de usuário, então as fixtures `created_user`/`auth_headers`/`seeded_products`
do conftest do legacy (que importam `app.modules.auth.*`) não portam; cada
arquivo de teste do commerce declara o seu próprio `headers_for` (o padrão
já repetido em `tests/test_orders_routes.py`, `tests/test_admin_routes.py`
etc.). 401 → 403 nos casos de "requer autenticação": divergência medida na
task B0 do bloco B — `edu-common` responde 403 para header ausente e 401 só
para token presente e inválido/expirado; o legacy responde 401 nos dois.

Adaptação NÃO mecânica: o legacy resolve `address_id` chamando
`addresses_services.get_address` na MESMA sessão de banco (mesmo monólito).
Aqui a resolução é HTTP contra o auth-users-service (outro banco) — ver
`app/services/auth_client.py::get_address` e `app/routers/pedidos.py`. Os
casos que exercitam `address_id` remendam `app.routers.pedidos.get_address`
— o nome onde o ROUTER importa a função (constraint 14 do brief), não
`app.services.auth_client.get_address` onde ela é definida. O caso feliz
("snapshota o endereço") e o caso "sem endereço" viram testes de SERVIÇO em
`test_orders_services_parity.py`, porque a função nova
(`criar_pedido_do_carrinho`) recebe `address: dict | None` já resolvido, não
`address_id` — só o caso de ownership/id inválido
(`test_rejects_address_of_another_user` no legacy) depende da resolução HTTP
e por isso mora aqui, em `TestCheckoutAddress` abaixo.

NÃO portado: `TestRebuy` (`test_rebuy_repopulates_cart`,
`test_rebuy_unknown_order_returns_404`) — os dois batem em `POST
/orders/{id}/rebuy`, que não está no escopo desta task: não aparece na
lista de Interfaces/Produces do brief nem no código do Step 5, e não tem
consumidor Flutter (`grep -rn "rebuy" front-end-flutter/lib/` não devolve
nada). O terceiro teste de "rebuy" do legacy
(`TestRebuyRepopulatesCart.test_order_items_can_refill_cart`, em
`test_services.py`) NÃO bate na rota — só prova que os itens do pedido dão
para realimentar o carrinho via `cart_services.add_item`, uma propriedade
do MODELO de dados, não da rota — esse SIM foi portado, em
`test_orders_services_parity.py`. Ver task-C6-report.md para o registro
completo desta decisão.

`test_lifecycle.py` e `test_status_pipeline.py` do legacy também não são
portados — carve-out declarado da task (constraint 22 do plano do bloco C):
não há simulador de avanço de status na fase 2
(`advance_order_status_task.delay` não é portado).
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pedido import Order
from app.models.produto import Product
from app.services.auth_client import AuthServiceUnavailableError

ALUNO = "00000000-0000-0000-0000-0000000000a1"


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
    """Porte de `legacy/tests/modules/orders/conftest.py::seeded_products`,
    adaptando só o import de `Product`."""
    products = [
        Product(
            name="Cálculo", type="Livro", subtype="Mat", description="", price=Decimal("100.00")
        ),
        Product(
            name="Caderno", type="Material", subtype="Pap", description="", price=Decimal("24.50")
        ),
    ]
    db_session.add_all(products)
    await db_session.commit()
    for p in products:
        await db_session.refresh(p)
    return products


@pytest.fixture
async def filled_cart(client: AsyncClient, seeded_products: list[Product]) -> list[Product]:
    """Porte de `legacy/tests/modules/orders/conftest.py::filled_cart`
    (1x produto0, 100.00; 2x produto1, 24.50 — total 149.00). O legacy monta
    o carrinho chamando `cart_services.add_item` direto na sessão; aqui o
    carrinho só é mutável pela rota HTTP (`POST /cart/items`) — não há
    atalho de sessão que valha manter, e as rotas de carrinho já estão
    portadas e testadas (`test_cart_parity.py`)."""
    await client.post(
        "/cart/items",
        json={"product_id": str(seeded_products[0].id), "quantity": 1},
        headers=headers_for("student", sub=ALUNO),
    )
    await client.post(
        "/cart/items",
        json={"product_id": str(seeded_products[1].id), "quantity": 2},
        headers=headers_for("student", sub=ALUNO),
    )
    return seeded_products


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/orders")
        # 403, não 401 — ver o docstring do módulo.
        assert r.status_code == 403

    async def test_create_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/orders")
        assert r.status_code == 403


class TestCreateOrder:
    async def test_checkout_from_cart_returns_order(
        self, client: AsyncClient, filled_cart: list[Product]
    ) -> None:
        r = await client.post(
            "/orders",
            json={"payment_method": "Visa ••••1234"},
            headers=headers_for("student", sub=ALUNO),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["total"] == "149.00"
        assert body["payment_method"] == "Visa ••••1234"
        assert len(body["items"]) == 2
        assert body["items"][0]["unit_price"] in {"100.00", "24.50"}

    async def test_checkout_empty_body_defaults_payment(
        self, client: AsyncClient, filled_cart: list[Product]
    ) -> None:
        r = await client.post("/orders", headers=headers_for("student", sub=ALUNO))
        assert r.status_code == 201, r.text
        assert r.json()["payment_method"] == ""

    async def test_checkout_empty_cart_returns_400(self, client: AsyncClient) -> None:
        r = await client.post("/orders", headers=headers_for("student", sub=ALUNO))
        assert r.status_code == 400

    async def test_cart_is_empty_after_checkout(
        self, client: AsyncClient, filled_cart: list[Product]
    ) -> None:
        await client.post("/orders", headers=headers_for("student", sub=ALUNO))
        r = await client.get("/cart", headers=headers_for("student", sub=ALUNO))
        assert r.json()["items"] == []


class TestListOrders:
    async def test_lists_created_order(
        self, client: AsyncClient, filled_cart: list[Product]
    ) -> None:
        await client.post("/orders", headers=headers_for("student", sub=ALUNO))
        r = await client.get("/orders", headers=headers_for("student", sub=ALUNO))
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestOrderImagePresign:
    async def test_create_order_item_image_url_is_presigned(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        product = Product(
            name="Produto com imagem",
            type="Livro",
            subtype="Mat",
            description="",
            price=Decimal("50.00"),
            image_url="products/test-order-presign.png",
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)

        await client.post(
            "/cart/items",
            json={"product_id": str(product.id), "quantity": 1},
            headers=headers_for("student", sub=ALUNO),
        )

        r = await client.post(
            "/orders",
            json={"payment_method": "PIX"},
            headers=headers_for("student", sub=ALUNO),
        )
        assert r.status_code == 201, r.text
        items = r.json()["items"]
        assert len(items) == 1
        image_url = items[0]["image_url"]
        assert "X-Amz-Signature" in image_url or "X-Amz-Credential" in image_url


class TestCheckoutAddress:
    """Não existe assim no legacy — ver o docstring do módulo para o porquê
    de só o caso de ownership/id inválido morar aqui (os outros dois viram
    teste de serviço). `test_checkout_when_auth_service_is_down_returns_503`
    é cobertura nova: o ramo `except AuthServiceUnavailableError` do router
    (Step 5 do brief) não tinha nenhum teste em lugar nenhum antes desta
    task — mesmo ramo, mesmo padrão do `criar_review` não coberto em
    `app/routers/produtos.py` (gap pré-existente, fora do escopo desta
    task)."""

    async def test_checkout_with_a_valid_address_snapshots_it_onto_the_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        filled_cart: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        endereco = {
            "label": "Casa",
            "zip_code": "13201-005",
            "street": "Rua das Flores",
            "number": "42",
            "complement": "Apto 3",
            "neighborhood": "Centro",
            "city": "Jundiaí",
            "state": "SP",
        }

        async def _get_address_falso(raw_token: str, address_id: uuid.UUID) -> dict:
            return endereco

        monkeypatch.setattr("app.routers.pedidos.get_address", _get_address_falso)

        r = await client.post(
            "/orders",
            json={"payment_method": "PIX", "address_id": str(uuid.uuid4())},
            headers=headers_for("student", sub=ALUNO),
        )
        assert r.status_code == 201, r.text

        # `OrderOut` (contrato do aluno) não expõe os campos `ship_*` — a
        # prova é direta no banco, mesma técnica de
        # `test_order_carries_the_shipping_snapshot` em test_orders_routes.py.
        pedido = (
            await db_session.execute(select(Order).where(Order.id == uuid.UUID(r.json()["id"])))
        ).scalar_one()
        assert pedido.ship_street == "Rua das Flores"
        assert pedido.ship_city == "Jundiaí"
        assert pedido.ship_label == "Casa"

    async def test_checkout_with_an_invalid_address_id_returns_400(
        self,
        client: AsyncClient,
        filled_cart: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _get_address_ausente(raw_token: str, address_id: uuid.UUID) -> None:
            return None

        monkeypatch.setattr("app.routers.pedidos.get_address", _get_address_ausente)

        r = await client.post(
            "/orders",
            json={"payment_method": "PIX", "address_id": str(uuid.uuid4())},
            headers=headers_for("student", sub=ALUNO),
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "Invalid delivery address"

    async def test_checkout_when_auth_service_is_down_returns_503(
        self,
        client: AsyncClient,
        filled_cart: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _get_address_indisponivel(raw_token: str, address_id: uuid.UUID) -> None:
            raise AuthServiceUnavailableError("auth-users-service indisponível")

        monkeypatch.setattr("app.routers.pedidos.get_address", _get_address_indisponivel)

        r = await client.post(
            "/orders",
            json={"payment_method": "PIX", "address_id": str(uuid.uuid4())},
            headers=headers_for("student", sub=ALUNO),
        )
        assert r.status_code == 503

    async def test_checkout_forwards_the_callers_own_bearer_to_get_address(
        self,
        client: AsyncClient,
        filled_cart: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Achado 3 da revisão da task C6: nenhum teste provava que
        `get_address` recebia o BEARER DO CHAMADOR (`user["raw_token"]`) —
        os três dublês acima (`_get_address_falso`,
        `_get_address_ausente`, `_get_address_indisponivel`) ignoram o
        argumento que recebem. Repassar o token de quem chamou (em vez de
        uma credencial própria do commerce) é todo o design de segurança
        de `get_address`: mantém a autorização no serviço DONO do dado
        (ver docstring de `app/services/auth_client.py`). Um espião que
        captura o argumento e o compara com o token real que a requisição
        carregou fecha essa lacuna."""
        tokens_recebidos: list[str] = []

        async def _get_address_espiao(raw_token: str, address_id: uuid.UUID) -> dict:
            tokens_recebidos.append(raw_token)
            return {
                "label": "Casa",
                "zip_code": "13201-005",
                "street": "Rua das Flores",
                "number": "42",
                "complement": "Apto 3",
                "neighborhood": "Centro",
                "city": "Jundiaí",
                "state": "SP",
            }

        monkeypatch.setattr("app.routers.pedidos.get_address", _get_address_espiao)

        headers = headers_for("student", sub=ALUNO)
        r = await client.post(
            "/orders",
            json={"payment_method": "PIX", "address_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert r.status_code == 201, r.text

        token_da_requisicao = headers["Authorization"].removeprefix("Bearer ")
        assert tokens_recebidos == [token_da_requisicao]


async def test_the_total_comes_from_the_catalog_not_from_the_request(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Prova de mutação (constraint 11 do brief): a rota antiga compunha o
    total com o `preco_unitario` da requisição e nunca importava o model de
    produto. `preco_unitario` no corpo abaixo é ignorado — `OrderCreateIn`
    não declara esse campo, e `extra="forbid"` não foi adicionado (ver
    task-C6-report.md, seção "Escolhas registradas")."""
    produto = Product(name="Guia", type="apostila", price=Decimal("49.90"))
    db_session.add(produto)
    await db_session.commit()

    await client.post(
        "/cart/items",
        json={"product_id": str(produto.id), "quantity": 2},
        headers=headers_for("student", sub=ALUNO),
    )
    response = await client.post(
        "/orders",
        json={"payment_method": "PIX", "preco_unitario": "0.01"},
        headers=headers_for("student", sub=ALUNO),
    )

    assert response.status_code == 201
    assert response.json()["total"] == "99.80"


def _e_select_lock_cart_checkout(stmt: object) -> bool:
    """Identifica, pela FORMA da query, o `select(Cart).where(Cart.user_id
    == user_id).with_for_update()` de `criar_pedido_do_carrinho`
    (`app/services/pedidos.py`). Medido com `str(stmt)`:

        'SELECT carts.id, carts.user_id, carts.created_at, carts.updated_at
        \\nFROM carts \\nWHERE carts.user_id = :user_id_1 FOR UPDATE'

    De propósito NÃO exige `FOR UPDATE` no texto — mesma razão de
    `_e_select_lock_carrinho` em `test_cart_parity.py`: a prova de mutação
    (Step 5 do achado 1 da revisão) remove só a cláusula
    `.with_for_update()`, e o detector precisa continuar reconhecendo a
    MESMA instrução sob mutação, senão o teste trava esperando um evento
    que nunca dispara em vez de ir vermelho pelo motivo certo.

    `get_or_create_cart` (`app/services/carrinho.py`) compila para o MESMO
    texto sem o `FOR UPDATE` final — mas só é chamado pelas rotas de
    `/cart`, nunca por `POST /orders`, e o teste abaixo só exercita
    `/orders` concorrentemente, então a ambiguidade não se materializa
    aqui (mesma ressalva que o docstring de `_e_select_lock_carrinho` faz
    para o próprio arquivo)."""
    texto = str(stmt)
    return texto.startswith(
        "SELECT carts.id, carts.user_id, carts.created_at, carts.updated_at \nFROM carts"
    )


class TestCheckoutLockConcurrency:
    """Prova o `.with_for_update()` de `criar_pedido_do_carrinho`
    (`app/services/pedidos.py`) — achado 1 da revisão da task C6, regra 3
    do CLAUDE.md (leitura->escrita sobre recurso compartilhado precisa ser
    atômica).

    Medido pela revisão: removendo só o `.with_for_update()` da linha, a
    suíte inteira continuava "243 passed" — nenhum teste existente pegava
    a ausência do lock. E medido que duas requisições `POST /orders`
    concorrentes contra o MESMO carrinho, SEM o lock, produzem DOIS
    pedidos (o "duplo toque" que o docstring de `criar_pedido_do_carrinho`
    promete impedir); COM o lock, uma vira 201 e a outra 400 "Cart is
    empty" — a segunda encontra o carrinho já esvaziado pela primeira.

    `test_second_checkout_on_emptied_cart_raises` (portado do legacy, em
    `test_orders_services_parity.py`) prova checkout duplicado
    SEQUENCIAL — não uma corrida real. Nem o legacy nem esta task tinham
    um teste de concorrência para este lock antes desta rodada. Mesmo
    padrão de `test_cart_parity.py::TestCartLockConcurrency` (task B8), que
    prova o lock equivalente do carrinho.

    Limitação declarada (mesma de `test_cart_parity.py`): um teste destes,
    num único processo/event loop, prova a ORDEM LÓGICA das operações e
    exercita um lock de linha real do Postgres entre duas conexões
    distintas (duas `AsyncSession`) — não prova contenção entre processos
    ou réplicas distintas do serviço.
    """

    async def test_concurrent_checkout_does_not_create_two_orders(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        produto = Product(
            name="Caderno", type="Material", subtype="Pap", description="", price=Decimal("24.50")
        )
        db_session.add(produto)
        await db_session.commit()
        await db_session.refresh(produto)

        headers = headers_for("student", sub=ALUNO)
        await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers,
        )

        segundo_lock_disparado = asyncio.Event()
        estado = {"locks_cart": 0, "commits": 0}

        execute_real = AsyncSession.execute
        commit_real = AsyncSession.commit

        async def _execute_que_avisa(self: AsyncSession, *args: object, **kwargs: object):
            if args and _e_select_lock_cart_checkout(args[0]):
                estado["locks_cart"] += 1
                if estado["locks_cart"] == 2:
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

        body = {"payment_method": "PIX"}
        r1, r2 = await asyncio.gather(
            client.post("/orders", json=body, headers=headers),
            client.post("/orders", json=body, headers=headers),
        )

        status_codes = sorted([r1.status_code, r2.status_code])
        assert status_codes == [201, 400], (
            f"esperava [201, 400] (uma cria o pedido, a outra encontra o "
            f"carrinho já esvaziado), achou {status_codes}: "
            f"r1={r1.status_code} {r1.text!r} / r2={r2.status_code} {r2.text!r}"
        )

        pedidos = await client.get("/orders", headers=headers)
        assert pedidos.status_code == 200
        assert len(pedidos.json()) == 1, (
            f"esperava exatamente 1 pedido, achou {len(pedidos.json())} — "
            "o lock deveria ter impedido um segundo pedido do mesmo carrinho"
        )
