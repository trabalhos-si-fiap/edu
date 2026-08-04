from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import services as auth_services
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterIn
from app.modules.auth.security import create_access_token
from app.modules.cart import services as cart_services
from app.modules.cart.schemas import CartItemIn
from app.modules.products.models import Product


@pytest.fixture
async def created_user(db_session: AsyncSession) -> User:
    data = RegisterIn(
        name="Maria Silva",
        email="maria@example.com",
        phone="11999998888",
        birth_date=date(1995, 6, 15),
        education_level="Vestibulando",
        password="Secret!1",
    )
    return await auth_services.register(db_session, data)


@pytest.fixture
def auth_headers(created_user: User) -> dict[str, str]:
    token = create_access_token(created_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
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


@pytest.fixture(autouse=True)
def captured_pipeline_kickoffs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Stop checkout from hitting the broker and capture the status-pipeline
    kickoff. Autouse so every test that creates an order stays offline; the
    trigger test reads the captured calls."""
    from app.modules.orders import tasks

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks.advance_order_status_task,
        "delay",
        lambda order_id, to_status: calls.append((order_id, to_status)),
    )
    return calls


@pytest.fixture
async def filled_cart(
    db_session: AsyncSession, created_user: User, seeded_products: list[Product]
) -> list[Product]:
    """Put 1x product0 (100.00) and 2x product1 (24.50) into the user's cart."""
    await cart_services.add_item(
        db_session, created_user.id, CartItemIn(product_id=seeded_products[0].id, quantity=1)
    )
    await cart_services.add_item(
        db_session, created_user.id, CartItemIn(product_id=seeded_products[1].id, quantity=2)
    )
    return seeded_products
