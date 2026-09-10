from collections.abc import AsyncIterator

import httpx
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


@pytest.fixture(autouse=True)
def _block_real_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trava estrutural: nenhum teste pode mandar e-mail de verdade.

    Copiado de `back-end/commerce-service/tests/conftest.py` (mesma técnica,
    mesmo motivo: um `monkeypatch` que remenda a função de alto nível não
    IMPEDE estruturalmente uma chamada real caso um teste futuro esqueça de
    aplicá-lo). Aqui, o único chamador de rede é o backend `resend` de
    `app/services/email.py` — sem este bloqueio, um teste com o backend
    `email_backend=resend` mal configurado (ex.: sem monkeypatch de
    `httpx.AsyncClient.post`) mandaria um POST de verdade para a API do
    Resend, com uma senha de carregamento no corpo.

    `httpx.AsyncClient()` sem `transport=` explícito usa
    `httpx.AsyncHTTPTransport` por baixo — é esse método que qualquer request
    real acabaria atravessando. O teste do backend `resend`
    (`test_the_resend_backend_posts_to_the_api`) remenda
    `httpx.AsyncClient.post` diretamente, então intercepta a chamada ANTES de
    ela chegar ao transporte e não é afetado por este patch. O `client` deste
    conftest usa `ASGITransport`, uma classe diferente — também não passa
    por aqui.
    """

    async def _blocked(self, request: httpx.Request) -> httpx.Response:
        raise RuntimeError(f"chamada de rede real tentada: {request.url}")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _blocked)


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    from app.models import device_token as device_token_models  # noqa: F401
    from app.models import notificacao as notificacao_models  # noqa: F401
    from app.models import staff as staff_models  # noqa: F401

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
async def client(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
