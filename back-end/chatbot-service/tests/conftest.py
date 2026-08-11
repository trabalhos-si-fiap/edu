"""Fixtures compartilhadas dos testes do Chatbot Service.

Desde a fase 2 este serviço TEM banco (`chatbot_db`), para o módulo
`support` — as fixtures `test_engine`/`test_session_factory`/`db_session`
abaixo cobrem isso, e o `client` passa a sobrescrever `get_db` com uma
sessão de teste. O outro estado global é o índice FAISS/encoder em memória
(`app/rag.py`) e os clientes Groq (`app/rag.py`,
`app/services/explicacao_questao.py`), ambos stubados aqui, sempre, para
nenhum teste baixar modelo nem tocar rede.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest
from edu_common.security import create_access_token
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
    from app.models import suporte as suporte_models  # noqa: F401 -- registra em Base.metadata

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
    return async_sessionmaker(test_engine, expire_on_commit=False)


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


@dataclass(frozen=True)
class StudentIdentity:
    """Um aluno de teste e o header pronto para autenticar como ele — os dois
    lados do mesmo token, para testes que gravam linhas com o MESMO `user_id`
    que a rota vai extrair do JWT."""

    user_id: uuid.UUID
    headers: dict[str, str]


@pytest.fixture
def student_identity() -> StudentIdentity:
    user_id = uuid.uuid4()
    token = create_access_token(
        sub=str(user_id),
        role="student",
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return StudentIdentity(user_id=user_id, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def auth_headers(student_identity: StudentIdentity) -> dict[str, str]:
    return student_identity.headers


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


class _FakeEncoder:
    """Substituto fiel de `SentenceTransformer.encode` para os dois call
    sites reais em `app/rag.py` (`buscar_contexto`, `inicializar_index`):
    ambos SEMPRE passam uma LISTA de strings com `convert_to_numpy=True`
    (nunca uma string solta), então `.encode` aqui sempre devolve uma
    matriz 2D — igual ao contrato real para esse formato de chamada.
    Nenhum call site usa `normalize_embeddings` (o índice é
    `faiss.IndexFlatL2`, distância L2, não cosseno) — diferente do fake
    encoder do learning-service, este não precisa normalizar para ser
    fiel ao real.
    """

    def encode(self, texts, **kwargs):
        return np.vstack(
            [
                np.array(
                    [len(t) % 7, sum(map(ord, t)) % 11, len(t.split()) % 5, len(t) % 5],
                    dtype=np.float32,
                )
                for t in texts
            ]
        )


@pytest.fixture(autouse=True)
def fake_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste pode baixar `all-MiniLM-L6-v2` do HuggingFace Hub.

    Nome real do loader confirmado com:

        grep -n "SentenceTransformer\\|faiss\\|def .*model\\|_modelo" app/rag.py

    → é `_get_modelo_embeddings()`. O rascunho do brief supunha
    `app.rag.carregar_indice` com `monkeypatch.setattr(..., raising=False)`
    — esse nome NÃO existe em nenhum lugar deste código; `raising=False`
    teria feito o patch ser um no-op silencioso, e a suíte baixaria o
    modelo de verdade (centenas de MB) no primeiro teste que exercitasse
    `/chat/ask`.

    `raising=True` (o default) de propósito: um `_get_modelo_embeddings`
    renomeado no futuro deve estourar esta fixture alto e claro, não
    deixar o download acontecer em silêncio.
    """
    monkeypatch.setattr("app.rag._get_modelo_embeddings", lambda: _FakeEncoder(), raising=True)


def _fake_completion(texto: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])


class FakeAsyncGroq:
    """Substituto de `groq.AsyncGroq` — nunca abre socket.

    Os dois call sites (`app/rag.py::responder`,
    `app/services/explicacao_questao.py::_get_client`) fazem
    `from groq import AsyncGroq`, o que copia a referência para o
    namespace de CADA módulo — por isso o alvo do patch é
    `app.rag.AsyncGroq` e `app.services.explicacao_questao.AsyncGroq`, não
    `groq.AsyncGroq`: remendar a origem não afetaria nenhuma das duas
    cópias já vinculadas em tempo de import. Mesmo princípio do aviso
    sobre `publish_event` na Recipe C do plano de migração.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        return _fake_completion("resposta de teste (stub, sem chamada real à Groq)")


@pytest.fixture(autouse=True)
def no_real_groq_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste pode fazer uma chamada de rede real à Groq — nem por
    GROQ_API_KEY vazia (o `.env` de teste não tem uma chave real), nem por
    engano. Os dois pontos de instanciação são substituídos por um dublê
    que nunca abre socket; testes que precisam simular uma falha do
    provedor sobrescrevem este patch localmente com um dublê que levanta.

    `explicacao_questao.py` guarda um singleton de módulo (`_client`) —
    resetado aqui para que o cliente (real ou de um teste anterior) nunca
    vaze para o próximo teste.
    """
    monkeypatch.setattr("app.rag.AsyncGroq", FakeAsyncGroq, raising=True)
    monkeypatch.setattr("app.services.explicacao_questao.AsyncGroq", FakeAsyncGroq, raising=True)

    import app.services.explicacao_questao as explicacao_questao_module

    explicacao_questao_module._client = None
