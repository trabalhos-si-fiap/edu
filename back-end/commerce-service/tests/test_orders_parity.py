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
