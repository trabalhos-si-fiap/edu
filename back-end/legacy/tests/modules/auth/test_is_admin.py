from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import services as auth_services
from app.modules.auth.schemas import RegisterIn


async def test_new_user_is_not_admin_by_default(db_session: AsyncSession) -> None:
    user = await auth_services.register(
        db_session,
        RegisterIn(
            name="Ana",
            email="ana@example.com",
            phone="11999990000",
            birth_date=date(1995, 1, 1),
            education_level="Vestibulando",
            password="Secret!1",
        ),
    )
    assert user.is_admin is False
