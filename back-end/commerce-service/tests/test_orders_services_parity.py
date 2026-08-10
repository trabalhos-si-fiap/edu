"""Testes de paridade da camada de serviço de pedidos — porte de
`legacy/tests/modules/orders/test_services.py` (task C6).

Adaptações em relação ao legacy, além da troca de imports:
- `services.create_order_from_cart`/`list_orders`/`get_order` →
  `services.criar_pedido_do_carrinho`/`listar_pedidos`/`buscar_pedido`
  (nomes em português, convenção do commerce-service — mesma troca já feita
  em `carrinho.py`/`produtos.py` nas tasks B6/B8).
- `EmptyCart`/`OrderNotFound` → `EmptyCartError`/`OrderNotFoundError`
  (`ruff` N818 — ver `app/exceptions.py`).
- O legacy usa um `User` real (`created_user`) porque `orders.user_id` é FK
  lógica para a tabela de usuários DO PRÓPRIO MONÓLITO. Aqui o
  commerce-service não tem tabela de usuários — `orders.user_id` sempre foi
  FK lógica sem constraint física, então um `uuid.uuid4()` solto (fixture
  `user_id`) serve ao mesmo propósito, mesmo padrão já usado em
  `test_cart_services_parity.py`.
- `filled_cart` chama `carrinho_services.adicionar_item` (nome português) em
  vez de `cart_services.add_item`, mesma sessão — isso continua sendo um
  atalho válido aqui porque estes são testes de SERVIÇO, não de rota; o
  carrinho e o pedido são o MESMO serviço/processo/sessão, ao contrário do
  endereço (outro microserviço, ver `test_orders_parity.py`).

`TestCheckoutAddressSnapshot` NÃO porta `test_rejects_address_of_another_user`
do legacy: no legacy, o próprio `create_order_from_cart` resolvia
`address_id` e levantava `AddressNotFound` para um id de outro usuário. Aqui
`criar_pedido_do_carrinho` recebe `address: dict | None` JÁ resolvido — a
validação de existência/ownership do `address_id` aconteceu um passo antes,
via HTTP (`app.routers.pedidos.get_address`), fora da camada de serviço. Esse
caso foi portado como teste de ROTA em `test_orders_parity.py::TestCheckoutAddress`,
remendando `get_address` para devolver `None`. Os outros dois casos desta
classe (endereço válido / sem endereço) continuam sendo teste de serviço
porque não dependem de resolução alguma — só de o dict chegar pronto.

`TestRebuyRepopulatesCart.test_order_items_can_refill_cart` é portado
integralmente: não bate em nenhuma rota (`/rebuy` não existe nesta task, ver
`test_orders_parity.py`), só prova que os itens de um pedido dão para
realimentar o carrinho via `carrinho_services.adicionar_item` — propriedade
do MODELO de dados (`product_id`/`quantity` em `OrderItem`), que continua
valendo.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EmptyCartError, OrderNotFoundError
from app.models.carrinho import CartItem
from app.models.pedido import PedidoStatusHistorico
from app.models.produto import Product
from app.schemas.carrinho import CartItemIn
from app.services import carrinho as carrinho_services
from app.services import pedidos as services
from app.services.status_pedido import StatusPedido


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
    """Porte de `legacy/tests/modules/orders/conftest.py::seeded_products`."""
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
async def filled_cart(
    db_session: AsyncSession, user_id: uuid.UUID, seeded_products: list[Product]
) -> list[Product]:
    """Porte de `legacy/tests/modules/orders/conftest.py::filled_cart` (1x
    produto0, 100.00; 2x produto1, 24.50 — total 149.00)."""
    await carrinho_services.adicionar_item(
        db_session, user_id, CartItemIn(product_id=seeded_products[0].id, quantity=1)
    )
    await carrinho_services.adicionar_item(
        db_session, user_id, CartItemIn(product_id=seeded_products[1].id, quantity=2)
    )
    return seeded_products


class TestCreateOrderFromCart:
    async def test_builds_order_and_empties_cart(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        order = await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")

        assert order.total == Decimal("149.00")
        assert order.payment_method == "PIX"
        assert len(order.items) == 2

        # O carrinho ficou vazio.
        remaining = (
            await db_session.execute(select(func.count()).select_from(CartItem))
        ).scalar_one()
        assert remaining == 0

        # Guarda de regressão (achado 2 da revisão da task C6): `Order.id` é
        # um default Python (`new_uuid`), avaliado só no FLUSH. Sem o
        # `await db.flush()` entre `db.add(order)` e a construção de
        # `PedidoStatusHistorico(order_id=order.id, ...)`
        # (app/services/pedidos.py::criar_pedido_do_carrinho), a linha de
        # histórico nasce com `order_id = NULL` — silenciosamente, porque a
        # coluna não é `NOT NULL` (medido no Red desta task, ver
        # task-C6-report.md). O bug foi medido e corrigido, mas até esta
        # rodada nenhuma asserção travava a regressão.
        historico = (
            (
                await db_session.execute(
                    select(PedidoStatusHistorico).where(
                        PedidoStatusHistorico.status == StatusPedido.CRIADO.value
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(historico) == 1
        assert historico[0].order_id == order.id

    async def test_snapshots_unit_price(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        order = await services.criar_pedido_do_carrinho(db_session, user_id, "")
        by_name = {i.product_name: i for i in order.items}
        assert by_name["Cálculo"].unit_price == filled_cart[0].price

    async def test_empty_cart_raises(self, db_session: AsyncSession, user_id: uuid.UUID) -> None:
        with pytest.raises(EmptyCartError):
            await services.criar_pedido_do_carrinho(db_session, user_id, "")

    async def test_second_checkout_on_emptied_cart_raises(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")
        with pytest.raises(EmptyCartError):
            await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")


class TestListAndGet:
    async def test_lists_user_orders_desc(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")
        orders = await services.listar_pedidos(db_session, user_id, limit=50, offset=0)
        assert len(orders) == 1
        assert orders[0].items

    async def test_get_unknown_raises(self, db_session: AsyncSession, user_id: uuid.UUID) -> None:
        with pytest.raises(OrderNotFoundError):
            await services.buscar_pedido(db_session, user_id, uuid.uuid4())

    async def test_get_enforces_ownership(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        order = await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")
        other_user = uuid.uuid4()
        with pytest.raises(OrderNotFoundError):
            await services.buscar_pedido(db_session, other_user, order.id)


class TestRebuyRepopulatesCart:
    async def test_order_items_can_refill_cart(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        order = await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")
        # Carrinho esvaziado pelo checkout; realimenta a partir do pedido.
        for item in order.items:
            await carrinho_services.adicionar_item(
                db_session,
                user_id,
                CartItemIn(product_id=item.product_id, quantity=item.quantity),
            )
        cart = await carrinho_services.obter_carrinho(db_session, user_id)
        assert cart.total == order.total


class TestCheckoutAddressSnapshot:
    async def test_snapshots_address_onto_order(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
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

        order = await services.criar_pedido_do_carrinho(
            db_session, user_id, "PIX", address=endereco
        )

        assert order.ship_street == "Rua das Flores"
        assert order.ship_number == "42"
        assert order.ship_city == "Jundiaí"
        assert order.ship_state == "SP"
        assert order.ship_zip_code == "13201-005"
        assert order.ship_label == "Casa"

    async def test_without_address_leaves_snapshot_empty(
        self, db_session: AsyncSession, user_id: uuid.UUID, filled_cart: list[Product]
    ) -> None:
        order = await services.criar_pedido_do_carrinho(db_session, user_id, "PIX")
        assert order.ship_street is None
