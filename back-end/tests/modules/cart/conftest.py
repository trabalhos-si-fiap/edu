from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import services as auth_services
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterIn
from app.modules.auth.security import create_access_token
from app.modules.products.models import Product


@pytest.fixture
async def created_user(db_session: AsyncSession) -> User:
    data = RegisterIn(
        name="Maria Silva",
        email="maria@example.com",
        phone="11999998888",
        birth_date=date(1995, 6, 15),
        education_level="Ensino Superior",
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
