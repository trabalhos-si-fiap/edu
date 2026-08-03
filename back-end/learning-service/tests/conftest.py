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
    from app.models import progresso as progresso_models  # noqa: F401
    from app.models import questao as questao_models  # noqa: F401
    from app.models import resposta as resposta_models  # noqa: F401
    from app.models import subtema as subtema_models  # noqa: F401

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
    """`ASGITransport` never roda o lifespan do app (`init_publisher()` nunca é
    chamado), então `app.events.publisher._publisher` fica sempre desconectado —
    qualquer rota que aguarde `publish_event` (`POST /diagnostico/responder`)
    estouraria `RuntimeError("EventPublisher not connected — call connect()
    first")` depois que o progresso/resposta já foi gravado no banco.

    O alvo do monkeypatch é o nome onde a ROTA importa `publish_event`, não
    onde ele é definido: `app/routers/diagnostico.py` faz `from
    app.events.publisher import publish_event`, o que copia a referência
    para o namespace do próprio módulo — remendar
    `app.events.publisher.publish_event` não afetaria essa cópia. Confirmado
    com `grep -rn "publish_event" app/` antes de escrever esta fixture.
    """

    async def _noop(routing_key: str, payload: dict) -> None:
        return None

    monkeypatch.setattr("app.routers.diagnostico.publish_event", _noop)


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


@pytest.fixture(autouse=True)
def fake_encoder(monkeypatch: pytest.MonkeyPatch):
    """Evita baixar `paraphrase-multilingual-MiniLM-L12-v2` na suíte.

    O nome real da função de carga do modelo é `_get_modelo()`, dentro de
    `app/services/embeddings.py` — NÃO `_carregar_modelo` em
    `classificacao_ia.py`/`recomendacao_semantica.py` como um rascunho
    anterior desta fixture supunha. Confirmado com:

        grep -n "SentenceTransformer\\|def .*model\\|_modelo" \\
            app/services/classificacao_ia.py app/services/recomendacao_semantica.py

    que não encontrou NENHUMA ocorrência nesses dois arquivos — ambos só
    importam `gerar_embedding`/`gerar_embeddings` de `embeddings.py`, que é
    quem de fato chama `_get_modelo()`. Um `monkeypatch.setattr` num nome
    que não existe, com `raising=False`, não faz nada silenciosamente — e a
    suíte baixaria o modelo de verdade (centenas de MB) no primeiro teste
    que exercitasse classificação/recomendação semântica.

    Só precisa de UM alvo (o módulo que de fato define `_get_modelo`):
    `gerar_embedding`/`gerar_embeddings` resolvem `_get_modelo` no
    namespace global do próprio `embeddings.py` em tempo de chamada, não
    importa se chamadas a partir de outro módulo.

    Devolve um vetor determinístico por texto, o suficiente para exercitar a
    lógica de similaridade sem carregar centenas de MB. Testes que precisam
    do modelo real levam a marca `slow` e não usam esta fixture.
    """
    import numpy as np

    class FakeEncoder:
        def encode(self, texts, **kwargs):
            # Espelha o contrato real do SentenceTransformer.encode: uma
            # string solta devolve um vetor 1D; uma lista de strings devolve
            # uma matriz 2D. `gerar_embedding` (singular) depende do
            # primeiro formato para que `similaridade_cosseno` (um
            # `np.dot` de dois vetores 1D) funcione — devolver sempre 2D
            # quebraria essa chamada com um shape mismatch silencioso.
            single = isinstance(texts, str)
            entrada = [texts] if single else texts
            vetores = np.vstack(
                [
                    np.array([len(t) % 7, sum(map(ord, t)) % 11, len(t.split()) % 5], dtype=float)
                    for t in entrada
                ]
            )
            return vetores[0] if single else vetores

    # `raising=True` (o default) de propósito, ao contrário do rascunho
    # original: agora que o nome foi confirmado, um `_get_modelo` renomeado
    # no futuro deve estourar a fixture (falha alta e óbvia), não deixar a
    # suíte baixar o modelo real em silêncio.
    monkeypatch.setattr("app.services.embeddings._get_modelo", lambda: FakeEncoder())
