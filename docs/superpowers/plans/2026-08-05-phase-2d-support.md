# Fase 2 — Bloco D: suporte no chatbot-service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Servir `GET /support` e `POST /support` a partir do `chatbot-service`, com o mesmo contrato do legacy — o que exige dar ao serviço a primeira camada de persistência que ele nunca teve.

**Architecture:** O `chatbot-service` **não tem banco**: sem `database.py`, sem `alembic/`, e o compose zera o `DATABASE_URL` dele de propósito. Portar `support` para lá é acrescentar um eixo de infraestrutura, não um router. A maior parte deste plano é isso; as duas rotas em si são trinta linhas.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic, asyncpg, Pydantic v2, pytest, ruff, uv, PostgreSQL, Docker Compose.

**Spec:** [`docs/superpowers/specs/2026-08-04-microservices-migration-phase-2-design.md`](../specs/2026-08-04-microservices-migration-phase-2-design.md) — bloco D.
**Depende de:** [bloco A](2026-08-05-phase-2a-security-and-fleet.md) concluído — task 15 (o whitelist de `requer_papel` saiu do `pyproject`), task 19 (`get_current_user_id` é o nome canônico) e task 20 (`async_sessionmaker`, que este serviço adota já de nascença). **Independente dos blocos B e C**; pode rodar em paralelo com eles.

> `modules/support/test_routes.py` é a **17ª** suíte do critério de aceite binário da fase 2. Sem este bloco, o critério não fecha.

---

## Global Constraints

**Do `CLAUDE.md`:**

1. Nunca concatenar input do usuário em SQL — sempre ORM com bind params.
2. Todo endpoint com controle de acesso explícito **e** filtro de ownership.
3. Read→write em recurso compartilhado é atômico.
4. Todo input com limite: `max_length` no model **e** no schema; listagem paginada.
5. Nenhum segredo no código. `loguru.logger`, nunca `print()`.
6. Schemas com campos explícitos.
7. Comparação de segredo com `hmac.compare_digest()`.
8. TDD sem exceção: Red → Green → Refactor.
9. Conventional Commits, um commit por unidade lógica, `git diff --staged` antes de cada commit.
10. `ruff check` e `ruff format` limpos antes de commitar.

**Do backlog da fase 1:**

11. **Todo teste de regressão precisa ser provado quebrando o que ele trava.**
12. **Nunca alimentar o teste com a própria constante da implementação.**
13. **Desconfie do instrumento antes de concluir que o código está limpo.**
14. **Monkeypatch no módulo que define, não no que importa.**
15. **`default=` do SQLAlchemy é client-side** — `server_default=` junto.
16. **Comentário que era verdade e virou mentira.** Este bloco invalida três comentários que hoje afirmam que o serviço não tem banco: o docstring de `app/config.py`, o de `tests/conftest.py`, e a linha `DATABASE_URL: ""` do compose. Os três têm que mudar junto com o código.
17. **`docker ps` reporta saudável container que não serve.**

**Deste bloco:**

18. **Réplica exata é o critério.** A task D4 começa portando `legacy/tests/modules/support/test_routes.py`.
19. **`GET /support` devolve array puro e `POST /support` devolve a LISTA COMPLETA com 201.** Não é um erro de desenho — é o contrato: o app substitui a conversa inteira pela resposta do POST.
20. **A armadilha do `initdb.d`.** O compose unificado monta o `initdb.d` **script a script**, porque não dá para montar duas pastas no mesmo destino. Um script novo que não ganhe a linha de mount vira **no-op silencioso** — funciona no compose do legacy, que monta a pasta toda, e não roda aqui. E há **duas cópias** do mesmo script (uma em `postgres/initdb.d/`, outra em `scripts/`); as duas precisam mudar.

**Comandos:**

```bash
cd back-end/chatbot-service && uv run pytest -q
cd back-end/chatbot-service && uv run ruff check . && uv run ruff format --check .
make services-test
make services-dbs      # cria os bancos num volume já inicializado
make services-migrate  # aplica alembic em todo serviço com banco
```

---

## File Structure

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `back-end/postgres/initdb.d/10-create-service-databases.sh` | `chatbot_db` e `chatbot_test` na lista | D1 |
| `back-end/scripts/create-service-databases.sh` | **a segunda cópia** do mesmo script | D1 |
| `back-end/docker-compose.yml` | `DATABASE_URL` do chatbot deixa de ser vazio | D1 |
| `Makefile` | `chatbot-service` entra em `DB_SERVICES` | D1 |
| `chatbot-service/pyproject.toml` | `sqlalchemy`, `asyncpg`, `alembic` | D2 |
| `chatbot-service/app/config.py` | `database_url`, `database_url_test` | D2 |
| `chatbot-service/app/database.py` | **novo** — engine, `async_session`, `Base`, `get_db` | D2 |
| `chatbot-service/alembic.ini` | **novo** | D2 |
| `chatbot-service/alembic/env.py` · `script.py.mako` · `versions/` | **novos** | D2 |
| `chatbot-service/.env.example` | as duas variáveis novas | D2 |
| `chatbot-service/tests/conftest.py` | fixtures de banco + `auth_headers` | D2 |
| `chatbot-service/app/models/__init__.py` · `suporte.py` | **novos** — `SupportMessage` | D3 |
| `chatbot-service/alembic/versions/<hash>_baseline.py` | **novo** | D3 |
| `chatbot-service/app/schemas.py` | `SupportMessageIn`/`Out` | D4 |
| `chatbot-service/app/services/suporte.py` | **novo** | D4 |
| `chatbot-service/app/routers/__init__.py` · `suporte.py` | **novos** | D4 |
| `chatbot-service/app/main.py` | registra o router | D4 |
| `chatbot-service/tests/test_support_parity.py` | **novo** — portado | D4 |

---

### Task D1: `chatbot_db` existe e o serviço sabe dele

Infraestrutura antes de código. Se esta task não estiver certa, tudo o que vier depois falha com "database does not exist" ou — pior — passa nos testes e não funciona no compose.

**Files:**
- Modify: `back-end/postgres/initdb.d/10-create-service-databases.sh`
- Modify: `back-end/scripts/create-service-databases.sh`
- Modify: `back-end/docker-compose.yml`
- Modify: `Makefile`

**Interfaces:**
- Produces: bancos `chatbot_db` e `chatbot_test` no Postgres compartilhado; `DATABASE_URL`/`DATABASE_URL_TEST` injetados no container do chatbot; `chatbot-service` na lista `DB_SERVICES` do Makefile.

- [ ] **Step 1: Confirme que as duas cópias do script são idênticas**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app/back-end
diff postgres/initdb.d/10-create-service-databases.sh scripts/create-service-databases.sh && echo "IDÊNTICOS"
```

Expected: `IDÊNTICOS`. **Se divergirem, pare e reconcilie primeiro** — este bloco não é o lugar de descobrir que dois scripts de criação de banco discordam.

> Por que existem duas cópias: `postgres/initdb.d/` é montado no entrypoint do Postgres (roda uma vez, na inicialização do volume); `scripts/` é o que `make services-dbs` alimenta via `docker compose exec -T postgres bash <`, para criar os bancos num volume **já inicializado**. Um clone limpo usa o primeiro; um ambiente existente usa o segundo. Editar só um deles produz um ambiente onde o banco existe e outro onde não — sem erro em lugar nenhum.

- [ ] **Step 2: Acrescente `chatbot_db` nos dois**

Nos **dois** arquivos, a linha:

```bash
DATABASES="auth_db learning_db commerce_db notification_db analytics_db"
DATABASES="$DATABASES auth_test learning_test commerce_test notification_test analytics_test"
```

vira:

```bash
DATABASES="auth_db learning_db commerce_db notification_db analytics_db chatbot_db"
DATABASES="$DATABASES auth_test learning_test commerce_test notification_test analytics_test"
DATABASES="$DATABASES chatbot_test"
```

- [ ] **Step 3: Acrescente a linha de mount — a armadilha**

Abra `back-end/docker-compose.yml` no bloco `postgres`. O comentário nas linhas 44-50 já avisa:

> "ATENÇÃO: por ser script a script e não pasta inteira, um arquivo novo em qualquer um dos dois `initdb.d` NÃO passa a rodar sozinho — ele vira um no-op silencioso aqui, ainda que funcione no compose do legacy, que monta a pasta toda. Ao acrescentar um script, acrescente a linha aqui."

Nesta task você **não** acrescentou um script novo — editou um que já está montado. **Confirme** que `./postgres/initdb.d/10-create-service-databases.sh` continua na lista de `volumes` do `postgres`. Se estiver, não há linha a acrescentar; se não estiver, acrescente-a.

Registre no relatório qual dos dois casos era. É a diferença entre "o aviso não se aplicava" e "o aviso salvou a task".

- [ ] **Step 4: Dê ao chatbot o `DATABASE_URL`**

No bloco `chatbot-service` do compose, substitua:

```yaml
    environment:
      # O chatbot não tem banco e não publica nem consome eventos (ver o
      # docstring de app/config.py). DATABASE_URL é zerada pelo mesmo motivo
      # do gateway: o .env compartilhado traz a do legacy.
      DATABASE_URL: ""
      DATABASE_URL_TEST: ""
```

por:

```yaml
    environment:
      # O chatbot ganhou banco na fase 2 (módulo `support`). Antes destas
      # duas linhas serem preenchidas, elas eram zeradas de propósito, pelo
      # mesmo motivo do gateway: o `.env` compartilhado traz a URL do legacy,
      # e um serviço sem banco não pode herdá-la por acidente. Continua sem
      # publicar nem consumir eventos.
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/chatbot_db
      DATABASE_URL_TEST: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/chatbot_test
```

e acrescente ao `depends_on` do chatbot (que hoje provavelmente não tem, ou só tem o learning):

```yaml
    depends_on:
      postgres:
        condition: service_healthy
```

> **Não** use o anchor `*depends-db-mq`: ele inclui o RabbitMQ, e o chatbot continua não publicando nem consumindo eventos. Depender de algo que não se usa é ruído que a próxima pessoa vai tentar entender.

- [ ] **Step 5: Ponha o chatbot em `DB_SERVICES`**

No `Makefile`:

```makefile
DB_SERVICES := auth-users-service learning-service commerce-service notification-service analytics-service chatbot-service
```

`make services-migrate` percorre essa lista. Sem esta linha, a migration do chatbot nunca é aplicada por ninguém — e o serviço sobe, responde `/health`, e devolve 500 na primeira chamada a `/support`. É exatamente a armadilha 8 da fase 1 com outra roupa.

- [ ] **Step 6: Crie os bancos e prove que existem**

```bash
cd /home/elias/programming/fiap/estuda_app
make stack-up
make services-dbs
cd back-end && docker compose exec -T postgres psql -U edu -d postgres -c "\l" | grep chatbot
```

Expected: `chatbot_db` e `chatbot_test` na saída.

> `make services-dbs` roda `scripts/create-service-databases.sh` (a cópia do host). Se ele não criar os dois bancos, você editou só a cópia do `initdb.d` — volte ao Step 2.

- [ ] **Step 7: Prove que o container enxerga a URL**

```bash
cd back-end && docker compose up -d chatbot-service && docker compose restart chatbot-service
docker compose exec -T chatbot-service printenv DATABASE_URL
curl -s localhost:8104/health
```

Expected: a URL com `/chatbot_db`, e `{"status":"ok"}`. **Constraint 17:** o `restart` não é decorativo — o watcher do granian pode ter travado no `up -d`.

- [ ] **Step 8: Commit**

```bash
cd /home/elias/programming/fiap/estuda_app
git add back-end/postgres/initdb.d/10-create-service-databases.sh \
        back-end/scripts/create-service-databases.sh \
        back-end/docker-compose.yml Makefile
git diff --staged
git commit -m "feat(chatbot): give the service its own database

The support module lands here in phase 2 and this service never had
persistence: DATABASE_URL was deliberately blanked so the shared .env could
not leak the legacy URL into it. Both copies of the database-creation script
are updated — one runs from the Postgres entrypoint on a fresh volume, the
other from make services-dbs on an existing one, and editing only one leaves
an environment where the database silently does not exist.

chatbot-service joins DB_SERVICES so make services-migrate reaches it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task D2: a camada de banco do serviço

**Files:**
- Modify: `back-end/chatbot-service/pyproject.toml`
- Modify: `back-end/chatbot-service/app/config.py`
- Create: `back-end/chatbot-service/app/database.py`
- Create: `back-end/chatbot-service/alembic.ini`
- Create: `back-end/chatbot-service/alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/.gitkeep`
- Modify: `back-end/chatbot-service/.env.example`
- Modify: `back-end/chatbot-service/tests/conftest.py`
- Modify: `back-end/chatbot-service/Dockerfile` (se ele copiar arquivos por lista)

**Interfaces:**
- Produces:
  - `settings.database_url: str`, `settings.database_url_test: str`
  - `app.database.engine`, `app.database.async_session: async_sessionmaker[AsyncSession]`, `app.database.Base`, `app.database.get_db()`
  - Fixtures `test_engine`, `test_session_factory`, `db_session`, `auth_headers`, `student_identity` no conftest; o `client` existente passa a sobrescrever `get_db`.

- [ ] **Step 1: Escreva o teste que falha**

Crie `back-end/chatbot-service/tests/test_database.py`:

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import Base, async_session, get_db


def test_the_session_factory_is_the_modern_one():
    """`async_sessionmaker`, não `sessionmaker(..., class_=AsyncSession)`.

    Os cinco serviços que nasceram antes usam a forma legada da 1.4 (o bloco
    A os converteu). Este nasce já na forma da 2.x — não vale reintroduzir
    a dívida que acabou de ser paga.
    """
    assert isinstance(async_session, async_sessionmaker)


def test_base_is_declarative():
    assert hasattr(Base, "metadata")


async def test_get_db_yields_a_working_session(db_session: AsyncSession):
    resultado = await db_session.execute(text("SELECT 1"))
    assert resultado.scalar_one() == 1
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/chatbot-service && uv run pytest tests/test_database.py -v`

Expected: `ModuleNotFoundError: No module named 'app.database'`.

- [ ] **Step 3: Acrescente as dependências**

Em `back-end/chatbot-service/pyproject.toml`, em `[project].dependencies`:

```toml
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
```

Run: `cd back-end/chatbot-service && uv sync`

- [ ] **Step 4: Acrescente os settings**

Em `back-end/chatbot-service/app/config.py`, dentro de `Settings`:

```python
    # Banco próprio, criado na fase 2 para o módulo `support` (ver
    # docs/superpowers/plans/2026-08-05-phase-2d-support.md). Sem default: o
    # serviço não pode subir apontando para lugar nenhum, e um default
    # apontando para o banco do legacy seria pior que estourar no import.
    database_url: str
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/chatbot_test"
```

E **atualize o docstring do módulo** (constraint 16). Ele hoje diz que `rabbitmq_url`/`exchange_name` foram removidas porque nada publica eventos — isso continua verdade e fica. Mas se ele afirmar em algum ponto que o serviço não tem banco, corrija; acrescente:

```
Desde a fase 2 este serviço TEM banco (`chatbot_db`), para o módulo
`support`. Ele continua sem publicar nem consumir eventos.
```

- [ ] **Step 5: Escreva `app/database.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
# `async_sessionmaker`, a fábrica tipada da 2.x — não o
# `sessionmaker(..., class_=AsyncSession)` da 1.4 que os cinco serviços
# anteriores carregavam e que a fase 2A converteu.
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 6: Monte o Alembic**

Copie a estrutura de um serviço que já a tem — o `notification-service` é o mais próximo em tamanho:

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp notification-service/alembic.ini chatbot-service/alembic.ini
mkdir -p chatbot-service/alembic/versions
cp notification-service/alembic/script.py.mako chatbot-service/alembic/
cp notification-service/alembic/env.py chatbot-service/alembic/env.py
touch chatbot-service/alembic/versions/.gitkeep
```

Em `chatbot-service/alembic/env.py`, troque o bloco de imports de models por:

```python
# Importa os models para que registrem em Base.metadata antes do autogenerate.
from app.models import suporte as suporte_models  # noqa: F401
```

**Confirme que `compare_server_default=True` sobreviveu à cópia:**

Run: `cd back-end/chatbot-service && grep -n compare_server_default alembic/env.py`

Expected: uma linha. **Constraint 13** — sem ela, todo sync-check deste serviço nasce vazio de significado, que é exatamente a armadilha que a fase 1 pagou para descobrir.

- [ ] **Step 7: Declare no `.env.example`**

```
# Banco próprio do serviço (fase 2, módulo support).
DATABASE_URL=postgresql+asyncpg://edu:edu@localhost:5433/chatbot_db

# Opcional — já tem default em app/config.py.
# DATABASE_URL_TEST=postgresql+asyncpg://edu:edu@localhost:5433/chatbot_test
```

`DATABASE_URL` entra na seção de **obrigatórias** (sem default em `app/config.py`), junto do `JWT_SECRET`.

> `make services-env` copia `.env.example` para `.env` num clone limpo, e **nunca sobrescreve** um `.env` existente. O seu `chatbot-service/.env` já existe — acrescente `DATABASE_URL` a ele à mão, senão a suíte estoura no import com `ValidationError`, não numa assertion, e o sintoma fica confuso.

- [ ] **Step 8: Dê ao conftest as fixtures de banco**

Em `back-end/chatbot-service/tests/conftest.py`, **atualize o docstring do módulo** (constraint 16 — ele hoje diz "Este serviço não tem banco (não usa a Recipe C do plano de migração)") e acrescente as fixtures, copiando a forma de `notification-service/tests/conftest.py`:

```python
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from edu_common.security import create_access_token
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    from app.models import suporte as suporte_models  # noqa: F401

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
```

e o `client` existente passa a sobrescrever `get_db`:

```python
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
```

> As três suítes que já existem (`test_chat_routes`, `test_diagnostico_client`, `test_rag`) usam `client` e **não** tocam banco. Elas passam a arrastar a fixture de banco por dependência — o que significa que a suíte inteira do chatbot passa a exigir um Postgres alcançável. Isso é o preço de o serviço ganhar persistência; registre no relatório, porque quem rodar `uv run pytest` num clone sem stack vai ver a mudança.

- [ ] **Step 9: Confira o Dockerfile**

Run: `cd back-end/chatbot-service && cat Dockerfile`

Se ele copia arquivos por lista (`COPY app/ ./app/` e nada mais), `alembic/` e `alembic.ini` **não entram na imagem** e `make services-migrate` falha com "No 'script_location' key found". Compare com o `Dockerfile` do `notification-service`, que já carrega Alembic, e acrescente as linhas que faltarem.

- [ ] **Step 10: Rode e confirme que passa**

```bash
cd /home/elias/programming/fiap/estuda_app && make stack-up
cd back-end/chatbot-service && uv run pytest -q
```

Expected: PASS. O `test_database.py` passa; as três suítes antigas continuam passando.

> `db_session` conecta em `settings.database_url_test`. Rodando no host, isso precisa apontar para a porta publicada do Postgres (`localhost:5433` no default acima) — não para `postgres:5432`, que só resolve dentro da rede do compose.

- [ ] **Step 11: Commit**

```bash
cd back-end/chatbot-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/chatbot-service/
git diff --staged
git commit -m "feat(chatbot): add the persistence layer

engine, session factory, declarative Base and an Alembic tree, plus the
database fixtures the test suite needs. async_sessionmaker from the start:
this service is not going to be born carrying the 1.4 form the other five
just shed.

compare_server_default is verified present in env.py — without it every
sync check on this service would be empty of meaning, which is the trap
phase 1 paid to learn.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task D3: `support_messages`

**Files:**
- Create: `back-end/chatbot-service/app/models/__init__.py`
- Create: `back-end/chatbot-service/app/models/suporte.py`
- Create: `back-end/chatbot-service/app/ids.py`
- Create: `back-end/chatbot-service/alembic/versions/<hash>_baseline_schema.py`
- Test: `back-end/chatbot-service/tests/test_support_model.py`

**Interfaces:**
- Produces: `SupportMessage` (`support_messages`) — `id UUID PK`, `user_id UUID NOT NULL index`, `sender String(16) NOT NULL DEFAULT 'user'`, `body String(2000) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `CheckConstraint("sender IN ('user','support')")`.
- `app.ids.new_uuid() -> uuid.UUID` (UUIDv7), igual ao dos outros serviços.

- [ ] **Step 1: Escreva o teste que falha**

```python
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.suporte import SupportMessage


async def test_a_message_is_stored_with_its_owner(db_session):
    user_id = uuid.uuid4()
    mensagem = SupportMessage(user_id=user_id, sender="user", body="Não consigo pagar")
    db_session.add(mensagem)
    await db_session.commit()
    await db_session.refresh(mensagem)

    assert isinstance(mensagem.id, uuid.UUID)
    assert mensagem.user_id == user_id
    assert mensagem.created_at is not None


async def test_sender_defaults_to_user(db_session):
    mensagem = SupportMessage(user_id=uuid.uuid4(), body="olá")
    db_session.add(mensagem)
    await db_session.commit()
    await db_session.refresh(mensagem)
    assert mensagem.sender == "user"


async def test_an_unknown_sender_is_rejected_by_the_database(db_session):
    """O CHECK vive no banco, não só no schema Pydantic: a conversa é lida
    por duas partes e um `sender` fora do par quebraria a renderização."""
    mensagem = SupportMessage(user_id=uuid.uuid4(), sender="robo", body="olá")
    db_session.add(mensagem)
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 2: Rode e confirme que falha**

Expected: `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Escreva `app/ids.py` e o model**

`back-end/chatbot-service/app/ids.py` — copie de `commerce-service/app/ids.py` (criado no bloco B) ou de `legacy/app/core/ids.py`:

```python
import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """UUIDv7 (ordenado no tempo) como `uuid.UUID` da stdlib.

    Preserva a localidade de inserção no índice B-tree do Postgres; UUIDv4
    aleatório fragmenta o índice a cada insert.
    """
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
```

Acrescente `"uuid-utils>=0.10.0"` a `[project].dependencies` e rode `uv sync`.

`back-end/chatbot-service/app/models/suporte.py`:

```python
from sqlalchemy import CheckConstraint, Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.ids import new_uuid


class SupportMessage(Base):
    """Uma mensagem da conversa de suporte.

    Em inglês — tabela e colunas — porque é um agregado com cliente: o app
    Flutter lê `/support` na fase 4.

    `user_id` é FK LÓGICA para o `auth-users-service`: banco diferente,
    nenhuma FK física possível. A posse é garantida em toda query, sem
    exceção — é a única defesa que existe aqui.

    O CHECK de `sender` vive no banco, e não só no schema Pydantic, porque a
    conversa é renderizada como dois lados; um valor fora do par quebraria a
    tela e não haveria nada para pegá-lo se a escrita viesse por fora do ORM.
    """

    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint("sender IN ('user', 'support')", name="ck_support_messages_sender"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # `default=` cobre insert pelo ORM; `server_default` cobre insert que
    # passa por fora dele — constraint 15.
    sender = Column(String(16), nullable=False, default="user", server_default=text("'user'"))
    # 2000 no model E no schema (regra 4 do CLAUDE.md). O legacy declara os
    # dois; declarar só um deixa o limite a cargo de quem chamar.
    body = Column(String(2000), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

`back-end/chatbot-service/app/models/__init__.py` fica vazio.

- [ ] **Step 4: Gere a baseline do Alembic**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
docker compose up -d chatbot-service && docker compose restart chatbot-service
docker compose exec -T chatbot-service uv run alembic revision --autogenerate -m "baseline schema"
```

Revise a revision gerada: `create_table("support_messages")` com as cinco colunas, o `CheckConstraint` nomeado, o índice em `user_id`, e os dois `server_default`. **O autogenerate às vezes perde `CheckConstraint` nomeado** — se perdeu, acrescente à mão.

- [ ] **Step 5: Aplique e confirme o sync-check**

```bash
cd back-end
docker compose exec -T chatbot-service uv run alembic upgrade head
docker compose exec -T postgres psql -U edu -d chatbot_db -c "\d support_messages"
docker compose exec -T chatbot-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: a tabela existe com o CHECK e o índice; o sync-check gera revision **vazia**. Apague o arquivo gerado.

- [ ] **Step 6: Rode a suíte**

Run: `cd back-end/chatbot-service && uv run pytest -q`

Expected: PASS.

- [ ] **Step 7: Prove o CHECK (constraint 11)**

Remova o `CheckConstraint` do `__table_args__`, recrie a tabela de teste (a fixture `test_engine` faz `drop_all`/`create_all`), rode `test_an_unknown_sender_is_rejected_by_the_database`, confirme `DID NOT RAISE`, reaplique.

- [ ] **Step 8: Commit**

```bash
cd back-end/chatbot-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/chatbot-service/
git diff --staged
git commit -m "feat(chatbot): add the support_messages table

English table and columns: support gains a client in phase 4. user_id is a
logical FK to auth-users-service — different database, no physical FK
possible — so ownership is enforced in every query, which is the only
defence there is. The sender CHECK lives in the database because the
conversation renders as two sides.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task D4: `GET /support` e `POST /support`

**Files:**
- Modify: `back-end/chatbot-service/app/schemas.py`
- Create: `back-end/chatbot-service/app/services/suporte.py`
- Create: `back-end/chatbot-service/app/routers/__init__.py`, `app/routers/suporte.py`
- Modify: `back-end/chatbot-service/app/main.py`
- Create: `back-end/chatbot-service/tests/test_support_parity.py` (portado)

**Interfaces:**
- Produces:
  - `SupportMessageIn{body: str, min_length=1, max_length=2000}` com `str_strip_whitespace=True`
  - `SupportMessageOut{id, sender, body, created_at}`
  - `services.listar_mensagens(db, user_id) -> list[SupportMessage]`
  - `services.enviar_mensagem(db, user_id, body) -> list[SupportMessage]`
  - `GET /support` → `list[SupportMessageOut]` (array puro, ordem `created_at`)
  - `POST /support` → **201**, `list[SupportMessageOut]` (a conversa **completa**, não só a mensagem nova)

- [ ] **Step 1: Porte o teste do legacy (Red)**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp legacy/tests/modules/support/test_routes.py chatbot-service/tests/test_support_parity.py
```

Adaptações:
1. Toda URL perde o `/api`: `/api/support` → `/support`.
2. As fixtures `created_user`/`auth_headers` de `legacy/tests/modules/support/conftest.py` não existem aqui — o `auth_headers` da task D2 as substitui.
3. `assert r.status_code == 401` em `TestAuthRequired` → **403**, com o comentário apontando para a divergência registrada na task B0 do bloco B:
   ```python
   # 403, não 401: `edu-common` responde 403 para header ausente e 401 para
   # token inválido/expirado; o legacy responde 401 nos dois. Divergência
   # registrada na task B0 do plano do bloco B.
   ```

Acrescente o teste de posse, que o legacy não tem porque lá o `user` vem do banco e aqui vem do JWT:

```python
def _headers_de_outro_aluno() -> dict[str, str]:
    """Um segundo aluno, com `sub` diferente do da fixture `student_identity`.

    `user_id` é FK lógica para outro banco: nada no schema impede ler a
    conversa alheia, só a cláusula `where` do serviço. Este teste é o que
    trava essa cláusula.
    """
    token = create_access_token(
        sub=str(uuid.uuid4()),
        role="student",
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_a_student_never_sees_another_students_conversation(client, student_identity):
    await client.post(
        "/support", json={"body": "minha mensagem"}, headers=student_identity.headers
    )

    resposta = await client.get("/support", headers=_headers_de_outro_aluno())
    assert resposta.status_code == 200
    assert resposta.json() == []
```

Imports no topo do arquivo portado:

```python
import uuid

from edu_common.security import create_access_token

from app.config import settings
```

E o teste do teto, que a regra 4 exige:

```python
async def test_a_body_over_the_cap_returns_422(client, auth_headers):
    resposta = await client.post(
        "/support", json={"body": "x" * 2001}, headers=auth_headers
    )
    assert resposta.status_code == 422
```

> **Constraint 12:** `2001` literal, não `SupportMessage.body.type.length + 1`.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/chatbot-service && uv run pytest tests/test_support_parity.py -v`

Expected: 404 em todas as rotas.

- [ ] **Step 3: Acrescente os schemas**

Em `back-end/chatbot-service/app/schemas.py` (o arquivo único que o serviço já usa):

```python
class SupportMessageIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # `min_length=1` DEPOIS do strip: uma mensagem só de espaços vira "" e é
    # rejeitada com 422, em vez de virar um balão vazio na conversa.
    # `max_length` bate com a coluna (regra 4 do CLAUDE.md).
    body: str = Field(min_length=1, max_length=2000)


class SupportMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: str
    body: str
    created_at: datetime
```

- [ ] **Step 4: Escreva o serviço**

`back-end/chatbot-service/app/services/suporte.py`:

```python
import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suporte import SupportMessage


async def listar_mensagens(db: AsyncSession, user_id: uuid.UUID) -> list[SupportMessage]:
    """A conversa do aluno, em ordem cronológica.

    O filtro por `user_id` é a única defesa de posse que existe: `user_id` é
    FK lógica para outro banco, então nada no schema impede ler a conversa
    alheia — só esta cláusula.
    """
    stmt = (
        select(SupportMessage)
        .where(SupportMessage.user_id == user_id)
        .order_by(SupportMessage.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def enviar_mensagem(
    db: AsyncSession, user_id: uuid.UUID, body: str
) -> list[SupportMessage]:
    """Grava a mensagem e devolve a conversa COMPLETA.

    Devolver a lista inteira, e não só a mensagem criada, é o contrato: o app
    substitui a conversa pela resposta do POST em vez de acrescentar
    localmente, então uma resposta parcial esvaziaria a tela.
    """
    mensagem = SupportMessage(user_id=user_id, sender="user", body=body)
    db.add(mensagem)
    await db.commit()
    logger.info("support: mensagem enviada id={} user={}", mensagem.id, user_id)
    return await listar_mensagens(db, user_id)
```

> **Sem paginação, de propósito.** O legacy não pagina `/support`, e réplica exata é o alvo (constraint 18); a conversa é por aluno e cresce devagar. Isso é uma exceção consciente à regra 4 do `CLAUDE.md` — registre-a no relatório da task, para a revisão não a confundir com esquecimento. Se um dia ela crescer, o lugar de paginar é aqui, não no router.

- [ ] **Step 5: Escreva o router**

`back-end/chatbot-service/app/routers/suporte.py`:

```python
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas import SupportMessageIn, SupportMessageOut
from app.services import suporte as services

router = APIRouter(prefix="/support", tags=["support"])


@router.get("", response_model=list[SupportMessageOut])
async def listar_mensagens(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SupportMessageOut]:
    """ARRAY PURO, sem envelope — como `/orders` e `/payment-methods`, e ao
    contrário de `/products` e `/cart`. É o contrato, medido contra o legacy."""
    mensagens = await services.listar_mensagens(db, uuid.UUID(user_id))
    return [SupportMessageOut.model_validate(m) for m in mensagens]


@router.post("", response_model=list[SupportMessageOut], status_code=status.HTTP_201_CREATED)
async def enviar_mensagem(
    payload: SupportMessageIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SupportMessageOut]:
    """201 com a conversa COMPLETA, não só a mensagem criada.

    Os dois detalhes são contrato: o app troca a conversa inteira pela
    resposta, então devolver só a nova mensagem esvaziaria a tela.
    """
    mensagens = await services.enviar_mensagem(db, uuid.UUID(user_id), payload.body)
    return [SupportMessageOut.model_validate(m) for m in mensagens]
```

`app/routers/__init__.py` fica vazio.

> `get_current_user_id` é o nome canônico desde a task 19 do bloco A. Se `app/dependencies.py` ainda exportar `get_current_student`, aquela task não foi executada — pare e execute-a antes de seguir, senão este bloco reintroduz a divergência que ela removeu.

- [ ] **Step 6: Registre no `main.py`**

```python
from app.routers import suporte

app = FastAPI(title="Chatbot Service", lifespan=lifespan)
app.include_router(suporte.router)
```

- [ ] **Step 7: Rode e confirme que passa**

Run: `cd back-end/chatbot-service && uv run pytest -q`

Expected: PASS, incluindo `test_support_parity.py` inteiro.

- [ ] **Step 8: Prove os dois detalhes de contrato (constraint 11)**

1. Troque `status_code=status.HTTP_201_CREATED` por 200, rode `test_send_returns_updated_list`, confirme FAIL, reaplique.
2. Troque o retorno do POST por `[SupportMessageOut.model_validate(mensagem)]` (só a nova), rode `test_messages_accumulate_in_order`, confirme FAIL, reaplique.

Os dois são divergências que a fase 1 mediu. Se algum deles voltar ao "óbvio" sem quebrar teste, o arquivo portado não está fazendo seu trabalho.

- [ ] **Step 9: Commit**

```bash
cd back-end/chatbot-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/chatbot-service/
git diff --staged
git commit -m "feat(chatbot): port the support conversation

GET returns a bare array and POST answers 201 with the WHOLE conversation,
not just the created message — the app replaces the thread with the
response, so a partial answer would empty the screen. Both are contract,
measured against the legacy.

Ownership is the user_id filter and nothing else: user_id is a logical FK
into another service's database.

/support is deliberately unpaginated, matching the legacy — a conscious
exception to CLAUDE.md rule 4, recorded in the task report.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task D5: portão do bloco D

**Files:** nenhum. Produz um relatório.

- [ ] **Step 1: A 17ª suíte**

Run: `cd back-end/chatbot-service && uv run pytest tests/test_support_parity.py -q`

Compare a contagem com o legacy:

```bash
cd back-end/legacy && uv run pytest --collect-only -q tests/modules/support/test_routes.py 2>/dev/null | tail -3
```

Os números têm que bater, mais os dois testes que este bloco acrescentou (posse e teto de corpo). Registre.

- [ ] **Step 2: Frota verde**

Run: `make services-test && make services-lint`

Expected: PASS nos oito alvos. O chatbot agora exige Postgres — se `make services-test` falhar num ambiente sem stack, é esperado; documente o pré-requisito.

- [ ] **Step 3: Sync-check dos SEIS bancos**

Agora são seis, não cinco:

```bash
cd back-end && grep -l compare_server_default */alembic/env.py | wc -l   # tem que dar 6
for s in auth-users-service learning-service commerce-service notification-service analytics-service chatbot-service; do
  echo "→ $s"
  docker compose exec -T $s uv run alembic upgrade head
  docker compose exec -T $s uv run alembic revision --autogenerate -m "sync check $s"
done
```

Cada revision gerada tem que estar **vazia**. Apague as seis.

> **Constraint 13:** se o `wc -l` der 5, o `env.py` copiado na task D2 perdeu o `compare_server_default` e o sync-check deste serviço não vale nada.

- [ ] **Step 4: Prove que um clone limpo funciona**

Esta é a verificação que o bloco D justifica sozinho — ele acrescentou um eixo de infraestrutura, e o caminho do clone limpo é o que quebra em silêncio.

```bash
cd /home/elias/programming/fiap/estuda_app
make stack-down
cd back-end && docker compose down -v          # APAGA os volumes — só faça isto se não houver dado que importe
cd .. && make stack-up
make services-dbs
make services-migrate
cd back-end && docker compose exec -T postgres psql -U edu -d postgres -c "\l" | grep chatbot
docker compose exec -T postgres psql -U edu -d chatbot_db -c "\dt"
```

Expected: `chatbot_db` e `chatbot_test` existem; `support_messages` e `alembic_version` estão em `chatbot_db`.

> **`docker compose down -v` apaga todos os volumes**, inclusive o do legacy que serve o app na 8001. Confirme com quem for dono do ambiente antes de rodar, e se houver dado que importe, faça `pg_dump` primeiro. Se não puder apagar, pule este step e registre que a verificação do clone limpo ficou pendente — é uma lacuna real, não um detalhe.

- [ ] **Step 5: Prove a rota pelo gateway**

`"support": "chatbot"` já está no `SERVICE_MAP` do gateway. Com o stack de pé e um bearer de aluno:

```bash
TOKEN="<bearer de aluno>"
curl -s -X POST "localhost:8100/api/support" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"body":"teste pelo gateway"}' -w "\n%{http_code}\n"
curl -s "localhost:8100/api/support" -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expected: 201 no POST com a lista completa; array puro no GET.

E lado a lado com o legacy:

```bash
curl -s "localhost:8001/api/support" -H "Authorization: Bearer <token legacy>" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(sorted(d[0].keys()) if d else 'vazio')"
curl -s "localhost:8100/api/support" -H "Authorization: Bearer $TOKEN" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(sorted(d[0].keys()) if d else 'vazio')"
```

As listas de chaves têm que ser **idênticas**.

- [ ] **Step 6: Confira os três comentários que viraram mentira (constraint 16)**

```bash
cd back-end
grep -n "não tem banco\|sem banco\|DATABASE_URL: \"\"" chatbot-service/app/config.py \
  chatbot-service/tests/conftest.py docker-compose.yml
```

Expected: **nenhuma ocorrência** que ainda afirme que o serviço não tem banco. Se alguma sobreviveu, corrija antes de fechar o bloco. Um comentário que descreve a versão anterior é pior do que nenhum, e a fase 1 pagou por isso seis vezes.

- [ ] **Step 7: Relate**

Relatório com: contagem de testes portados vs. legacy, resultado dos seis sync-checks, o log do clone limpo (ou o registro de que ficou pendente e por quê), o diff de chaves contra o legacy, e a exceção declarada de paginação em `/support`.

Nada a commitar.

---

## Fechamento da fase 2

Com A, B, C e D concluídos, o critério binário do spec pode ser avaliado: **as 17 suítes do legacy que entram no critério passam contra os serviços novos.** Consolide, no relatório final, as quatro listas de asserções adaptadas (as de B0 e as de cada bloco) — é o inventário de onde o stack novo ainda não é o legacy, e é a entrada obrigatória do plano da fase 4.

Os três carve-outs declarados, todos para a fase 3, têm que aparecer nomeados: `modules/products/test_image_upload.py`, `modules/orders/test_lifecycle.py`, `modules/orders/test_status_pipeline.py` — e a metade de escrita de `core/test_storage.py`.
