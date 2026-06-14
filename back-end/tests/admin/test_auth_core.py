import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth import authenticate_admin, load_admin
from app.modules.auth.models import User


async def test_authenticate_admin_success(db_session: AsyncSession, admin_user: User):
    result = await authenticate_admin(db_session, "admin@example.com", "Secret!1")
    assert result is not None
    assert result.id == admin_user.id


async def test_authenticate_admin_wrong_password(db_session: AsyncSession, admin_user: User):
    assert await authenticate_admin(db_session, "admin@example.com", "nope") is None


async def test_authenticate_admin_non_admin_rejected(db_session: AsyncSession, regular_user: User):
    assert await authenticate_admin(db_session, "user@example.com", "Secret!1") is None


async def test_authenticate_admin_inactive_rejected(db_session: AsyncSession, inactive_admin: User):
    assert await authenticate_admin(db_session, "ghost@example.com", "Secret!1") is None


async def test_authenticate_admin_unknown_email(db_session: AsyncSession):
    # Caminho do DUMMY_PASSWORD_HASH — não deve levantar exceção, retorna None.
    assert await authenticate_admin(db_session, "missing@example.com", "Secret!1") is None


async def test_load_admin_returns_active_admin(db_session: AsyncSession, admin_user: User):
    result = await load_admin(db_session, str(admin_user.id))
    assert result is not None
    assert result.id == admin_user.id


async def test_load_admin_rejects_non_admin(db_session: AsyncSession, regular_user: User):
    assert await load_admin(db_session, str(regular_user.id)) is None


async def test_load_admin_rejects_inactive(db_session: AsyncSession, inactive_admin: User):
    assert await load_admin(db_session, str(inactive_admin.id)) is None


async def test_load_admin_rejects_garbage_id(db_session: AsyncSession):
    assert await load_admin(db_session, "not-a-uuid") is None
    assert await load_admin(db_session, None) is None


async def test_load_admin_rejects_unknown_uuid(db_session: AsyncSession):
    # UUID bem-formado mas sem usuário correspondente (ex: usuário deletado).
    assert await load_admin(db_session, str(uuid.uuid4())) is None
