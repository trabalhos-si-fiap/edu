from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin.auth import AdminAuth
from app.modules.auth.models import User
from tests.admin.conftest import make_request


def _backend(test_session_factory: async_sessionmaker[AsyncSession]) -> AdminAuth:
    return AdminAuth(secret_key="test-secret", session_factory=test_session_factory)


async def test_login_success_sets_session(
    test_session_factory: async_sessionmaker[AsyncSession], admin_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(form={"username": "admin@example.com", "password": "Secret!1"})

    assert await backend.login(request) is True
    assert request.session["user_id"] == str(admin_user.id)


async def test_login_wrong_password_returns_false(
    test_session_factory: async_sessionmaker[AsyncSession], admin_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(form={"username": "admin@example.com", "password": "wrong"})

    assert await backend.login(request) is False
    assert "user_id" not in request.session


async def test_login_non_admin_returns_false(
    test_session_factory: async_sessionmaker[AsyncSession], regular_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(form={"username": "user@example.com", "password": "Secret!1"})

    assert await backend.login(request) is False


async def test_logout_clears_session(
    test_session_factory: async_sessionmaker[AsyncSession],
):
    backend = _backend(test_session_factory)
    request = make_request(session={"user_id": "abc"})

    assert await backend.logout(request) is True
    assert "user_id" not in request.session


async def test_authenticate_valid_admin(
    test_session_factory: async_sessionmaker[AsyncSession], admin_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(session={"user_id": str(admin_user.id)})

    assert await backend.authenticate(request) is True


async def test_authenticate_no_session_returns_false(
    test_session_factory: async_sessionmaker[AsyncSession],
):
    backend = _backend(test_session_factory)
    request = make_request(session={})

    assert await backend.authenticate(request) is False


async def test_authenticate_demoted_user_clears_session(
    test_session_factory: async_sessionmaker[AsyncSession], regular_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(session={"user_id": str(regular_user.id)})

    assert await backend.authenticate(request) is False
    assert "user_id" not in request.session
