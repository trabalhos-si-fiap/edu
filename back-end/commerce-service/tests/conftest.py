from collections.abc import AsyncIterator

import pytest
from fakeredis.aioredis import FakeRedis
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
from app.redis_client import get_redis


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    from app.models import ocorrencia as ocorrencia_models  # noqa: F401
    from app.models import pedido as pedido_models  # noqa: F401
    from app.models import produto as produto_models  # noqa: F401

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
def _stub_publish_event(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """`ASGITransport` nunca roda o lifespan do app (`init_publisher()` nunca é
    chamado), então `app.events.publisher._publisher` fica sempre desconectado —
    qualquer rota que aguarde `publish_event` estouraria `RuntimeError
    ("EventPublisher not connected — call connect() first")` depois que o
    pedido/ocorrência já foi gravado no banco.

    O alvo do monkeypatch é o nome onde CADA CHAMADOR importa `publish_event`,
    não onde ele é definido — `from app.events.publisher import publish_event`
    copia a referência para o namespace de quem importa, então remendar
    `app.events.publisher.publish_event` não afetaria nenhuma dessas cópias.
    Há TRÊS chamadores, confirmados com `grep -rn "publish_event" app/`:
    `app/routers/pedidos.py`, `app/routers/ocorrencias.py` (quatro publishes) e
    `app/routers/separacao.py`.

    Devolve a lista de eventos capturados (`(routing_key, payload)`, na ordem
    de publicação) — fix round 2: testes de idempotência (ex: prova de que
    `confirm-payment` chamado duas vezes só publica UM `order.status_changed`,
    não dois) declaram esta fixture diretamente, além de `client`. O pytest
    resolve a MESMA instância cacheada para as duas dependências dentro do
    mesmo teste (fixture de escopo `function`, pedida duas vezes no mesmo
    teste = uma única resolução), então a lista devolvida aqui é a mesma que
    `client` já está usando por baixo dos panos.
    """
    eventos: list[tuple[str, dict]] = []

    async def _capturar(routing_key: str, payload: dict) -> None:
        eventos.append((routing_key, payload))

    monkeypatch.setattr("app.routers.pedidos.publish_event", _capturar)
    monkeypatch.setattr("app.routers.ocorrencias.publish_event", _capturar)
    monkeypatch.setattr("app.routers.separacao.publish_event", _capturar)

    return eventos


@pytest.fixture
async def redis_client() -> AsyncIterator[FakeRedis]:
    """Redis de teste via `fakeredis`, não um Redis real.

    Decisão de 2026-08-07 (ver task-B2-brief.md, CONTEXTO DO CONTROLADOR): o
    `edu-redis` no ar é a instância viva do usuário, e a fixture original do
    legacy (`redis.asyncio.from_url` + `flushdb` nas duas pontas) rodaria
    contra ela.

    Sem `server=` compartilhado, cada `FakeRedis()` abre seu próprio backend
    em memória — instância nova não enxerga chave gravada por outra instância
    (medido: duas `FakeRedis()` distintas, `set` numa e `get` na outra devolve
    `None`; ver task-B2-report.md). Como esta fixture é `function`-scoped, uma
    instância por teste já garante isolamento sem precisar de `flushdb`.
    """
    client = FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def client(
    test_session_factory: async_sessionmaker[AsyncSession],
    redis_client: FakeRedis,
    _stub_publish_event: list[tuple[str, dict]],
) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    async def _override_get_redis() -> FakeRedis:
        return redis_client

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fake_encoder(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Evita baixar `paraphrase-multilingual-MiniLM-L12-v2` na suíte.

    O nome real da função de carga do modelo é `_get_modelo()`, dentro de
    `app/services/embeddings.py` — NÃO `_carregar_modelo` como o rascunho do
    brief supunha. Confirmado com:

        grep -n "SentenceTransformer\\|def .*model\\|_modelo" \\
            app/services/embeddings.py app/services/substituicao_ia.py

    que só encontra `_get_modelo`/`_modelo` em `embeddings.py` —
    `substituicao_ia.py` só importa `gerar_embedding`/`gerar_embeddings` de lá,
    então um único alvo de patch (`app.services.embeddings._get_modelo`) basta:
    as duas funções resolvem `_get_modelo` no namespace global do próprio
    `embeddings.py` em tempo de chamada, não importa quem as invoca.

    Testes marcados `slow` fazem esta fixture retornar sem remendar nada —
    para rodar contra o modelo real de propósito.
    """
    if request.node.get_closest_marker("slow") is not None:
        return

    import numpy as np

    class FakeEncoder:
        def encode(self, texts, **kwargs):
            # Espelha o contrato real do SentenceTransformer.encode: uma
            # string solta devolve um vetor 1D; uma lista de strings devolve
            # uma matriz 2D. `gerar_embedding` (singular, embeddings.py:32)
            # passa uma string solta; `gerar_embeddings` (plural) passa uma
            # lista — `similaridade_cosseno` é um `np.dot` de dois vetores
            # 1D, então devolver sempre 2D quebraria essa chamada com um
            # shape mismatch silencioso.
            single = isinstance(texts, str)
            entrada = [texts] if single else texts
            vetores = np.vstack(
                [
                    np.array(
                        [len(t) % 7, sum(map(ord, t)) % 11, len(t.split()) % 5],
                        dtype=np.float32,
                    )
                    for t in entrada
                ]
            )
            # `normalize_embeddings=True` está presente em TODA chamada real
            # (embeddings.py:32,39) — sem honrar isso aqui,
            # `similaridade_cosseno` (que só É a similaridade de cosseno
            # porque assume vetores de norma 1) devolveria o produto escalar
            # bruto em vez de um valor em [-1, 1], inflando o
            # `LIMIAR_SIMILARIDADE` de `substituicao_ia.py` de forma
            # silenciosa. Guarda contra norma zero (texto vazio) para não
            # gerar NaN, que se propagaria sem erro pelo `except Exception`
            # largo de `sugerir_substitutos`.
            if kwargs.get("normalize_embeddings"):
                normas = np.linalg.norm(vetores, axis=1, keepdims=True)
                normas[normas == 0] = 1.0
                vetores = (vetores / normas).astype(np.float32)
            return vetores[0] if single else vetores

    # `raising=True` (o default) de propósito: agora que o nome foi
    # confirmado, um `_get_modelo` renomeado no futuro deve estourar a
    # fixture (falha alta e óbvia), não deixar a suíte baixar o modelo real
    # em silêncio — `raising=False` no rascunho do brief faria exatamente
    # isso, sem avisar ninguém.
    monkeypatch.setattr("app.services.embeddings._get_modelo", lambda: FakeEncoder())
