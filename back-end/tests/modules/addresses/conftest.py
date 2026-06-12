from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import services as auth_services
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterIn
from app.modules.auth.security import create_access_token


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


def make_address(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "label": "Casa",
        "zip_code": "01310-100",
        "street": "Av. Paulista",
        "number": "1000",
        "complement": "Apto 12",
        "neighborhood": "Bela Vista",
        "city": "São Paulo",
        "state": "SP",
    }
    base.update(overrides)
    return base
