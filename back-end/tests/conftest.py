from collections.abc import AsyncIterator

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_session
from app.core.redis_client import get_redis
from app.main import app


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    # Module models are imported lazily here so each domain's tables register
    # with Base.metadata before create_all. Add imports as modules are added.
    engine = create_async_engine(settings.DATABASE_URL_TEST, echo=False, future=True)
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
    # Run before every test — covers tests that use `client` (commits from the
    # route-level session) without forcing them to also request `db_session`.
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
async def redis_client() -> AsyncIterator[aioredis.Redis]:
    client = aioredis.from_url(
        settings.REDIS_URL_TEST,
        encoding="utf-8",
        decode_responses=True,
    )
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def client(
    test_session_factory: async_sessionmaker[AsyncSession],
    redis_client: aioredis.Redis,
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    async def override_get_redis() -> aioredis.Redis:
        return redis_client

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
