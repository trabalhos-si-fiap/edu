"""Testes de paridade da camada de serviço do carrinho — porte de
`legacy/tests/modules/cart/test_services.py` (task B8 do bloco B).

Adaptações em relação ao legacy, além da troca de imports:
- O legacy usa um `User` real (`created_user`, criado via
  `auth_services.register`) porque `Cart.user_id` é FK lógica para a tabela
  de usuários DO PRÓPRIO MONÓLITO. Aqui o commerce-service não tem tabela de
  usuários (auth é outro microserviço, outro banco) — `Cart.user_id` sempre
  foi uma FK lógica sem constraint física, então um `uuid.uuid4()` solto
  serve exatamente ao mesmo propósito nos testes, sem precisar criar linha
  nenhuma.
- `services.get_cart`/`add_item`/`remove_item` → `services.obter_carrinho`/
  `adicionar_item`/`remover_item` (nomes em português, convenção do
  commerce-service — ver `app/services/produtos.py`, que já fez a mesma
  troca ao portar `list_products`→`listar_produtos` etc. na task B6).
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import CartItemNotFoundError, CartProductNotFoundError
from app.models.produto import Product
from app.schemas.carrinho import CartItemIn
from app.services import carrinho as services


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
    """Porte de `legacy/tests/modules/cart/conftest.py::seeded_products`."""
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


class TestGetCart:
    async def test_empty_cart_has_zero_total(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        cart = await services.obter_carrinho(db_session, user_id)
        assert cart.items == []
        assert cart.total == 0


class TestAddItem:
    async def test_adds_item_and_computes_subtotal_and_total(
        self,
        db_session: AsyncSession,
        user_id: uuid.UUID,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]  # price 100.00
        cart = await services.adicionar_item(
            db_session, user_id, CartItemIn(product_id=product.id, quantity=2)
        )
        assert len(cart.items) == 1
        item = cart.items[0]
        assert item.quantity == 2
        assert item.subtotal == product.price * 2
        assert cart.total == product.price * 2

    async def test_adding_same_product_accumulates_quantity(
        self,
        db_session: AsyncSession,
        user_id: uuid.UUID,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.adicionar_item(
            db_session, user_id, CartItemIn(product_id=product.id, quantity=1)
        )
        cart = await services.adicionar_item(
            db_session, user_id, CartItemIn(product_id=product.id, quantity=3)
        )
        assert len(cart.items) == 1
        assert cart.items[0].quantity == 4

    async def test_unknown_product_raises(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        with pytest.raises(CartProductNotFoundError):
            await services.adicionar_item(
                db_session, user_id, CartItemIn(product_id=uuid.uuid4(), quantity=1)
            )


class TestRemoveItem:
    async def test_remove_whole_item(
        self,
        db_session: AsyncSession,
        user_id: uuid.UUID,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.adicionar_item(
            db_session, user_id, CartItemIn(product_id=product.id, quantity=3)
        )
        cart = await services.remover_item(db_session, user_id, product.id)
        assert cart.items == []
        assert cart.total == 0

    async def test_decrement_quantity(
        self,
        db_session: AsyncSession,
        user_id: uuid.UUID,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.adicionar_item(
            db_session, user_id, CartItemIn(product_id=product.id, quantity=5)
        )
        cart = await services.remover_item(db_session, user_id, product.id, quantity=2)
        assert cart.items[0].quantity == 3

    async def test_decrement_to_zero_removes_item(
        self,
        db_session: AsyncSession,
        user_id: uuid.UUID,
        seeded_products: list[Product],
    ) -> None:
        product = seeded_products[0]
        await services.adicionar_item(
            db_session, user_id, CartItemIn(product_id=product.id, quantity=2)
        )
        cart = await services.remover_item(db_session, user_id, product.id, quantity=5)
        assert cart.items == []

    async def test_remove_absent_item_raises(
        self,
        db_session: AsyncSession,
        user_id: uuid.UUID,
        seeded_products: list[Product],
    ) -> None:
        with pytest.raises(CartItemNotFoundError):
            await services.remover_item(db_session, user_id, seeded_products[0].id)
