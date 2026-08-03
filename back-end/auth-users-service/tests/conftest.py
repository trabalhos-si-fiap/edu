from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    from app.models import address as address_models  # noqa: F401
    from app.models import password_reset as password_reset_models  # noqa: F401
    from app.models import user as user_models  # noqa: F401

    engine = create_async_engine(settings.database_url_test, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def test_session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def _clean_tables(test_engine: AsyncEngine) -> AsyncIterator[None]:
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest.fixture
async def db_session(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
def _stub_publish_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ASGITransport` never runs the app's lifespan (`init_publisher()` is
    never called), so `app.events.publisher._publisher` stays disconnected —
    any route that awaits `publish_event` (`/auth/register`,
    `/auth/register-staff`) hits `RuntimeError("EventPublisher not
    connected — call connect() first")` after the DB row is already
    committed. Stub it at the router's own import site: `app/routers/auth.py`
    does `from app.events.publisher import publish_event`, which binds its
    own name in that module's namespace, so patching
    `app.events.publisher.publish_event` would not affect the router's
    already-bound reference.
    """

    async def _noop(routing_key: str, payload: dict) -> None:
        return None

    monkeypatch.setattr("app.routers.auth.publish_event", _noop)


@pytest.fixture
async def client(
    test_session_factory: async_sessionmaker[AsyncSession],
    _stub_publish_event: None,
) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
