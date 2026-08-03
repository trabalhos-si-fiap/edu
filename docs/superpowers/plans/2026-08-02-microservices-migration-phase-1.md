# Migração para microserviços — Fase 1 (Fundação) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trazer os 7 serviços de `/home/elias/Downloads/edu-project (2)` para `back-end/`, normalizados ao padrão do projeto (uv, ruff, pytest, Alembic), com testes e correções de segurança, rodando ao lado do monolito legacy que continua servindo o Flutter intacto.

**Architecture:** O monolito atual desce para `back-end/legacy/` e continua sendo o backend de produção do app. Ao lado dele nascem `back-end/packages/edu-common` (JWT e eventos RabbitMQ) e os 7 serviços, cada um um projeto uv independente com seu próprio Alembic e sua própria suíte. Um único `docker-compose.yml` em `back-end/` sobe a infra compartilhada (Postgres, Redis, RabbitMQ, MinIO) e os dois stacks lado a lado.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic, uv, ruff, pytest + pytest-asyncio + httpx, aio-pika, python-jose, bcrypt, loguru, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-02-microservices-migration-design.md`

---

## Global Constraints

Valem para toda task deste plano.

- **Python `>=3.12`** em todo `pyproject.toml`.
- **O legacy não pode quebrar.** `back-end/legacy/` continua servindo o Flutter na porta host que já usa hoje — `API_PORT_EXTERNAL` do `back-end/.env`, **8001** nesta máquina — durante toda a fase 1. Nada no plano altera essa variável.
- **Faixa de portas do stack novo: 81xx.** Gateway em **8100**, serviços em **8101-8106**. A faixa 80xx está ocupada nesta máquina (8000 por outro projeto, 8001 pelo legacy) — nenhum serviço novo pode publicar em 80xx.
- **`back-end/.env` já existe e está em uso.** Nunca sobrescrever: as variáveis novas são *acrescentadas* ao arquivo existente. O plano só cria/atualiza o `.env.example`.
- **ruff** com a mesma config do legacy: `target-version = "py312"`, `line-length = 100`, `select = ["E","F","I","N","UP","B","A","C4","SIM","RUF","ASYNC","S"]`, `ignore = ["S101"]`, e `per-file-ignores` de `"tests/**" = ["S","ASYNC"]` e `"alembic/**" = ["S","E501"]`.
- **pytest** com `asyncio_mode = "auto"`, `addopts = "-ra --strict-markers"`, e a marca `slow` registrada para os testes que carregam modelo de embeddings real.
- **Logging com loguru.** Nenhum `print()` sobrevive à importação. Nenhum segredo (token, código OTP, senha, JWT) vai para log.
- **Autorização explícita** em todo endpoint: `Depends(get_current_user)` ou equivalente, e filtro de ownership em toda query de dado de usuário.
- **Paginação obrigatória** em todo endpoint de listagem, com `limit` default e teto.
- **Schemas Pydantic com campos explícitos.** Nenhum endpoint devolve objeto ORM cru.
- **Contrato público em inglês**, código interno dos serviços importados segue em português.
- **Nenhum segredo commitado.** `.env` nunca; só `.env.example`.
- **Conventional Commits**, uma unidade lógica por commit, `git diff --staged` antes de cada um.
- **Nada de `datetime.utcnow()`** — sempre `datetime.now(UTC)`.
- **Todo teste de regressão ou de segurança precisa ser provado não-vazio.** Antes de fechar a task: quebre de propósito o comportamento que o teste protege, veja o teste falhar, desfaça. Registre esse antes/depois no relatório. Três tasks seguidas entregaram testes verdes que não provavam nada — um `assert "code" not in body` contra uma resposta em português, um dublê que ignorava normalização, e um teste de vazamento consultando um id inexistente. Todos passariam contra o código quebrado que diziam proteger. Um teste que não pode falhar é pior que teste nenhum: ele compra confiança que não existe.
- **Nunca use a constante da própria implementação como entrada do teste que verifica essa constante.** `decidir_acao(LIMIAR_AVANCAR)` continua verdadeiro se alguém mudar o limiar; `decidir_acao(0.70)` não. Limiares e fronteiras vão como literais no teste.
- **Cada serviço tem seu `.env.example`.** As settings com campo obrigatório sem default fazem `uv run pytest` estourar no import num clone limpo — sem o `.env.example` ninguém descobre quais variáveis faltam. Listar toda variável obrigatória, com valor de exemplo e nunca com valor real.
- **Cada task de serviço reescreve o `Dockerfile` do serviço** pela Recipe E, e prova que `docker build` passa. O arquivo que vem no zip referencia o `requirements.txt` que a própria importação apaga — deixá-lo para a task 15 mantém a árvore com Dockerfiles quebrados por dez tasks.
- **`SettingsConfigDict`, nunca `class Config:`.** Os serviços importados usam a forma depreciada do Pydantic v1, que emite `PydanticDeprecatedSince20` e sai no v3. O monolito deste projeto já usa `SettingsConfigDict` (`back-end/legacy/app/core/config.py:5`) — todo serviço importado migra para ela.
- **401 vs 403 é contrato, não detalhe.** Header `Authorization` ausente → **403**. Token inválido, expirado ou do `type` errado → **401**. O Flutter dispara o refresh do par de tokens *só* em 401 (`front-end-flutter/lib/core/network/auth_http_client.dart:43`), então 401 tem que significar exatamente "tenta renovar" — devolver 401 para requisição sem sessão nenhuma faria o app gastar um refresh à toa. O `HTTPBearer` do FastAPI 0.141 devolve 401 para header ausente, por isso `edu-common` usa `HTTPBearer(auto_error=False)` e levanta o 403 explicitamente. Isso é deliberado; não "corrigir".

---

## Decisões que este plano trava

**Compose único, infra compartilhada.** Os dois compose declaram `container_name: edu-postgres` — não dá para rodar os dois arquivos em paralelo. A fase 1 funde tudo em `back-end/docker-compose.yml`: uma instância de Postgres com vários bancos (`edu` do legacy, `auth_db`, `learning_db`, `commerce_db`, `notification_db`, `analytics_db`), um Redis, um RabbitMQ, um MinIO, mais `api`/`worker` do legacy e o gateway com os 6 serviços.

**Sem uv workspace.** `auth-users-service` fixa `bcrypt==3.2.2` (limitação do passlib 1.7.4) e o legacy usa `bcrypt>=4.2.0`; num workspace o lock é único e os dois não coexistem. Cada serviço é um projeto uv independente, e `edu-common` entra como path dependency editável via `[tool.uv.sources]`. Além disso a task 2 **remove o passlib**, usando `bcrypt` direto como o legacy já faz — o formato de hash `$2b$` é o mesmo, então hashes existentes continuam válidos.

**`edu-common` sintetiza o melhor dos dois JWTs.** O contrato de claims é o dos serviços novos (inclui `role`, que eles usam para autorização); a implementação é a do legacy, que é mais dura: `datetime.now(UTC)`, `jti`, `iat`, `bcrypt.checkpw` em tempo constante e `DUMMY_PASSWORD_HASH` contra enumeração por timing.

---

## File Structure

```
back-end/
  docker-compose.yml               # Task 15 — infra compartilhada + legacy + 7 serviços
  .env.example                     # Task 15 — união das variáveis dos dois stacks
  postgres/initdb.d/               # Task 15 — criação idempotente dos bancos por serviço
  Makefile alvos                   # Task 15 — em /Makefile na raiz

  packages/edu-common/
    pyproject.toml                 # Task 2
    src/edu_common/__init__.py     # Task 2
    src/edu_common/security.py     # Task 2 — hash de senha + encode/decode de JWT
    src/edu_common/deps.py         # Task 3 — dependências FastAPI de auth
    src/edu_common/events.py       # Task 4 — publisher/consumer RabbitMQ
    tests/test_security.py         # Task 2
    tests/test_deps.py             # Task 3
    tests/test_events.py           # Task 4

  api-gateway/                     # Task 5
  auth-users-service/              # Tasks 6 e 7
  learning-service/                # Tasks 8 e 9
  commerce-service/                # Tasks 10 e 11
  chatbot-service/                 # Task 12
  notification-service/            # Task 13
  analytics-service/               # Task 14

  legacy/                          # Task 1 — monolito atual, intacto
```

Cada serviço tem o mesmo formato interno:

```
<service>/
  pyproject.toml        alembic.ini        Dockerfile
  app/                  (como veio, com as correções da task)
  alembic/env.py        alembic/versions/  tests/conftest.py  tests/...
```

---

## Shared Recipes

Conteúdo usado por várias tasks. Cada task diz exatamente quais parâmetros usar.

### Recipe A — `pyproject.toml` de um serviço

Substitua `<service>` pelo nome da pasta e `<deps>` pela lista de dependências que a task especificar.

```toml
[project]
name = "<service>"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "edu-common",
    <deps>
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
]

[tool.uv.sources]
edu-common = { path = "../packages/edu-common", editable = true }

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "RUF", "ASYNC", "S"]
ignore = ["S101"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S", "ASYNC"]
"alembic/**" = ["S", "E501"]

# `Depends(...)` como default de argumento é o idioma do FastAPI, não o
# bug que o B008 procura. Declarar aqui evita espalhar `# noqa: B008`
# por todo router dos sete serviços. `requer_papel` entra na lista pelo
# mesmo motivo: `Depends(requer_papel("admin"))` é chamada inline por
# design, e sem isso todo endpoint com papel exigido carregaria um noqa.
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends",
    "fastapi.Security",
    "app.dependencies.requer_papel",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
# As duas linhas de loop_scope andam juntas. Só a de fixture não basta: o
# default de teste é "function", e um engine asyncpg criado no loop da sessão
# estoura no segundo teste que tocar o banco — falha que só aparece quando o
# serviço ganha o seu segundo teste de banco, não no primeiro.
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
    "slow: tests that load a real embeddings model (opt-in)",
]

[tool.coverage.run]
source = ["app"]
omit = ["alembic/*"]
```

Serviços sem banco (api-gateway, chatbot-service) omitem a seção `per-file-ignores` de `alembic/**` e o `omit`.

### Recipe B — `alembic/env.py` de um serviço

Substitua `<model imports>` pelos imports que a task especificar.

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.database import Base

# Importa os models para que registrem em Base.metadata antes do autogenerate.
<model imports>

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Recipe C — `tests/conftest.py` de um serviço com banco

Substitua `<model imports>` pelos mesmos imports da Recipe B.

```python
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
<model imports>

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
```

**Serviços que publicam eventos precisam de mais uma fixture.** O `ASGITransport`
não roda o lifespan do app, então o `init_publisher()` do startup nunca dispara e
qualquer rota que publique evento estoura `RuntimeError: EventPublisher not
connected` — depois de já ter gravado no banco. Sem isso, nenhum teste consegue
exercitar as rotas de escrita. Acrescentar ao `conftest.py`:

```python
@pytest.fixture(autouse=True)
def fake_event_publisher(monkeypatch) -> list[tuple[str, dict]]:
    """Captura eventos em memória em vez de exigir um RabbitMQ de verdade.

    Devolve a lista de `(routing_key, payload)` publicados, para que um teste
    possa afirmar que a rota publicou o evento certo.
    """
    published: list[tuple[str, dict]] = []

    async def _capture(routing_key: str, payload: dict) -> None:
        published.append((routing_key, payload))

    monkeypatch.setattr("app.events.publisher.publish_event", _capture)
    return published
```

O alvo do `monkeypatch` precisa ser o nome **onde a rota importa** `publish_event`,
não onde ele é definido. Se o router fez `from app.events.publisher import
publish_event`, o alvo é `app.routers.<módulo>.publish_event`. Confirmar com
`grep -rn "publish_event" app/` antes de escrever a fixture.

### Recipe E — `Dockerfile` de um serviço

Os serviços vieram com Dockerfile de `pip install -r requirements.txt`, e o
`requirements.txt` é apagado na importação — o arquivo original fica quebrado no
primeiro `docker build`. **Cada task de serviço reescreve o seu**, substituindo
`<service>` pelo nome da pasta:

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# O container reproduz a MESMA disposição relativa do repositório
# (/app/<service> ao lado de /app/packages/edu-common), para que o path
# `../packages/edu-common` do [tool.uv.sources] valha no host e aqui dentro
# sem precisar de source condicional.
WORKDIR /app/<service>

COPY packages/edu-common /app/packages/edu-common
COPY <service>/pyproject.toml <service>/uv.lock* ./
RUN uv sync --no-install-project

COPY <service>/ ./

CMD ["uv", "run", "granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "app.main:app"]
```

O `api-gateway` omite a linha do `edu-common`: ele é proxy burro e não valida
JWT. A porta 8000 é a **interna** do container e não muda — o mapeamento para a
porta do host (8100 no gateway, 8101-8106 nos serviços) é do compose, na task 15.

O contexto de build é `back-end/`, com `dockerfile: <service>/Dockerfile`.

Junto vai um `<service>/Dockerfile.dockerignore`. **Todo padrão precisa do prefixo
`**/`**: os padrões são ancorados na raiz do contexto (`back-end/`), então `.venv/`
sozinho casaria só com `back-end/.venv` — nunca com `back-end/<service>/.venv`, que
é justamente o que `COPY <service>/ ./` arrasta para dentro da imagem, junto com o
`.env` do serviço.

```
**/.env
**/.env.*
**/.venv
**/__pycache__
**/.pytest_cache
**/.ruff_cache
**/.git
```

Provar que constrói **e** que a imagem está limpa antes de fechar a task:

```bash
cd back-end
docker build -f <service>/Dockerfile -t edu-<service>-test .
docker run --rm edu-<service>-test uv run python -c "import edu_common.security; print('ok')"
# A imagem não pode conter .env nem caches do host:
docker run --rm edu-<service>-test sh -c \
  'find /app -maxdepth 3 \( -name ".env" -o -name "__pycache__" -o -name ".pytest_cache" -o -name ".ruff_cache" \) | head'
# E o .venv precisa ser o do container, não o do host:
docker run --rm edu-<service>-test cat /app/<service>/.venv/pyvenv.cfg
```

Expected: o `find` sem nenhuma saída, e o `pyvenv.cfg` apontando para o Python do
container (`/usr/local`), não para um caminho do host.

**Não procure pela ausência de `.venv`.** O `RUN uv sync` cria um `.venv` dentro da
imagem antes do `COPY`, então "existe `.venv`" é o estado normal e esperado — um teste
que exija a ausência dele nunca passa e, pior, some com a informação real. O que
distingue vazamento de build correto é a *procedência*: o `pyvenv.cfg` do host aponta
para o interpretador do host e uma versão diferente de Python/uv.

### Recipe D — baseline do Alembic a partir dos models

1. `uv run alembic init -t async alembic` e substituir `alembic/env.py` pela Recipe B.
2. Em `alembic.ini`, apagar a linha `sqlalchemy.url = ...` (o `env.py` define pela settings).
3. Comparar `schema.sql` com os models **coluna a coluna**, não por amostragem. Precisam existir no model: todo `CREATE INDEX` (`index=True`), toda constraint (`UniqueConstraint`, `CheckConstraint`), e **todo `DEFAULT` de nível de banco** como `server_default=sa.text(...)`.

   O `DEFAULT` é o que mais escapa, porque o `default=` do SQLAlchemy é client-side: ele só vale para inserts que passam por aquele caminho do ORM. Seed em SQL puro, painel admin, ou outro serviço escrevendo na mesma tabela recebem NULL. Dois serviços já perderam seus defaults exatamente assim. Manter os dois: `default=` para o ORM e `server_default=` para todo o resto.

   No relatório, listar a comparação coluna a coluna — "nenhuma divergência" sem a lista não é verificação.
4. `uv run alembic revision --autogenerate -m "baseline schema"` contra um banco vazio.
5. `uv run alembic upgrade head`.
6. **Prova de sincronia:** `uv run alembic revision --autogenerate -m "sync check"` deve gerar migration com `upgrade()` e `downgrade()` vazios (só `pass`). Apagar esse arquivo depois de conferir. Se não vier vazia, o model diverge do schema — corrigir o model e refazer o baseline.
7. Apagar o `schema.sql` do serviço — o Alembic passa a ser a fonte da verdade. (O `scripts/init-multiple-dbs.sh` do zip original **não** é importado: a task 15 escreve um script próprio que só cria os bancos, sem aplicar schema. Não há nada a editar nele aqui.)

O banco do serviço ainda não existe no Postgres compartilhado nesta altura — a task 15 é que automatiza a criação. Criar os dois bancos à mão antes de rodar o Alembic, lendo a senha do `back-end/legacy/.env` sem ecoá-la:

```bash
PGUSER=$(sed -n 's/^POSTGRES_USER=//p' back-end/legacy/.env | tr -d '[:space:]')
for db in <service>_db <service>_test; do
  docker exec -i edu-postgres psql -U "$PGUSER" -d postgres \
    -c "SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='$db')\gexec"
done
```

O Postgres do projeto já está de pé no container `edu-postgres`, publicado em `localhost:5433`.

---

### Task 1: Descer o monolito para `back-end/legacy/`

**Files:**
- Move: todo o conteúdo de `back-end/` → `back-end/legacy/`
- Modify: `back-end/legacy/docker-compose.yml` (path do volume `../secrets`)
- Modify: `Makefile:1-40` (variável `BACK_DIR`)

**Interfaces:**
- Consumes: nada
- Produces: `back-end/legacy/` com o monolito funcional; `BACK_DIR` no Makefile apontando para `back-end/legacy`

- [ ] **Step 1: Mover tudo com `git mv`, preservando histórico**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
mkdir -p legacy
for item in $(git ls-tree --name-only HEAD .); do
  git mv "$item" legacy/
done
git status --short | head -20
```

- [ ] **Step 2: Mover também os arquivos não versionados que o stack usa**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
for f in .env .coverage; do [ -e "$f" ] && mv "$f" legacy/; done
for d in .venv .pytest_cache .ruff_cache; do [ -e "$d" ] && mv "$d" legacy/; done
ls -a legacy | head -20
```

- [ ] **Step 3: Corrigir o path do volume de secrets no compose do legacy**

O compose monta `../secrets:/app/secrets:ro`, que agora resolveria para `back-end/secrets`. Em `back-end/legacy/docker-compose.yml`, no serviço `api` e no serviço `worker`, trocar:

```yaml
      - ../secrets:/app/secrets:ro
```

por:

```yaml
      - ../../secrets:/app/secrets:ro
```

- [ ] **Step 4: Apontar `BACK_DIR` para a nova pasta**

Em `Makefile`, na definição de `BACK_DIR`, trocar o valor `back-end` por `back-end/legacy`.

```bash
grep -n "BACK_DIR" Makefile
```

- [ ] **Step 5: Provar que o legacy continua de pé**

```bash
make back-up
sleep 20
API_PORT=$(sed -n 's/^API_PORT_EXTERNAL=//p' back-end/.env | tr -d '[:space:]')
curl -sf "http://localhost:${API_PORT:-8000}/health"
make back-test
```

Expected: `{"status":"ok"}` e a suíte inteira verde (**406 passed, 0 failed, 6 deselected** — baseline medido antes da task 1, com MinIO no ar).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(backend): move modular monolith into back-end/legacy/"
```

---

### Task 2: `edu-common` — hash de senha e JWT

**Files:**
- Create: `back-end/packages/edu-common/pyproject.toml`
- Create: `back-end/packages/edu-common/src/edu_common/__init__.py`
- Create: `back-end/packages/edu-common/src/edu_common/security.py`
- Test: `back-end/packages/edu-common/tests/test_security.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `DEFAULT_BCRYPT_ROUNDS: int`, `MAX_PASSWORD_BYTES: int`
  - `hash_password(plain: str, rounds: int = DEFAULT_BCRYPT_ROUNDS) -> str` — levanta `ValueError` acima de `MAX_PASSWORD_BYTES`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `DUMMY_PASSWORD_HASH: str`
  - `create_access_token(sub: str, role: str, secret: str, algorithm: str = "HS256", expires_minutes: int = 60) -> str`
  - `create_refresh_token(sub: str, role: str, secret: str, algorithm: str = "HS256", expires_days: int = 7) -> str`
  - `decode_token(token: str, secret: str, algorithm: str = "HS256", expected_type: str | None = None) -> dict | None` — devolve `None` (nunca levanta) para assinatura inválida, expirado, malformado, segredo inutilizável, ou `type` diferente do esperado

- [ ] **Step 1: Criar o esqueleto do pacote**

```bash
mkdir -p /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common/src/edu_common
mkdir -p /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common/tests
touch /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common/src/edu_common/__init__.py
```

`back-end/packages/edu-common/pyproject.toml`:

```toml
[project]
name = "edu-common"
version = "0.1.0"
description = "Shared JWT/auth and RabbitMQ event helpers for the Edu microservices"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "python-jose[cryptography]>=3.4.0",
    "bcrypt>=4.2.0",
    "aio-pika>=9.4.2",
    "loguru>=0.7.2",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "ruff>=0.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/edu_common"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "RUF", "ASYNC", "S"]
ignore = ["S101"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 2: Escrever os testes que falham**

`back-end/packages/edu-common/tests/test_security.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from edu_common.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-not-a-real-key"


def test_hash_password_produces_bcrypt_hash():
    hashed = hash_password("Senha@123")
    assert hashed.startswith("$2b$")
    assert hashed != "Senha@123"


def test_verify_password_accepts_correct_password():
    assert verify_password("Senha@123", hash_password("Senha@123")) is True


def test_verify_password_rejects_wrong_password():
    assert verify_password("errada", hash_password("Senha@123")) is False


def test_verify_password_returns_false_on_malformed_hash():
    assert verify_password("Senha@123", "nao-e-um-hash") is False


def test_dummy_password_hash_is_usable_for_timing_defense():
    assert DUMMY_PASSWORD_HASH.startswith("$2b$")
    assert verify_password("qualquer-coisa", DUMMY_PASSWORD_HASH) is False


def test_access_token_carries_sub_role_and_type():
    token = create_access_token("user-1", "student", SECRET)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert payload["sub"] == "user-1"
    assert payload["role"] == "student"
    assert payload["type"] == "access"


def test_access_token_carries_jti_and_iat():
    payload = jwt.decode(create_access_token("user-1", "student", SECRET), SECRET, algorithms=["HS256"])
    assert payload["jti"]
    assert payload["iat"] <= int(datetime.now(UTC).timestamp())


def test_two_access_tokens_have_distinct_jti():
    a = jwt.decode(create_access_token("u", "student", SECRET), SECRET, algorithms=["HS256"])
    b = jwt.decode(create_access_token("u", "student", SECRET), SECRET, algorithms=["HS256"])
    assert a["jti"] != b["jti"]


def test_refresh_token_has_refresh_type():
    payload = jwt.decode(create_refresh_token("user-1", "admin", SECRET), SECRET, algorithms=["HS256"])
    assert payload["type"] == "refresh"
    assert payload["role"] == "admin"


def test_decode_token_returns_payload_for_valid_token():
    payload = decode_token(create_access_token("user-1", "student", SECRET), SECRET)
    assert payload is not None
    assert payload["sub"] == "user-1"


def test_decode_token_returns_none_for_wrong_secret():
    assert decode_token(create_access_token("user-1", "student", SECRET), "outro-secret") is None


def test_decode_token_returns_none_for_garbage():
    assert decode_token("nao.e.um.jwt", SECRET) is None


def test_decode_token_returns_none_for_expired_token():
    expired = jwt.encode(
        {
            "sub": "user-1",
            "role": "student",
            "type": "access",
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        SECRET,
        algorithm="HS256",
    )
    assert decode_token(expired, SECRET) is None


@pytest.mark.parametrize("minutes", [1, 60])
def test_access_token_expiry_respects_argument(minutes: int):
    token = create_access_token("u", "student", SECRET, expires_minutes=minutes)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    delta = payload["exp"] - payload["iat"]
    assert abs(delta - minutes * 60) <= 2
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common
uv sync
uv run pytest -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'edu_common.security'`.

- [ ] **Step 4: Implementar**

`back-end/packages/edu-common/src/edu_common/security.py`:

> **O código abaixo é a versão original do plano e foi superado.** A revisão da
> task 2 encontrou cinco falhas nele — `type` não verificável (refresh token
> valendo como access), `ValueError` não tratado acima de 72 bytes, custo do
> hash-isca desacoplado, `JWKError` escapando do `except`, e piso vulnerável do
> `python-jose`. A implementação que vale é a que está no arquivo, commitada em
> `757214f`. Não reescreva este arquivo a partir do bloco abaixo.

```python
"""Hash de senha e JWT compartilhados entre os serviços.

Implementação herdada do monolito (tempo constante, `jti`, timezone-aware),
com o contrato de claims dos microserviços (inclui `role`, usado para
autorização em cada serviço).
"""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

DEFAULT_ALGORITHM = "HS256"


def hash_password(plain: str, rounds: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compara em tempo constante — `bcrypt.checkpw` já garante isso."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Hash malformado conta como divergência, não como erro.
        return False


# Hash de uma senha aleatória, gerado uma vez no import. O login verifica
# contra ele quando o e-mail não existe, para que o tempo de resposta de um
# e-mail inexistente iguale o de uma senha errada (anti-enumeração).
DUMMY_PASSWORD_HASH: str = hash_password("dummy-password-for-timing-defense")


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(payload: dict, secret: str, algorithm: str) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def _base_claims(sub: str, role: str, token_type: str, expires_at: datetime) -> dict:
    now = _now()
    return {
        "sub": sub,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }


def create_access_token(
    sub: str,
    role: str,
    secret: str,
    algorithm: str = DEFAULT_ALGORITHM,
    expires_minutes: int = 60,
) -> str:
    expires_at = _now() + timedelta(minutes=expires_minutes)
    return _encode(_base_claims(sub, role, "access", expires_at), secret, algorithm)


def create_refresh_token(
    sub: str,
    role: str,
    secret: str,
    algorithm: str = DEFAULT_ALGORITHM,
    expires_days: int = 7,
) -> str:
    expires_at = _now() + timedelta(days=expires_days)
    return _encode(_base_claims(sub, role, "refresh", expires_at), secret, algorithm)


def decode_token(token: str, secret: str, algorithm: str = DEFAULT_ALGORITHM) -> dict | None:
    """Devolve o payload, ou None se o token for inválido, expirado ou adulterado."""
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError:
        return None
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common
uv run pytest -v
uv run ruff check .
```

Expected: 14 testes PASS, ruff sem erro.

- [ ] **Step 6: Commit**

```bash
git add back-end/packages/edu-common
git commit -m "feat(edu-common): add shared password hashing and JWT helpers"
```

---

### Task 3: `edu-common` — dependências FastAPI de autenticação

**Files:**
- Create: `back-end/packages/edu-common/src/edu_common/deps.py`
- Test: `back-end/packages/edu-common/tests/test_deps.py`

**Interfaces:**
- Consumes: `decode_token` da task 2
- Produces:
  - `build_auth_deps(secret: str, algorithm: str = "HS256") -> AuthDeps`
  - `AuthDeps` é uma dataclass com os atributos `get_current_user`, `get_current_user_id`, `require_role`
  - `get_current_user` devolve o payload do JWT **acrescido de** `raw_token` (o chatbot precisa repassar o token na chamada ao learning)

- [ ] **Step 1: Escrever os testes que falham**

`back-end/packages/edu-common/tests/test_deps.py`:

```python
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from edu_common.deps import build_auth_deps
from edu_common.security import create_access_token, create_refresh_token

SECRET = "test-secret-not-a-real-key"
auth = build_auth_deps(SECRET)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()

    @application.get("/me")
    async def me(user: dict = Depends(auth.get_current_user)):
        return {"sub": user["sub"], "role": user["role"], "has_raw": bool(user.get("raw_token"))}

    @application.get("/my-id")
    async def my_id(user_id: str = Depends(auth.get_current_user_id)):
        return {"id": user_id}

    @application.get("/admin-only")
    async def admin_only(user: dict = Depends(auth.require_role("admin"))):
        return {"ok": True, "role": user["role"]}

    @application.get("/staff-only")
    async def staff_only(user: dict = Depends(auth.require_role("separador", "entregador"))):
        return {"ok": True}

    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_get_current_user_returns_payload(client):
    token = create_access_token("user-1", "student", SECRET)
    response = await client.get("/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {"sub": "user-1", "role": "student", "has_raw": True}


async def test_get_current_user_id_returns_sub(client):
    token = create_access_token("user-42", "student", SECRET)
    response = await client.get("/my-id", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {"id": "user-42"}


async def test_missing_token_is_rejected(client):
    assert (await client.get("/me")).status_code == 403


async def test_invalid_token_is_rejected(client):
    response = await client.get("/me", headers=bearer("nao.e.um.jwt"))
    assert response.status_code == 401


async def test_token_signed_with_other_secret_is_rejected(client):
    token = create_access_token("user-1", "student", "outro-secret")
    assert (await client.get("/me", headers=bearer(token))).status_code == 401


async def test_refresh_token_is_rejected_where_access_is_required(client):
    token = create_refresh_token("user-1", "student", SECRET)
    response = await client.get("/me", headers=bearer(token))
    assert response.status_code == 401


async def test_require_role_allows_matching_role(client):
    token = create_access_token("admin-1", "admin", SECRET)
    response = await client.get("/admin-only", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_require_role_forbids_other_role(client):
    token = create_access_token("user-1", "student", SECRET)
    assert (await client.get("/admin-only", headers=bearer(token))).status_code == 403


async def test_require_role_accepts_any_of_several_roles(client):
    for role in ("separador", "entregador"):
        token = create_access_token("staff", role, SECRET)
        assert (await client.get("/staff-only", headers=bearer(token))).status_code == 200


async def test_require_role_still_rejects_invalid_token(client):
    assert (await client.get("/admin-only", headers=bearer("lixo"))).status_code == 401
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common
uv run pytest tests/test_deps.py -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'edu_common.deps'`.

- [ ] **Step 3: Implementar**

`back-end/packages/edu-common/src/edu_common/deps.py`:

> **O código abaixo é a versão original do plano e foi superado.** A revisão da
> task 3 encontrou que `build_auth_deps("")` montava um portão que validava
> qualquer token (chave HMAC vazia assina qualquer coisa), e o `HTTPBearer` do
> FastAPI 0.141 devolve 401 em header ausente, quebrando o contrato 401/403. A
> implementação que vale está no arquivo, commitada em `e38bc9e`: valida o
> segredo no build, usa `auto_error=False` com 403 explícito, e avisa no
> docstring que o dict devolvido carrega o bearer token vivo. Não reescreva
> este arquivo a partir do bloco abaixo.

```python
"""Dependências FastAPI de autenticação, parametrizadas pelo segredo do serviço.

Cada serviço chama `build_auth_deps(settings.jwt_secret)` uma vez e usa o
resultado nos seus routers — assim a validação de JWT vive num lugar só, mas
nenhum serviço precisa importar a config de outro.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from edu_common.security import DEFAULT_ALGORITHM, decode_token

bearer_scheme = HTTPBearer()


@dataclass(frozen=True)
class AuthDeps:
    get_current_user: Callable
    get_current_user_id: Callable
    require_role: Callable


def build_auth_deps(secret: str, algorithm: str = DEFAULT_ALGORITHM) -> AuthDeps:
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ) -> dict:
        # `expected_type="access"` faz o próprio decode_token recusar um refresh
        # token — a checagem não fica espalhada por serviço.
        payload = decode_token(credentials.credentials, secret, algorithm, expected_type="access")
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
            )
        # O token bruto acompanha o payload porque chamadas serviço-a-serviço
        # (chatbot -> learning) repassam o MESMO token do aluno.
        return {**payload, "raw_token": credentials.credentials}

    async def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
        return user["sub"]

    def require_role(*allowed_roles: str) -> Callable:
        async def verifier(user: dict = Depends(get_current_user)) -> dict:
            if user.get("role") not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Sem permissão para esta ação",
                )
            return user

        return verifier

    return AuthDeps(
        get_current_user=get_current_user,
        get_current_user_id=get_current_user_id,
        require_role=require_role,
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common
uv run pytest -v
uv run ruff check .
```

Expected: 24 testes PASS no total (14 da task 2 + 10 desta).

- [ ] **Step 5: Commit**

```bash
git add back-end/packages/edu-common
git commit -m "feat(edu-common): add parametrized FastAPI auth dependencies"
```

---

### Task 4: `edu-common` — publisher e consumer de eventos

**Files:**
- Create: `back-end/packages/edu-common/src/edu_common/events.py`
- Test: `back-end/packages/edu-common/tests/test_events.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `EventPublisher(rabbitmq_url: str, exchange_name: str)` com `async connect()`, `async publish(routing_key: str, payload: dict)`, `async close()`
  - `EventConsumer(rabbitmq_url: str, exchange_name: str)` com `async connect()`, `async bind(queue_name: str, routing_keys: list[str], handler)`, `async close()`

- [ ] **Step 1: Escrever os testes que falham**

Os testes usam um duplo de `aio_pika` — não sobem RabbitMQ. O contrato verificado é: exchange topic durável, mensagem JSON persistente, e o bind de fila por routing key.

`back-end/packages/edu-common/tests/test_events.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from edu_common.events import EventConsumer, EventPublisher

URL = "amqp://guest:guest@localhost/"
EXCHANGE = "edu.events"


@pytest.fixture
def fake_aio_pika(monkeypatch):
    exchange = AsyncMock()
    channel = AsyncMock()
    channel.declare_exchange = AsyncMock(return_value=exchange)
    queue = AsyncMock()
    channel.declare_queue = AsyncMock(return_value=queue)
    connection = AsyncMock()
    connection.channel = AsyncMock(return_value=channel)

    connect_robust = AsyncMock(return_value=connection)
    monkeypatch.setattr("edu_common.events.aio_pika.connect_robust", connect_robust)

    fake = MagicMock()
    fake.connect_robust = connect_robust
    fake.connection = connection
    fake.channel = channel
    fake.exchange = exchange
    fake.queue = queue
    return fake


async def test_publisher_declares_durable_topic_exchange(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()

    fake_aio_pika.connect_robust.assert_awaited_once_with(URL)
    name, *_ = fake_aio_pika.channel.declare_exchange.await_args.args
    kwargs = fake_aio_pika.channel.declare_exchange.await_args.kwargs
    assert name == EXCHANGE
    assert kwargs["durable"] is True


async def test_publisher_sends_json_body_with_routing_key(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()
    await publisher.publish("order.created", {"pedido_id": 7, "aluno_id": "abc"})

    message, = fake_aio_pika.exchange.publish.await_args.args
    kwargs = fake_aio_pika.exchange.publish.await_args.kwargs
    assert kwargs["routing_key"] == "order.created"
    assert json.loads(message.body) == {"pedido_id": 7, "aluno_id": "abc"}
    assert message.content_type == "application/json"


async def test_publish_before_connect_raises(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    with pytest.raises(RuntimeError, match="not connected"):
        await publisher.publish("order.created", {})


async def test_close_is_safe_when_never_connected(fake_aio_pika):
    await EventPublisher(URL, EXCHANGE).close()


async def test_close_closes_the_connection(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()
    await publisher.close()
    fake_aio_pika.connection.close.assert_awaited_once()


async def test_consumer_binds_every_routing_key_to_one_queue(fake_aio_pika):
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    async def handler(message):
        return None

    await consumer.bind("analytics.event_log", ["order.created", "order.status_changed"], handler)

    fake_aio_pika.channel.declare_queue.assert_awaited_once_with(
        "analytics.event_log", durable=True
    )
    bound = [call.kwargs["routing_key"] for call in fake_aio_pika.queue.bind.await_args_list]
    assert bound == ["order.created", "order.status_changed"]
    fake_aio_pika.queue.consume.assert_awaited_once_with(handler)


async def test_consumer_bind_before_connect_raises(fake_aio_pika):
    consumer = EventConsumer(URL, EXCHANGE)

    async def handler(message):
        return None

    with pytest.raises(RuntimeError, match="not connected"):
        await consumer.bind("q", ["k"], handler)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common
uv run pytest tests/test_events.py -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'edu_common.events'`.

- [ ] **Step 3: Implementar**

`back-end/packages/edu-common/src/edu_common/events.py`:

```python
"""Publisher e consumer da exchange de eventos, compartilhados entre serviços.

Substitui as cópias idênticas de `events/publisher.py` que existiam em auth,
commerce e learning, e o boilerplate de conexão dos consumers de notification
e analytics. O contrato da exchange (topic, durável, mensagem persistente) vive
aqui — mudá-lo num lugar só passa a valer para todos.
"""

import json
from collections.abc import Awaitable, Callable

import aio_pika
from loguru import logger

Handler = Callable[[aio_pika.IncomingMessage], Awaitable[None]]


class _RabbitConnection:
    def __init__(self, rabbitmq_url: str, exchange_name: str) -> None:
        self._url = rabbitmq_url
        self._exchange_name = exchange_name
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        logger.info("Conectado à exchange {}", self._exchange_name)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None


class EventPublisher(_RabbitConnection):
    async def publish(self, routing_key: str, payload: dict) -> None:
        if self._exchange is None:
            raise RuntimeError("EventPublisher not connected — call connect() first")
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key)


class EventConsumer(_RabbitConnection):
    async def bind(self, queue_name: str, routing_keys: list[str], handler: Handler) -> None:
        if self._channel is None or self._exchange is None:
            raise RuntimeError("EventConsumer not connected — call connect() first")
        queue = await self._channel.declare_queue(queue_name, durable=True)
        for routing_key in routing_keys:
            await queue.bind(self._exchange, routing_key=routing_key)
        await queue.consume(handler)
        logger.info("Fila {} ligada a {}", queue_name, routing_keys)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/packages/edu-common
uv run pytest -v
uv run ruff check .
```

Expected: 31 testes PASS no total.

- [ ] **Step 5: Commit**

```bash
git add back-end/packages/edu-common
git commit -m "feat(edu-common): add RabbitMQ event publisher and consumer"
```

---

### Task 5: `api-gateway`

**Files:**
- Create: `back-end/api-gateway/` (copiado da refatoração)
- Modify: `back-end/api-gateway/app/main.py` (CORS por env)
- Modify: `back-end/api-gateway/app/config.py` (`cors_origins`)
- Modify: `back-end/api-gateway/app/routing.py` (rotas em inglês)
- Create: `back-end/api-gateway/pyproject.toml`, `tests/conftest.py`, `tests/test_routing.py`, `tests/test_proxy.py`

**Interfaces:**
- Consumes: nada de `edu-common` (o gateway não valida JWT — é proxy burro)
- Produces: `resolve_destination(path: str) -> tuple[str, str] | None` (renomeado de `resolver_destino`), e o app FastAPI em `app.main:app`

- [ ] **Step 1: Copiar o serviço e criar o `pyproject.toml`**

```bash
cp -r "/home/elias/Downloads/edu-project (2)/api-gateway" /home/elias/programming/fiap/estuda_app/back-end/api-gateway
rm /home/elias/programming/fiap/estuda_app/back-end/api-gateway/requirements.txt
mkdir -p /home/elias/programming/fiap/estuda_app/back-end/api-gateway/tests
```

Criar `back-end/api-gateway/pyproject.toml` pela **Recipe A** com `<service>` = `api-gateway`, sem a linha `"edu-common",` nas dependencies, sem `[tool.uv.sources]`, sem o `per-file-ignores` de alembic, e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "httpx>=0.28.0",
    "pydantic-settings>=2.6.0",
    "loguru>=0.7.2",
```

- [ ] **Step 2: Escrever os testes que falham**

`back-end/api-gateway/tests/conftest.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

`back-end/api-gateway/tests/test_routing.py`:

```python
import pytest

from app.routing import SERVICE_MAP, resolve_destination


@pytest.mark.parametrize(
    ("path", "expected_service"),
    [
        ("auth/login", "auth"),
        ("users/me", "auth"),
        ("addresses", "auth"),
        ("subjects", "learning"),
        ("topics/1/subtopics", "learning"),
        ("diagnostic/answer", "learning"),
        ("recommendations", "learning"),
        ("reviews/today", "learning"),
        ("products", "commerce"),
        ("orders/1/tracking", "commerce"),
        ("cart/items", "commerce"),
        ("payment-methods", "commerce"),
        ("picking/queue", "commerce"),
        ("delivery/1/collect", "commerce"),
        ("occurrences", "commerce"),
        ("notifications/devices", "notification"),
        ("analytics/summary", "analytics"),
        ("chat/explain-question", "chatbot"),
        ("support", "chatbot"),
    ],
)
def test_first_segment_resolves_to_expected_service(path: str, expected_service: str):
    assert SERVICE_MAP[path.split("/", 1)[0]] == expected_service


def test_resolve_destination_keeps_full_path():
    destination = resolve_destination("orders/42/tracking")
    assert destination is not None
    base_url, final_path = destination
    assert final_path == "/orders/42/tracking"
    assert base_url.startswith("http")


def test_resolve_destination_returns_none_for_unmapped_path():
    assert resolve_destination("rota-inexistente") is None


def test_resolve_destination_returns_none_for_empty_path():
    assert resolve_destination("") is None


def test_no_portuguese_paths_remain_in_the_public_contract():
    portuguese = {
        "produtos", "pedidos", "separacao", "entrega", "ocorrencias",
        "materias", "temas", "subtemas", "diagnostico", "recomendacoes", "revisoes",
    }
    assert portuguese.isdisjoint(SERVICE_MAP.keys())
```

`back-end/api-gateway/tests/test_proxy.py`:

```python
import httpx
import pytest


async def test_health_does_not_need_a_backend(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unmapped_path_returns_404_from_the_gateway(client):
    response = await client.get("/api/rota-inexistente")
    assert response.status_code == 404
    assert "Nenhum serviço mapeado" in response.json()["detail"]


async def test_proxy_forwards_method_body_and_query(client, monkeypatch):
    captured = {}

    async def fake_request(self, method, url, **kwargs):
        captured.update(method=method, url=url, content=kwargs["content"], params=kwargs["params"])
        return httpx.Response(201, json={"id": 1}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    response = await client.post("/api/orders?dry_run=1", json={"total": "10.00"})

    assert response.status_code == 201
    assert response.json() == {"id": 1}
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/orders")
    assert b"total" in captured["content"]
    assert dict(captured["params"])["dry_run"] == "1"


async def test_proxy_returns_503_when_service_is_down(client, monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    response = await client.get("/api/products")
    assert response.status_code == 503


async def test_proxy_returns_504_on_timeout(client, monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        raise httpx.TimeoutException("too slow")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    response = await client.get("/api/products")
    assert response.status_code == 504


@pytest.mark.parametrize("origin", ["http://localhost:3000", "https://app.edu.com"])
async def test_cors_allows_only_configured_origins(client, origin):
    from app.config import settings

    response = await client.options(
        "/api/products",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    allowed = response.headers.get("access-control-allow-origin")
    if origin in settings.cors_origins:
        assert allowed == origin
    else:
        assert allowed is None


async def test_cors_is_not_a_wildcard():
    from app.main import app as gateway_app

    cors = [m for m in gateway_app.user_middleware if "CORSMiddleware" in str(m)]
    assert cors, "CORS middleware ausente"
    assert "*" not in cors[0].kwargs["allow_origins"]
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/api-gateway
uv sync
uv run pytest -v
```

Expected: FAIL — `resolve_destination` não existe (o código tem `resolver_destino`), `SERVICE_MAP` ainda tem chaves em português, e `settings.cors_origins` não existe.

- [ ] **Step 4: Traduzir o mapa de rotas para inglês**

Substituir o `SERVICE_MAP` e a função em `back-end/api-gateway/app/routing.py`:

```python
from app.config import settings

# Primeiro segmento do path (depois de /api/) -> qual serviço atende.
# Mantém o Gateway "burro" de propósito: ele só decide PARA ONDE mandar,
# nunca decide autenticação/autorização — isso continua 100% no serviço
# de destino (cada um valida o JWT com o mesmo JWT_SECRET compartilhado).
SERVICE_MAP: dict[str, str] = {
    "auth": "auth",
    "users": "auth",
    "addresses": "auth",
    "subjects": "learning",
    "topics": "learning",
    "subtopics": "learning",
    "diagnostic": "learning",
    "recommendations": "learning",
    "reviews": "learning",
    "products": "commerce",
    "orders": "commerce",
    "cart": "commerce",
    "payment-methods": "commerce",
    "picking": "commerce",
    "delivery": "commerce",
    "occurrences": "commerce",
    "admin": "commerce",
    "notifications": "notification",
    "analytics": "analytics",
    "chat": "chatbot",
    "support": "chatbot",
}

SERVICE_BASE_URLS: dict[str, str] = {
    "auth": settings.auth_service_url,
    "learning": settings.learning_service_url,
    "commerce": settings.commerce_service_url,
    "notification": settings.notification_service_url,
    "analytics": settings.analytics_service_url,
    "chatbot": settings.chatbot_service_url,
}


def resolve_destination(path: str) -> tuple[str, str] | None:
    """Recebe o path já sem o prefixo `/api` (ex: "auth/login") e devolve
    (base_url_do_servico, path_final_com_barra_inicial), ou None se não
    houver serviço mapeado."""
    first_segment = path.split("/", 1)[0] if path else ""
    service = SERVICE_MAP.get(first_segment)
    if service is None:
        return None
    return SERVICE_BASE_URLS[service], f"/{path}"
```

Nota: `cart`, `orders`, `products`, `payment-methods` e `support` apontam para serviços que ainda não implementam esses endpoints — a fase 2 os implementa. Até lá respondem 404 vindo do serviço de destino, não do gateway.

- [ ] **Step 5: Trocar o CORS curinga por lista vinda do ambiente**

Em `back-end/api-gateway/app/config.py`, acrescentar o campo à classe `Settings`:

```python
    cors_origins: list[str] = ["http://localhost:3000"]
```

Em `back-end/api-gateway/app/main.py`, trocar o bloco do middleware por:

```python
# Origens liberadas vêm do ambiente (CORS_ORIGINS, lista JSON). Curinga com
# allow_credentials=True é rejeitado pelos browsers e vazaria a API para
# qualquer site — a lista explícita é obrigatória mesmo em dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

E trocar o import e a chamada de `resolver_destino` para `resolve_destination`:

```python
from app.routing import resolve_destination
```

```python
    destination = resolve_destination(path)
    if destination is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum serviço mapeado para '/{path}'. Verifique app/routing.py.",
        )

    base_url, final_path = destination
    url = f"{base_url}{final_path}"
```

Renomear as variáveis restantes do handler (`resposta` → `response`, `headers_resposta` → `response_headers`) para o corpo ficar coerente.

- [ ] **Step 6: Rodar os testes e confirmar que passam**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/api-gateway
CORS_ORIGINS='["http://localhost:3000"]' uv run pytest -v
uv run ruff check .
```

Expected: todos PASS.

- [ ] **Step 7: Commit**

```bash
git add back-end/api-gateway
git commit -m "feat(gateway): import API gateway with English routes and env-driven CORS"
```

---

### Task 6: `auth-users-service` — scaffold, Alembic e edu-common

**Files:**
- Create: `back-end/auth-users-service/` (copiado, **sem** o `.env`)
- Delete: `back-end/auth-users-service/app/security.py` (vai para edu-common)
- Modify: `back-end/auth-users-service/app/dependencies.py`
- Modify: `back-end/auth-users-service/app/config.py`
- Modify: `back-end/auth-users-service/app/events/publisher.py`
- Modify: `back-end/auth-users-service/app/models/user.py`, `password_reset.py`, `address.py`
- Create: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/versions/*_baseline_schema.py`
- Create: `tests/conftest.py`, `tests/test_health.py`

**Interfaces:**
- Consumes: `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `build_auth_deps` de `edu-common`
- Produces: módulo `app.dependencies` expondo `get_current_user`, `get_current_user_id`, `requer_papel`; `app.events.publisher` expondo `init_publisher()`, `publish_event()`, `close_publisher()`

- [ ] **Step 1: Copiar sem o `.env` e sem o `requirements.txt`**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp -r "/home/elias/Downloads/edu-project (2)/auth-users-service" auth-users-service
rm -f auth-users-service/.env auth-users-service/requirements.txt
test ! -f auth-users-service/.env && echo "OK: .env de sandbox não foi copiado"
```

O `.env` original trazia um `JWT_SECRET` de sandbox commitado. Ele não entra no repositório em hipótese alguma — e o valor não é reproduzido aqui, porque um segredo citado em documentação continua sendo um segredo no repositório.

- [ ] **Step 2: Criar o `pyproject.toml`**

Pela **Recipe A** com `<service>` = `auth-users-service` e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic[email]>=2.10.0",
    "pydantic-settings>=2.6.0",
    "aio-pika>=9.4.2",
    "loguru>=0.7.2",
```

Sem `passlib` e sem o pin `bcrypt==3.2.2`: o hash passa a vir de `edu-common`, que usa `bcrypt>=4.2.0` direto. O formato `$2b$` é o mesmo do passlib, então hashes já existentes continuam verificáveis.

- [ ] **Step 3: Acrescentar `database_url_test` à config**

Em `back-end/auth-users-service/app/config.py`, dentro da classe `Settings`:

```python
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/auth_test"
    cors_origins: list[str] = ["http://localhost:3000"]
```

- [ ] **Step 4: Trocar `app/security.py` e `app/dependencies.py` por edu-common**

```bash
rm /home/elias/programming/fiap/estuda_app/back-end/auth-users-service/app/security.py
```

Substituir `back-end/auth-users-service/app/dependencies.py` inteiro por:

```python
"""Dependências de auth do serviço — construídas a partir de edu-common.

Os aliases em português preservam os nomes que os routers já usam.
"""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
get_current_user_id = _auth.get_current_user_id
requer_papel = _auth.require_role
```

Nos arquivos que importavam de `app.security`, trocar o import. Em `app/routers/auth.py` e onde mais aparecer:

```python
from edu_common.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
```

E adaptar as chamadas: `hash_senha(x)` → `hash_password(x)`; `verificar_senha(a, b)` → `verify_password(a, b)`; `criar_access_token(sub, role)` → `create_access_token(sub, role, settings.jwt_secret, settings.jwt_algorithm, settings.access_token_expire_minutes)`; `criar_refresh_token(sub, role)` → `create_refresh_token(sub, role, settings.jwt_secret, settings.jwt_algorithm, settings.refresh_token_expire_days)`.

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
grep -rn "app.security\|hash_senha\|verificar_senha\|criar_access_token\|criar_refresh_token\|decodificar_token" app/
```

Expected após a edição: nenhuma ocorrência.

- [ ] **Step 5: Trocar o publisher local pelo de edu-common**

Substituir `back-end/auth-users-service/app/events/publisher.py` inteiro por:

```python
"""Publisher de eventos do serviço — instância única sobre edu-common."""

from edu_common.events import EventPublisher

from app.config import settings

_publisher = EventPublisher(settings.rabbitmq_url, settings.exchange_name)


async def init_publisher() -> None:
    await _publisher.connect()


async def publish_event(routing_key: str, payload: dict) -> None:
    await _publisher.publish(routing_key, payload)


async def close_publisher() -> None:
    await _publisher.close()
```

- [ ] **Step 6: Alinhar os models ao `schema.sql` antes do baseline**

O `schema.sql` cria índices que os models não declaram. Em `back-end/auth-users-service/app/models/user.py`, garantir `index=True` em `email` e `role`. Em `password_reset.py`, `index=True` em `user_id`. Em `address.py`, `index=True` em `user_id`. Trocar todo `DateTime` de `criado_em`/`atualizado_em`/`expira_em` por `DateTime(timezone=True)`.

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
grep -n "index=True\|DateTime" app/models/*.py
```

- [ ] **Step 7: Gerar a baseline do Alembic**

Seguir a **Recipe D**, com `<model imports>` na Recipe B =

```python
from app.models import address as address_models  # noqa: F401
from app.models import password_reset as password_reset_models  # noqa: F401
from app.models import user as user_models  # noqa: F401
```

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
uv sync
uv run alembic revision --autogenerate -m "baseline schema"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "sync check"
```

Expected: o segundo autogenerate produz um arquivo com `upgrade()` e `downgrade()` contendo apenas `pass`. Apagar esse arquivo.

```bash
rm alembic/versions/*sync_check*.py
rm schema.sql
```

- [ ] **Step 8: Criar o conftest e um teste de fumaça**

`back-end/auth-users-service/tests/conftest.py` pela **Recipe C**, com `<model imports>` =

```python
    from app.models import address as address_models  # noqa: F401
    from app.models import password_reset as password_reset_models  # noqa: F401
    from app.models import user as user_models  # noqa: F401
```

`back-end/auth-users-service/tests/test_health.py`:

```python
async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]


async def test_every_route_is_registered_under_a_known_prefix(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    known = ("/auth", "/users")
    unknown = [p for p in paths if not p.startswith(known)]
    assert unknown == []
```

- [ ] **Step 9: Rodar e confirmar verde**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
uv run pytest -v
uv run ruff check .
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add back-end/auth-users-service
git commit -m "feat(auth-service): import auth-users-service on uv, alembic and edu-common"
```

---

### Task 7: `auth-users-service` — testes de caracterização e correções de segurança

**Files:**
- Modify: `back-end/auth-users-service/app/routers/auth.py` (OTP no log, tz-aware)
- Modify: `back-end/auth-users-service/app/routers/users.py` (paginação)
- Modify: `back-end/auth-users-service/app/routers/addresses.py` (paginação)
- Test: `back-end/auth-users-service/tests/test_auth_routes.py`, `tests/test_password_reset.py`, `tests/test_users_routes.py`, `tests/test_addresses_routes.py`

**Interfaces:**
- Consumes: fixtures `client` e `db_session` da task 6
- Produces: suíte que congela o comportamento de `/auth/*`, `/users/*` e `/auth/addresses/*`

- [ ] **Step 1: Escrever os testes de registro e login**

`back-end/auth-users-service/tests/test_auth_routes.py`:

```python
import pytest

REGISTER = {
    "nome": "Maria Teste",
    "email": "maria@teste.com",
    "password": "Senha@123",
}


async def test_register_creates_user_and_returns_tokens(client):
    response = await client.post("/auth/register", json=REGISTER)
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "maria@teste.com"


async def test_register_never_returns_the_password_hash(client):
    body = (await client.post("/auth/register", json=REGISTER)).json()
    assert "senha_hash" not in str(body)
    assert "password" not in body["user"]


async def test_register_rejects_duplicate_email(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/register", json=REGISTER)
    assert response.status_code == 400


async def test_login_returns_tokens_for_valid_credentials(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_rejects_wrong_password(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": "errada"}
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_email_with_same_status(client):
    response = await client.post(
        "/auth/login", json={"email": "ninguem@teste.com", "password": "Senha@123"}
    )
    assert response.status_code == 401


async def test_me_returns_the_authenticated_user(client):
    tokens = (await client.post("/auth/register", json=REGISTER)).json()
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == REGISTER["email"]


async def test_me_requires_authentication(client):
    assert (await client.get("/auth/me")).status_code == 403


@pytest.mark.parametrize("token", ["lixo", "a.b.c"])
async def test_me_rejects_invalid_token(client, token):
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_refresh_exchanges_refresh_token_for_new_access_token(client):
    tokens = (await client.post("/auth/register", json=REGISTER)).json()
    response = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_an_access_token(client):
    tokens = (await client.post("/auth/register", json=REGISTER)).json()
    response = await client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401
```

- [ ] **Step 2: Escrever os testes do reset de senha, incluindo o vazamento do OTP**

`back-end/auth-users-service/tests/test_password_reset.py`:

```python
import pytest
from loguru import logger

REGISTER = {"nome": "Maria", "email": "maria@teste.com", "password": "Senha@123"}


@pytest.fixture
def captured_logs():
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(str(message)), level="DEBUG")
    yield messages
    logger.remove(sink_id)


async def test_request_returns_200_for_existing_email(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    assert response.status_code == 200


async def test_request_returns_200_for_unknown_email_to_prevent_enumeration(client):
    response = await client.post(
        "/auth/password-reset/request", json={"email": "ninguem@teste.com"}
    )
    assert response.status_code == 200


async def test_request_never_returns_the_code(client):
    # Procurar a substring "code" no corpo não prova nada: a resposta é em
    # português ("código"), então a asserção passaria mesmo com os seis dígitos
    # no meio da mensagem. O que precisa ser proibido é o número.
    import re

    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    assert not re.search(r"\b\d{6}\b", response.text), f"OTP vazou na resposta: {response.text}"


async def test_request_never_logs_the_code(client, captured_logs):
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    joined = " ".join(captured_logs)
    assert "código para" not in joined
    import re
    assert not re.search(r"\b\d{6}\b", joined), f"código de 6 dígitos vazou no log: {joined}"


async def test_confirm_rejects_wrong_code(client):
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    response = await client.post(
        "/auth/password-reset/confirm",
        json={"email": REGISTER["email"], "code": "000000", "new_password": "Nova@123"},
    )
    assert response.status_code == 400


async def test_confirm_rejects_unknown_email_with_the_same_generic_error(client):
    response = await client.post(
        "/auth/password-reset/confirm",
        json={"email": "ninguem@teste.com", "code": "123456", "new_password": "Nova@123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Código inválido ou expirado"
```

- [ ] **Step 3: Rodar e confirmar que estes testes já passam**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
uv run pytest tests/test_password_reset.py -v
grep -rn "print(\|utcnow\|random\." app/
```

Expected: **todos PASS**, e o grep sem nenhuma ocorrência.

A task 6 já removeu o `print()` do código OTP, trocou `datetime.utcnow()` por `datetime.now(UTC)` e substituiu `random.randint()` por geração criptograficamente segura — são constraints globais incondicionais, não dava para deixar o serviço commitado violando-as. Estes testes são, portanto, **testes de regressão**: eles travam o comportamento para que ninguém reintroduza o vazamento. Se algum falhar aqui, é regressão de verdade — investigar antes de seguir.

- [ ] **Step 5: Escrever os testes de paginação e ownership**

`back-end/auth-users-service/tests/test_users_routes.py`:

```python
from edu_common.security import create_access_token

from app.config import settings


def admin_headers() -> dict[str, str]:
    token = create_access_token("11111111-1111-1111-1111-111111111111", "admin", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def student_headers() -> dict[str, str]:
    token = create_access_token("22222222-2222-2222-2222-222222222222", "student", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_list_users_requires_admin_role(client):
    assert (await client.get("/users", headers=student_headers())).status_code == 403


async def test_list_users_requires_authentication(client):
    assert (await client.get("/users")).status_code == 403


async def test_list_users_is_paginated(client):
    response = await client.get("/users", headers=admin_headers())
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_users_rejects_limit_above_the_cap(client):
    response = await client.get("/users?limit=1000", headers=admin_headers())
    assert response.status_code == 422


async def test_list_users_respects_limit(client):
    for i in range(3):
        await client.post(
            "/auth/register",
            json={"nome": f"User {i}", "email": f"u{i}@teste.com", "password": "Senha@123"},
        )
    response = await client.get("/users?limit=2", headers=admin_headers())
    assert len(response.json()) == 2
```

`back-end/auth-users-service/tests/test_addresses_routes.py`:

```python
REGISTER = {"nome": "Maria", "email": "maria@teste.com", "password": "Senha@123"}
OTHER = {"nome": "Pedro", "email": "pedro@teste.com", "password": "Senha@123"}

ADDRESS = {
    "label": "Casa",
    "zip_code": "01001-000",
    "street": "Praça da Sé",
    "number": "1",
    "complement": "",
    "neighborhood": "Sé",
    "city": "São Paulo",
    "state": "SP",
    "is_favorite": True,
}


async def _register(client, payload) -> dict[str, str]:
    tokens = (await client.post("/auth/register", json=payload)).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_create_and_list_own_address(client):
    headers = await _register(client, REGISTER)
    created = await client.post("/auth/addresses", json=ADDRESS, headers=headers)
    assert created.status_code == 201

    listed = await client.get("/auth/addresses", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["street"] == "Praça da Sé"


async def test_addresses_require_authentication(client):
    assert (await client.get("/auth/addresses")).status_code == 403


async def test_user_cannot_see_another_users_addresses(client):
    maria = await _register(client, REGISTER)
    await client.post("/auth/addresses", json=ADDRESS, headers=maria)

    pedro = await _register(client, OTHER)
    assert (await client.get("/auth/addresses", headers=pedro)).json() == []


async def test_user_cannot_patch_another_users_address(client):
    maria = await _register(client, REGISTER)
    address_id = (await client.post("/auth/addresses", json=ADDRESS, headers=maria)).json()["id"]

    pedro = await _register(client, OTHER)
    response = await client.patch(
        f"/auth/addresses/{address_id}", json={"label": "Roubado"}, headers=pedro
    )
    assert response.status_code == 404


async def test_user_cannot_delete_another_users_address(client):
    maria = await _register(client, REGISTER)
    address_id = (await client.post("/auth/addresses", json=ADDRESS, headers=maria)).json()["id"]

    pedro = await _register(client, OTHER)
    assert (await client.delete(f"/auth/addresses/{address_id}", headers=pedro)).status_code == 404


async def test_list_addresses_is_paginated(client):
    headers = await _register(client, REGISTER)
    for i in range(3):
        await client.post("/auth/addresses", json={**ADDRESS, "number": str(i)}, headers=headers)
    response = await client.get("/auth/addresses?limit=2", headers=headers)
    assert len(response.json()) == 2
```

- [ ] **Step 6: Rodar e confirmar que os testes de paginação falham**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
uv run pytest tests/test_users_routes.py tests/test_addresses_routes.py -v
```

Expected: os testes de `limit` FAIL — os endpoints não aceitam paginação.

- [ ] **Step 7: Adicionar paginação aos endpoints de listagem**

Em `back-end/auth-users-service/app/routers/users.py`, trocar a assinatura de `listar_usuarios`:

```python
@router.get("", response_model=list[UserOut])
async def listar_usuarios(
    role: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Gestão de staff — só admin. Permite filtrar por papel (ex: ?role=separador)."""
    query = select(User)
    if role:
        query = query.where(User.role == role)
    query = query.order_by(User.criado_em.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
```

Acrescentar `Query` ao import do FastAPI no topo do arquivo:

```python
from fastapi import APIRouter, Depends, Query
```

Fazer o mesmo em `back-end/auth-users-service/app/routers/addresses.py`, no `GET ""`: acrescentar `limit: int = Query(50, ge=1, le=200)` e `offset: int = Query(0, ge=0)`, e aplicar `.limit(limit).offset(offset)` na query já filtrada por `user_id`.

- [ ] **Step 8: Rodar a suíte inteira**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/auth-users-service
uv run pytest -v
uv run ruff check .
```

Expected: tudo PASS.

- [ ] **Step 9: Commit**

```bash
git add back-end/auth-users-service
git commit -m "test(auth-service): add characterization tests and fix OTP logging and pagination"
```

---

### Task 8: `learning-service` — scaffold, Alembic e edu-common

**Files:**
- Create: `back-end/learning-service/` (copiado)
- Delete: `back-end/learning-service/app/security.py`
- Modify: `app/dependencies.py`, `app/config.py`, `app/events/publisher.py`
- Create: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/versions/*`
- Create: `tests/conftest.py`, `tests/test_health.py`

**Interfaces:**
- Consumes: `build_auth_deps`, `EventPublisher` de `edu-common`
- Produces: `app.dependencies` com `get_current_user`, `get_current_student_id`, `requer_papel`

- [ ] **Step 1: Copiar e criar o `pyproject.toml`**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp -r "/home/elias/Downloads/edu-project (2)/learning-service" learning-service
rm -f learning-service/requirements.txt
```

Pela **Recipe A** com `<service>` = `learning-service` e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "aio-pika>=9.4.2",
    "apscheduler>=3.10.4",
    "httpx>=0.28.0",
    "scikit-learn>=1.5.2",
    "sentence-transformers>=3.1.1",
    "groq>=0.11.0",
    "loguru>=0.7.2",
```

- [ ] **Step 2: Acrescentar `database_url_test` à config**

Em `back-end/learning-service/app/config.py`, dentro de `Settings`:

```python
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/learning_test"
```

- [ ] **Step 3: Trocar security e dependencies por edu-common**

```bash
rm /home/elias/programming/fiap/estuda_app/back-end/learning-service/app/security.py
```

Substituir `back-end/learning-service/app/dependencies.py` inteiro por:

```python
"""Dependências de auth do serviço — construídas a partir de edu-common."""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
get_current_student_id = _auth.get_current_user_id
requer_papel = _auth.require_role
```

- [ ] **Step 4: Trocar o publisher pelo de edu-common**

Substituir `back-end/learning-service/app/events/publisher.py` inteiro por:

```python
"""Publisher de eventos do serviço — instância única sobre edu-common."""

from edu_common.events import EventPublisher

from app.config import settings

_publisher = EventPublisher(settings.rabbitmq_url, settings.exchange_name)


async def init_publisher() -> None:
    await _publisher.connect()


async def publish_event(routing_key: str, payload: dict) -> None:
    await _publisher.publish(routing_key, payload)


async def close_publisher() -> None:
    await _publisher.close()
```

- [ ] **Step 5: Trocar o consumer pelo de edu-common**

Em `back-end/learning-service/app/events/consumer.py`, substituir a montagem manual de conexão/exchange/fila pelo `EventConsumer`, preservando os handlers e os bindings existentes:

```python
from edu_common.events import EventConsumer

from app.config import settings

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def start_consumer() -> None:
    await _consumer.connect()
    for queue_name, routing_key, handler in BINDINGS:
        await _consumer.bind(queue_name, [routing_key], handler)


async def close_consumer() -> None:
    await _consumer.close()
```

Onde `BINDINGS` é a lista de tuplas `(queue_name, routing_key, handler)` que já existia no `start_consumer` original, extraída para constante de módulo.

- [ ] **Step 6: Alinhar models e gerar a baseline do Alembic**

Trocar todo `DateTime` de coluna temporal por `DateTime(timezone=True)` em `app/models/*.py`, e conferir contra `schema.sql` que todo `CREATE INDEX` tem `index=True` no model correspondente.

Seguir a **Recipe D**, com `<model imports>` na Recipe B =

```python
from app.models import progresso as progresso_models  # noqa: F401
from app.models import questao as questao_models  # noqa: F401
from app.models import resposta as resposta_models  # noqa: F401
from app.models import subtema as subtema_models  # noqa: F401
```

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
uv sync
uv run alembic revision --autogenerate -m "baseline schema"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "sync check"
```

Expected: segundo autogenerate vazio.

```bash
rm alembic/versions/*sync_check*.py
rm schema.sql
```

- [ ] **Step 7: Criar conftest com fake de embeddings**

`back-end/learning-service/tests/conftest.py` pela **Recipe C**, com `<model imports>` =

```python
    from app.models import progresso as progresso_models  # noqa: F401
    from app.models import questao as questao_models  # noqa: F401
    from app.models import resposta as resposta_models  # noqa: F401
    from app.models import subtema as subtema_models  # noqa: F401
```

E acrescentar ao final do arquivo a fixture que evita baixar o modelo real:

```python
@pytest.fixture(autouse=True)
def fake_encoder(monkeypatch):
    """Evita baixar `paraphrase-multilingual-MiniLM-L12-v2` na suíte.

    Devolve um vetor determinístico por texto, o suficiente para exercitar a
    lógica de similaridade sem carregar centenas de MB. Testes que precisam do
    modelo real levam a marca `slow` e não usam esta fixture.
    """
    import numpy as np

    class FakeEncoder:
        def encode(self, texts, **kwargs):
            if isinstance(texts, str):
                texts = [texts]
            vectors = [
                np.array([len(t) % 7, sum(map(ord, t)) % 11, len(t.split()) % 5], dtype=float)
                for t in texts
            ]
            return np.vstack(vectors)

    monkeypatch.setattr(
        "app.services.classificacao_ia._carregar_modelo", lambda: FakeEncoder(), raising=False
    )
    monkeypatch.setattr(
        "app.services.recomendacao_semantica._carregar_modelo",
        lambda: FakeEncoder(),
        raising=False,
    )
```

Antes de escrever a fixture, confirmar o nome real da função de carga do modelo:

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
grep -n "SentenceTransformer\|def .*model\|_modelo" app/services/classificacao_ia.py app/services/recomendacao_semantica.py
```

Ajustar os alvos do `monkeypatch` para os nomes encontrados.

`back-end/learning-service/tests/test_health.py`:

```python
async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]
```

- [ ] **Step 8: Rodar e confirmar verde**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 9: Commit**

```bash
git add back-end/learning-service
git commit -m "feat(learning-service): import learning-service on uv, alembic and edu-common"
```

---

### Task 9: `learning-service` — rotas em inglês e testes de caracterização

**Files:**
- Modify: `app/routers/materias.py`, `diagnostico.py`, `recomendacao.py`, `revisao.py`
- Test: `tests/test_subjects_routes.py`, `tests/test_diagnostic_routes.py`, `tests/test_sm2.py`, `tests/test_decisao.py`

**Interfaces:**
- Consumes: fixtures `client`, `db_session`, `fake_encoder` da task 8
- Produces: contrato público `/subjects`, `/topics`, `/subtopics`, `/diagnostic`, `/recommendations`, `/reviews`

- [ ] **Step 1: Escrever os testes das regras de negócio puras**

Estas são as funções determinísticas do serviço — testáveis sem banco e sem HTTP.

`back-end/learning-service/tests/test_sm2.py`:

```python
from app.services.sm2 import calcular_proxima_revisao


def test_first_correct_answer_schedules_one_day_ahead():
    resultado = calcular_proxima_revisao(repeticoes=0, facilidade=2.5, intervalo=0, qualidade=5)
    assert resultado.intervalo == 1
    assert resultado.repeticoes == 1


def test_second_correct_answer_schedules_six_days_ahead():
    resultado = calcular_proxima_revisao(repeticoes=1, facilidade=2.5, intervalo=1, qualidade=5)
    assert resultado.intervalo == 6


def test_wrong_answer_resets_the_interval():
    resultado = calcular_proxima_revisao(repeticoes=5, facilidade=2.5, intervalo=30, qualidade=1)
    assert resultado.intervalo == 1
    assert resultado.repeticoes == 0


def test_easiness_never_drops_below_the_floor():
    resultado = calcular_proxima_revisao(repeticoes=0, facilidade=1.3, intervalo=0, qualidade=0)
    assert resultado.facilidade >= 1.3
```

Antes de escrever, confirmar a assinatura real:

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
sed -n '1,60p' app/services/sm2.py
```

Ajustar nomes de parâmetro e do retorno ao que o código expõe — o teste congela o comportamento **atual**, não um comportamento desejado.

`back-end/learning-service/tests/test_decisao.py`:

```python
from app.services.decisao import decidir_acao


def test_high_mastery_advances():
    assert decidir_acao(dominio=0.85, tem_tema_anterior=True) == "avancar"


def test_mid_mastery_studies():
    assert decidir_acao(dominio=0.50, tem_tema_anterior=True) == "estudar"


def test_low_mastery_goes_back_when_there_is_a_previous_topic():
    assert decidir_acao(dominio=0.20, tem_tema_anterior=True) == "retroceder"


def test_low_mastery_studies_when_there_is_no_previous_topic():
    assert decidir_acao(dominio=0.20, tem_tema_anterior=False) == "estudar"


def test_boundary_at_seventy_percent_advances():
    assert decidir_acao(dominio=0.70, tem_tema_anterior=True) == "avancar"


def test_boundary_at_thirty_percent_studies():
    assert decidir_acao(dominio=0.30, tem_tema_anterior=True) == "estudar"
```

Confirmar a assinatura real antes:

```bash
sed -n '1,60p' app/services/decisao.py
```

- [ ] **Step 2: Rodar e confirmar o estado atual**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
uv run pytest tests/test_sm2.py tests/test_decisao.py -v
```

Expected: passam depois de ajustar as assinaturas ao código real. Qualquer falha aqui é um bug real encontrado — anotar e corrigir o código, não o teste.

- [ ] **Step 3: Traduzir os prefixos dos routers para inglês**

| Arquivo | Antes | Depois |
|---|---|---|
| `app/routers/materias.py` | `prefix="/materias"` | `prefix="/subjects"` |
| `app/routers/materias.py` | `/materias/{id}/temas` | `/subjects/{id}/topics` |
| `app/routers/materias.py` | `prefix="/temas"` | `prefix="/topics"` |
| `app/routers/materias.py` | `/temas/{id}/subtemas` | `/topics/{id}/subtopics` |
| `app/routers/materias.py` | `/temas/{id}/questionario` | `/topics/{id}/quiz` |
| `app/routers/diagnostico.py` | `prefix="/diagnostico"` | `prefix="/diagnostic"` |
| `app/routers/diagnostico.py` | `/diagnostico/responder` | `/diagnostic/answer` |
| `app/routers/diagnostico.py` | `/diagnostico/questoes/{id}/contexto` | `/diagnostic/questions/{id}/context` |
| `app/routers/recomendacao.py` | `prefix="/recomendacoes"` | `prefix="/recommendations"` |
| `app/routers/revisao.py` | `prefix="/revisoes"` | `prefix="/reviews"` |
| `app/routers/revisao.py` | `/revisoes/hoje` | `/reviews/today` |

Só os paths mudam. Nomes de função, models e services seguem em português.

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
grep -rn "prefix=\|@router\." app/routers/
```

- [ ] **Step 4: Atualizar o chamador interno do chatbot**

O chatbot chama `GET /diagnostico/questoes/{id}/contexto` no learning. Esse path muda para `/diagnostic/questions/{id}/context` — a task 12 ajusta o chatbot. Registrar aqui para não esquecer:

```bash
grep -rn "diagnostico/questoes" "/home/elias/Downloads/edu-project (2)/chatbot-service"
```

- [ ] **Step 5: Escrever os testes de rota**

`back-end/learning-service/tests/test_subjects_routes.py`:

```python
async def test_subjects_are_listed_in_english_path(client):
    response = await client.get("/subjects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_old_portuguese_path_is_gone(client):
    assert (await client.get("/materias")).status_code == 404


async def test_subjects_listing_is_paginated(client):
    response = await client.get("/subjects?limit=1000")
    assert response.status_code == 422


async def test_topics_of_unknown_subject_return_404(client):
    assert (await client.get("/subjects/999999/topics")).status_code == 404
```

`back-end/learning-service/tests/test_diagnostic_routes.py`:

```python
async def test_answer_requires_authentication(client):
    response = await client.post("/diagnostic/answer", json={"tema_id": 1, "respostas": []})
    assert response.status_code == 403


async def test_question_context_requires_authentication(client):
    assert (await client.get("/diagnostic/questions/1/context")).status_code == 403


async def test_recommendations_require_authentication(client):
    assert (await client.get("/recommendations?tema_id=1")).status_code == 403


async def test_reviews_today_requires_authentication(client):
    assert (await client.get("/reviews/today")).status_code == 403
```

- [ ] **Step 6: Adicionar paginação onde os testes cobram**

Em `app/routers/materias.py`, no `GET ""` de subjects e nas listagens de topics e subtopics, acrescentar `limit: int = Query(50, ge=1, le=200)` e `offset: int = Query(0, ge=0)`, aplicando `.limit(limit).offset(offset)` na query. Importar `Query` do FastAPI.

- [ ] **Step 7: Rodar a suíte inteira**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/learning-service
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 8: Commit**

```bash
git add back-end/learning-service
git commit -m "refactor(learning-service): expose English routes and add characterization tests"
```

---

### Task 10: `commerce-service` — scaffold, Alembic e edu-common

**Files:**
- Create: `back-end/commerce-service/` (copiado)
- Delete: `back-end/commerce-service/app/security.py`
- Modify: `app/dependencies.py`, `app/config.py`, `app/events/publisher.py`
- Create: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/versions/*`
- Create: `tests/conftest.py`, `tests/test_health.py`

**Interfaces:**
- Consumes: `build_auth_deps`, `EventPublisher` de `edu-common`
- Produces: `app.dependencies` com `get_current_user`, `get_current_student_id`, `requer_papel`

- [ ] **Step 1: Copiar e criar o `pyproject.toml`**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp -r "/home/elias/Downloads/edu-project (2)/commerce-service" commerce-service
rm -f commerce-service/requirements.txt
```

Pela **Recipe A** com `<service>` = `commerce-service` e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "aio-pika>=9.4.2",
    "httpx>=0.28.0",
    "sentence-transformers>=3.1.1",
    "loguru>=0.7.2",
```

- [ ] **Step 2: Acrescentar `database_url_test` à config**

Em `back-end/commerce-service/app/config.py`, dentro de `Settings`:

```python
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/commerce_test"
```

- [ ] **Step 3: Trocar security, dependencies e publisher por edu-common**

```bash
rm /home/elias/programming/fiap/estuda_app/back-end/commerce-service/app/security.py
```

Substituir `back-end/commerce-service/app/dependencies.py` inteiro por:

```python
"""Dependências de auth do serviço — construídas a partir de edu-common."""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
get_current_student_id = _auth.get_current_user_id
requer_papel = _auth.require_role
```

Substituir `back-end/commerce-service/app/events/publisher.py` inteiro por:

```python
"""Publisher de eventos do serviço — instância única sobre edu-common."""

from edu_common.events import EventPublisher

from app.config import settings

_publisher = EventPublisher(settings.rabbitmq_url, settings.exchange_name)


async def init_publisher() -> None:
    await _publisher.connect()


async def publish_event(routing_key: str, payload: dict) -> None:
    await _publisher.publish(routing_key, payload)


async def close_publisher() -> None:
    await _publisher.close()
```

- [ ] **Step 4: Alinhar models e gerar a baseline do Alembic**

Trocar `DateTime` por `DateTime(timezone=True)` em `app/models/*.py` e conferir os índices contra `schema.sql`.

Seguir a **Recipe D**, com `<model imports>` na Recipe B =

```python
from app.models import ocorrencia as ocorrencia_models  # noqa: F401
from app.models import pedido as pedido_models  # noqa: F401
from app.models import produto as produto_models  # noqa: F401
```

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/commerce-service
uv sync
uv run alembic revision --autogenerate -m "baseline schema"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "sync check"
```

Expected: segundo autogenerate vazio.

```bash
rm alembic/versions/*sync_check*.py
rm schema.sql
```

Nota: os PKs seguem `Integer` nesta fase. A troca para UUID é da fase 2, junto com o resto da reconciliação de agregados — fazer agora exigiria migrar dados sem ainda ter o modelo final.

- [ ] **Step 5: Criar conftest e teste de fumaça**

`back-end/commerce-service/tests/conftest.py` pela **Recipe C**, com `<model imports>` =

```python
    from app.models import ocorrencia as ocorrencia_models  # noqa: F401
    from app.models import pedido as pedido_models  # noqa: F401
    from app.models import produto as produto_models  # noqa: F401
```

E a fixture de fake do encoder (o commerce usa embeddings em `substituicao_ia.py`), acrescentada ao final:

```python
@pytest.fixture(autouse=True)
def fake_encoder(monkeypatch):
    """Evita baixar o modelo de embeddings na suíte de substituição de produto."""
    import numpy as np

    class FakeEncoder:
        def encode(self, texts, **kwargs):
            if isinstance(texts, str):
                texts = [texts]
            vectors = [
                np.array([len(t) % 7, sum(map(ord, t)) % 11, len(t.split()) % 5], dtype=float)
                for t in texts
            ]
            return np.vstack(vectors)

    monkeypatch.setattr(
        "app.services.embeddings._carregar_modelo", lambda: FakeEncoder(), raising=False
    )
```

Confirmar o nome real antes de escrever:

```bash
grep -n "SentenceTransformer\|def .*model\|_modelo" app/services/embeddings.py app/services/substituicao_ia.py
```

`back-end/commerce-service/tests/test_health.py`:

```python
async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]
```

- [ ] **Step 6: Rodar e confirmar verde**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/commerce-service
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 7: Commit**

```bash
git add back-end/commerce-service
git commit -m "feat(commerce-service): import commerce-service on uv, alembic and edu-common"
```

---

### Task 11: `commerce-service` — rotas em inglês, paginação e schema explícito

**Files:**
- Modify: `app/routers/produtos.py`, `pedidos.py`, `separacao.py`, `entrega.py`, `ocorrencias.py`, `admin.py`
- Create: `app/schemas/produto.py`
- Test: `tests/test_products_routes.py`, `tests/test_orders_routes.py`, `tests/test_picking_routes.py`

**Interfaces:**
- Consumes: fixtures da task 10
- Produces: contrato público `/products`, `/orders`, `/picking`, `/delivery`, `/occurrences`, `/admin`; schema `ProductOut`

- [ ] **Step 1: Escrever os testes que falham**

`back-end/commerce-service/tests/test_products_routes.py`:

```python
from sqlalchemy import insert

from app.models.produto import Produto


async def _seed_products(db_session, quantity: int) -> None:
    await db_session.execute(
        insert(Produto),
        [
            {
                "nome": f"Livro {i}",
                "descricao": f"Descrição {i}",
                "preco": 49.90,
                "categoria": "livros",
                "imagem_url": "",
            }
            for i in range(quantity)
        ],
    )
    await db_session.commit()


async def test_products_are_listed_in_english_path(client):
    response = await client.get("/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_old_portuguese_path_is_gone(client):
    assert (await client.get("/produtos")).status_code == 404


async def test_products_listing_is_paginated(client, db_session):
    await _seed_products(db_session, 5)
    response = await client.get("/products?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_products_listing_rejects_limit_above_the_cap(client):
    assert (await client.get("/products?limit=5000")).status_code == 422


async def test_products_listing_has_a_default_limit(client, db_session):
    await _seed_products(db_session, 120)
    assert len((await client.get("/products")).json()) <= 100


async def test_product_response_exposes_only_declared_fields(client, db_session):
    await _seed_products(db_session, 1)
    product = (await client.get("/products")).json()[0]
    assert set(product) == {"id", "name", "description", "price", "category", "image_url"}


async def test_products_can_be_filtered_by_category(client, db_session):
    await _seed_products(db_session, 2)
    response = await client.get("/products?category=livros")
    assert response.status_code == 200
    assert all(p["category"] == "livros" for p in response.json())


async def test_unknown_category_returns_empty_list(client, db_session):
    await _seed_products(db_session, 2)
    assert (await client.get("/products?category=inexistente")).json() == []
```

`back-end/commerce-service/tests/test_orders_routes.py`:

```python
async def test_create_order_requires_authentication(client):
    response = await client.post("/orders", json={"itens": [], "endereco_entrega": "Rua X"})
    assert response.status_code == 403


async def test_my_orders_requires_authentication(client):
    assert (await client.get("/orders/mine")).status_code == 403


async def test_order_detail_requires_authentication(client):
    assert (await client.get("/orders/1")).status_code == 403


async def test_order_tracking_requires_authentication(client):
    assert (await client.get("/orders/1/tracking")).status_code == 403


async def test_delivery_estimate_requires_authentication(client):
    assert (await client.get("/orders/1/delivery-estimate")).status_code == 403


async def test_old_portuguese_order_path_is_gone(client):
    assert (await client.get("/pedidos/meus")).status_code == 404
```

`back-end/commerce-service/tests/test_picking_routes.py`:

```python
from edu_common.security import create_access_token

from app.config import settings


def headers_for(role: str) -> dict[str, str]:
    token = create_access_token("00000000-0000-0000-0000-000000000001", role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_picking_queue_requires_authentication(client):
    assert (await client.get("/picking/queue")).status_code == 403


async def test_picking_queue_forbids_students(client):
    assert (await client.get("/picking/queue", headers=headers_for("student"))).status_code == 403


async def test_picking_queue_allows_separador(client):
    assert (await client.get("/picking/queue", headers=headers_for("separador"))).status_code == 200


async def test_old_portuguese_picking_path_is_gone(client):
    assert (await client.get("/separacao/fila", headers=headers_for("separador"))).status_code == 404
```

- [ ] **Step 2: Rodar e confirmar que falham**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/commerce-service
uv run pytest tests/test_products_routes.py tests/test_orders_routes.py tests/test_picking_routes.py -v
```

Expected: FAIL — paths ainda em português, `/produtos` sem paginação e sem `response_model`.

- [ ] **Step 3: Criar o schema explícito de produto**

`back-end/commerce-service/app/schemas/produto.py`:

```python
"""Schema público de produto.

Campos declarados um a um de propósito: o model `Produto` pode ganhar colunas
internas (custo, margem, fornecedor preferencial) que não podem vazar para o
app só porque foram adicionadas ao banco.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(validation_alias="id")
    name: str = Field(validation_alias="nome")
    description: str | None = Field(default=None, validation_alias="descricao")
    price: Decimal = Field(validation_alias="preco")
    category: str | None = Field(default=None, validation_alias="categoria")
    image_url: str | None = Field(default=None, validation_alias="imagem_url")
```

- [ ] **Step 4: Reescrever o router de produtos**

Substituir `back-end/commerce-service/app/routers/produtos.py` inteiro por:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.produto import Produto
from app.schemas.produto import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def listar_produtos(
    category: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Catálogo público. Paginado por contrato — sem teto, um catálogo grande
    derruba o app e o serviço junto."""
    query = select(Produto)
    if category:
        query = query.where(Produto.categoria == category)
    query = query.order_by(Produto.id).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
```

- [ ] **Step 5: Traduzir os prefixos dos demais routers**

| Arquivo | Antes | Depois |
|---|---|---|
| `app/routers/pedidos.py` | `prefix="/pedidos"` | `prefix="/orders"` |
| `app/routers/pedidos.py` | `/pedidos/meus` | `/orders/mine` |
| `app/routers/pedidos.py` | `/pedidos/{id}/rastreio` | `/orders/{id}/tracking` |
| `app/routers/pedidos.py` | `/pedidos/{id}/previsao-entrega` | `/orders/{id}/delivery-estimate` |
| `app/routers/separacao.py` | `prefix="/separacao"` | `prefix="/picking"` |
| `app/routers/separacao.py` | `/separacao/fila` | `/picking/queue` |
| `app/routers/entrega.py` | `prefix="/entrega"` | `prefix="/delivery"` |
| `app/routers/ocorrencias.py` | `prefix="/ocorrencias"` | `prefix="/occurrences"` |

Confirmar os sub-paths reais antes de editar, e traduzir também os segmentos internos de cada um (ex: `/entrega/{id}/coletar` → `/delivery/{id}/collect`):

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/commerce-service
grep -rn "prefix=\|@router\." app/routers/
```

- [ ] **Step 6: Adicionar paginação às demais listagens**

Todo `@router.get("")` que devolve lista em `pedidos.py`, `separacao.py`, `ocorrencias.py` e `admin.py` recebe `limit: int = Query(50, ge=1, le=200)` e `offset: int = Query(0, ge=0)`, aplicados na query com `.limit(limit).offset(offset)`.

```bash
grep -rn "response_model=list" app/routers/
```

Expected: toda rota listada aqui tem `limit` e `offset` na assinatura.

- [ ] **Step 7: Rodar a suíte inteira**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/commerce-service
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 8: Commit**

```bash
git add back-end/commerce-service
git commit -m "refactor(commerce-service): expose English routes with pagination and explicit schemas"
```

---

### Task 12: `chatbot-service`

**Files:**
- Create: `back-end/chatbot-service/` (copiado)
- Modify: `app/dependencies.py`, `app/config.py`, `app/services/diagnostico_client.py`, `app/main.py`
- Create: `pyproject.toml`, `tests/conftest.py`, `tests/test_chat_routes.py`

**Interfaces:**
- Consumes: `build_auth_deps` de `edu-common`; `get_current_user` devolve `raw_token`, usado na chamada ao learning
- Produces: contrato `/chat/ask`, `/chat/explain-question`, `/support`

- [ ] **Step 1: Copiar e criar o `pyproject.toml`**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp -r "/home/elias/Downloads/edu-project (2)/chatbot-service" chatbot-service
rm -f chatbot-service/requirements.txt
mkdir -p chatbot-service/tests
```

Pela **Recipe A** com `<service>` = `chatbot-service`, sem o `per-file-ignores` de alembic, e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "groq>=0.11.0",
    "sentence-transformers>=3.1.1",
    "faiss-cpu>=1.9.0",
    "numpy>=1.26.4",
    "httpx>=0.28.0",
    "loguru>=0.7.2",
```

- [ ] **Step 2: Trocar `dependencies.py` por edu-common**

Substituir `back-end/chatbot-service/app/dependencies.py` inteiro por:

```python
"""Dependências de auth do serviço — construídas a partir de edu-common.

`get_current_student` devolve o payload do JWT já acrescido de `raw_token`,
porque `/chat/explain-question` repassa esse MESMO token na chamada ao
Learning Service (autenticação encadeada — o aluno só vê o contexto de
questões que ele mesmo respondeu).
"""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_student = _auth.get_current_user
```

O código antigo guardava o token em `payload["_token_bruto"]`. Trocar todos os usos para `raw_token`:

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/chatbot-service
grep -rn "_token_bruto" app/
```

Expected após a edição: nenhuma ocorrência.

- [ ] **Step 3: Apontar o cliente do learning para o path novo**

A task 9 renomeou `/diagnostico/questoes/{id}/contexto` para `/diagnostic/questions/{id}/context`. Em `back-end/chatbot-service/app/services/diagnostico_client.py`, atualizar a URL montada:

```bash
grep -n "diagnostico/questoes" app/services/diagnostico_client.py
```

Trocar para `/diagnostic/questions/{questao_id}/context`.

- [ ] **Step 4: Traduzir os paths públicos**

| Antes | Depois |
|---|---|
| `prefix="/chat"` | `prefix="/chat"` (já em inglês) |
| `/chat/explicar-questao` | `/chat/explain-question` |
| `/chat/perguntar` (confirmar nome real) | `/chat/ask` |

```bash
grep -rn "@app\.\|@router\.\|prefix=" app/main.py
```

- [ ] **Step 5: Escrever os testes**

`back-end/chatbot-service/tests/conftest.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def no_real_rag(monkeypatch):
    """O índice FAISS e o encoder não são carregados na suíte — os testes
    cobrem autenticação e contrato, não a qualidade da recuperação."""
    monkeypatch.setattr("app.rag.carregar_indice", lambda *a, **k: None, raising=False)
```

Confirmar o nome real da função de carga antes:

```bash
grep -n "def \|faiss" app/rag.py
```

`back-end/chatbot-service/tests/test_chat_routes.py`:

```python
from edu_common.security import create_access_token, create_refresh_token

from app.config import settings


def student_headers() -> dict[str, str]:
    token = create_access_token("00000000-0000-0000-0000-000000000001", "student", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_explain_question_requires_authentication(client):
    response = await client.post("/chat/explain-question", json={"questao_id": 5})
    assert response.status_code == 403


async def test_explain_question_rejects_invalid_token(client):
    response = await client.post(
        "/chat/explain-question",
        json={"questao_id": 5},
        headers={"Authorization": "Bearer lixo"},
    )
    assert response.status_code == 401


async def test_explain_question_rejects_a_refresh_token(client):
    token = create_refresh_token("user-1", "student", settings.jwt_secret)
    response = await client.post(
        "/chat/explain-question",
        json={"questao_id": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_explain_question_forwards_the_students_token_to_learning(client, monkeypatch):
    captured = {}

    async def fake_get_context(questao_id: int, token: str):
        captured.update(questao_id=questao_id, token=token)
        return {"enunciado": "?", "alternativas": [], "gabarito": "A", "resposta_aluno": "B"}

    monkeypatch.setattr(
        "app.services.diagnostico_client.buscar_contexto_questao", fake_get_context, raising=False
    )

    async def fake_explain(context: dict) -> str:
        return "explicação"

    monkeypatch.setattr(
        "app.services.explicacao_questao.gerar_explicacao", fake_explain, raising=False
    )

    await client.post("/chat/explain-question", json={"questao_id": 5}, headers=student_headers())
    assert captured["questao_id"] == 5
    assert captured["token"], "o token do aluno não foi repassado ao learning-service"


async def test_old_portuguese_path_is_gone(client):
    response = await client.post(
        "/chat/explicar-questao", json={"questao_id": 5}, headers=student_headers()
    )
    assert response.status_code == 404
```

Confirmar os nomes reais das funções antes de escrever os `monkeypatch`:

```bash
grep -n "^async def \|^def " app/services/diagnostico_client.py app/services/explicacao_questao.py
```

- [ ] **Step 6: Rodar e confirmar verde**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/chatbot-service
uv sync
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 7: Commit**

```bash
git add back-end/chatbot-service
git commit -m "feat(chatbot-service): import chatbot-service on uv and edu-common with English routes"
```

---

### Task 13: `notification-service`

**Files:**
- Create: `back-end/notification-service/` (copiado)
- Modify: `app/dependencies.py`, `app/config.py`, `app/events/consumer.py`, `app/routers/notificacoes.py`
- Create: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/versions/*`
- Create: `tests/conftest.py`, `tests/test_notifications_routes.py`, `tests/test_consumer.py`

**Interfaces:**
- Consumes: `build_auth_deps`, `EventConsumer` de `edu-common`
- Produces: contrato `/notifications`, `/notifications/{id}/read`, `/notifications/devices`

- [ ] **Step 1: Copiar e criar o `pyproject.toml`**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp -r "/home/elias/Downloads/edu-project (2)/notification-service" notification-service
rm -f notification-service/requirements.txt
```

Pela **Recipe A** com `<service>` = `notification-service` e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "aio-pika>=9.4.2",
    "loguru>=0.7.2",
```

- [ ] **Step 2: Acrescentar `database_url_test` à config**

Em `back-end/notification-service/app/config.py`, dentro de `Settings`:

```python
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/notification_test"
```

- [ ] **Step 3: Trocar `dependencies.py` por edu-common**

Substituir `back-end/notification-service/app/dependencies.py` inteiro por:

```python
"""Dependências de auth do serviço — construídas a partir de edu-common."""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
get_current_student_id = _auth.get_current_user_id
```

- [ ] **Step 4: Trocar o consumer pelo de edu-common**

Em `back-end/notification-service/app/events/consumer.py`, extrair a lista de bindings para constante de módulo e substituir `start_consumer`/`close_consumer`, preservando os handlers:

```python
from edu_common.events import EventConsumer

from app.config import settings

BINDINGS = [
    ("notification.revision_scheduled", "revision.scheduled", handle_revision_scheduled),
    ("notification.diagnostic_completed", "diagnostic.completed", handle_diagnostic_completed),
    ("notification.order_status_changed", "order.status_changed", handle_order_status_changed),
    ("notification.stock_issue", "order.stock_issue", handle_stock_issue),
    ("notification.delivery_delayed", "order.delivery_delayed", handle_delivery_delayed),
]

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def start_consumer() -> None:
    await _consumer.connect()
    for queue_name, routing_key, handler in BINDINGS:
        await _consumer.bind(queue_name, [routing_key], handler)


async def close_consumer() -> None:
    await _consumer.close()
```

- [ ] **Step 5: Gerar a baseline do Alembic**

Trocar `DateTime` por `DateTime(timezone=True)` nos models e seguir a **Recipe D**, com `<model imports>` na Recipe B =

```python
from app.models import device_token as device_token_models  # noqa: F401
from app.models import notificacao as notificacao_models  # noqa: F401
```

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/notification-service
uv sync
uv run alembic revision --autogenerate -m "baseline schema"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "sync check"
rm alembic/versions/*sync_check*.py
rm schema.sql
```

- [ ] **Step 6: Escrever os testes**

`back-end/notification-service/tests/conftest.py` pela **Recipe C**, com `<model imports>` =

```python
    from app.models import device_token as device_token_models  # noqa: F401
    from app.models import notificacao as notificacao_models  # noqa: F401
```

`back-end/notification-service/tests/test_notifications_routes.py`:

```python
from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.device_token import DeviceToken
from app.models.notificacao import Notificacao

STUDENT_ID = "00000000-0000-0000-0000-000000000001"
OTHER_ID = "00000000-0000-0000-0000-000000000002"


def headers_for(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, 'student', settings.jwt_secret)}"}


async def test_list_requires_authentication(client):
    assert (await client.get("/notifications")).status_code == 403


async def test_list_returns_only_own_notifications(client, db_session):
    db_session.add_all(
        [
            Notificacao(aluno_id=STUDENT_ID, titulo="Minha", descricao="d", tipo="estudo"),
            Notificacao(aluno_id=OTHER_ID, titulo="Do outro", descricao="d", tipo="estudo"),
        ]
    )
    await db_session.commit()

    body = (await client.get("/notifications", headers=headers_for(STUDENT_ID))).json()
    assert [n["titulo"] for n in body] == ["Minha"]


async def test_list_is_paginated(client, db_session):
    db_session.add_all(
        [
            Notificacao(aluno_id=STUDENT_ID, titulo=f"N{i}", descricao="d", tipo="estudo")
            for i in range(5)
        ]
    )
    await db_session.commit()
    body = (await client.get("/notifications?limit=2", headers=headers_for(STUDENT_ID))).json()
    assert len(body) == 2


async def test_cannot_mark_another_users_notification_as_read(client, db_session):
    notification = Notificacao(aluno_id=OTHER_ID, titulo="Do outro", descricao="d", tipo="estudo")
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)

    response = await client.patch(
        f"/notifications/{notification.id}/read", headers=headers_for(STUDENT_ID)
    )
    assert response.status_code == 404


async def test_register_device_stores_the_token(client, db_session):
    response = await client.post(
        "/notifications/devices",
        json={"token": "fcm-token-1", "platform": "android"},
        headers=headers_for(STUDENT_ID),
    )
    assert response.status_code == 201

    stored = (await db_session.execute(select(DeviceToken))).scalars().all()
    assert [t.token for t in stored] == ["fcm-token-1"]


async def test_register_device_is_idempotent(client, db_session):
    payload = {"token": "fcm-token-1", "platform": "android"}
    await client.post("/notifications/devices", json=payload, headers=headers_for(STUDENT_ID))
    await client.post("/notifications/devices", json=payload, headers=headers_for(STUDENT_ID))

    stored = (await db_session.execute(select(DeviceToken))).scalars().all()
    assert len(stored) == 1


async def test_unregister_device_only_removes_own_token(client, db_session):
    db_session.add(DeviceToken(aluno_id=OTHER_ID, token="alheio", platform="android"))
    await db_session.commit()

    await client.delete("/notifications/devices/alheio", headers=headers_for(STUDENT_ID))

    stored = (await db_session.execute(select(DeviceToken))).scalars().all()
    assert len(stored) == 1, "o token de outro usuário não pode ser apagado"


async def test_devices_require_authentication(client):
    response = await client.post(
        "/notifications/devices", json={"token": "x", "platform": "android"}
    )
    assert response.status_code == 403
```

`back-end/notification-service/tests/test_consumer.py`:

```python
import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from sqlalchemy import select

from app.events import consumer as consumer_module
from app.models.notificacao import Notificacao

STUDENT_ID = "00000000-0000-0000-0000-000000000001"


def fake_message(payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


async def test_diagnostic_completed_creates_a_notification(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_diagnostic_completed(
        fake_message({"aluno_id": STUDENT_ID, "acao": "avancar", "dominio": 0.9})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "estudo"
    assert "avançar" in stored[0].descricao


async def test_order_status_changed_creates_a_notification(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"aluno_id": STUDENT_ID, "pedido_id": 7, "status": "EM_TRANSITO"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 7
    assert "entrega" in stored[0].descricao.lower()


async def test_every_binding_points_to_a_real_handler():
    for queue_name, routing_key, handler in consumer_module.BINDINGS:
        assert queue_name and routing_key
        assert callable(handler)
```

- [ ] **Step 7: Adicionar paginação e conferir ownership**

`GET /notifications` recebe `limit: int = Query(50, ge=1, le=200)` e `offset: int = Query(0, ge=0)`. O `DELETE /notifications/devices/{token}` já filtra por `aluno_id` — o teste confirma; se falhar, acrescentar o filtro.

- [ ] **Step 8: Rodar e confirmar verde**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/notification-service
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 9: Commit**

```bash
git add back-end/notification-service
git commit -m "feat(notification-service): import notification-service on uv, alembic and edu-common"
```

---

### Task 14: `analytics-service`

**Files:**
- Create: `back-end/analytics-service/` (copiado)
- Modify: `app/dependencies.py`, `app/config.py`, `app/events/consumer.py`, `app/routers/analytics.py`
- Create: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/versions/*`
- Create: `tests/conftest.py`, `tests/test_analytics_routes.py`, `tests/test_anomalias.py`

**Interfaces:**
- Consumes: `build_auth_deps`, `EventConsumer` de `edu-common`
- Produces: contrato `/analytics/*`, todo ele restrito a `admin`

- [ ] **Step 1: Copiar e criar o `pyproject.toml`**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp -r "/home/elias/Downloads/edu-project (2)/analytics-service" analytics-service
rm -f analytics-service/requirements.txt
```

Pela **Recipe A** com `<service>` = `analytics-service` e `<deps>` =

```toml
    "fastapi>=0.115.0",
    "granian>=1.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "aio-pika>=9.4.2",
    "groq>=0.11.0",
    "loguru>=0.7.2",
```

- [ ] **Step 2: Acrescentar `database_url_test` à config**

```python
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/analytics_test"
```

- [ ] **Step 3: Trocar `dependencies.py` por edu-common**

Substituir `back-end/analytics-service/app/dependencies.py` inteiro por:

```python
"""Dependências de auth do serviço — construídas a partir de edu-common."""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
requer_papel = _auth.require_role
```

- [ ] **Step 4: Trocar o consumer pelo de edu-common**

Em `back-end/analytics-service/app/events/consumer.py`, substituir `start_consumer`/`close_consumer` preservando `ROUTING_KEYS` e `handle_event`:

```python
from edu_common.events import EventConsumer

from app.config import settings

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def start_consumer() -> None:
    await _consumer.connect()
    await _consumer.bind("analytics.event_log", ROUTING_KEYS, handle_event)


async def close_consumer() -> None:
    await _consumer.close()
```

- [ ] **Step 5: Gerar a baseline do Alembic**

Trocar `DateTime` por `DateTime(timezone=True)` no model e seguir a **Recipe D**, com `<model imports>` na Recipe B =

```python
from app.models import event_log as event_log_models  # noqa: F401
```

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/analytics-service
uv sync
uv run alembic revision --autogenerate -m "baseline schema"
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "sync check"
rm alembic/versions/*sync_check*.py
rm schema.sql
```

- [ ] **Step 6: Escrever os testes**

`back-end/analytics-service/tests/conftest.py` pela **Recipe C**, com `<model imports>` =

```python
    from app.models import event_log as event_log_models  # noqa: F401
```

`back-end/analytics-service/tests/test_analytics_routes.py`:

```python
import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.events import consumer as consumer_module
from app.models.event_log import EventLog


def headers_for(role: str) -> dict[str, str]:
    token = create_access_token("00000000-0000-0000-0000-000000000001", role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_analytics_requires_authentication(client):
    assert (await client.get("/analytics/anomalias")).status_code == 403


async def test_analytics_forbids_students(client):
    response = await client.get("/analytics/anomalias", headers=headers_for("student"))
    assert response.status_code == 403


async def test_analytics_allows_admin(client):
    response = await client.get("/analytics/anomalias", headers=headers_for("admin"))
    assert response.status_code == 200


async def test_every_analytics_route_is_admin_only(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    for path in paths:
        if not path.startswith("/analytics"):
            continue
        response = await client.get(path, headers=headers_for("student"))
        assert response.status_code in (403, 405), f"{path} não é admin-only"


def fake_message(routing_key: str, payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = routing_key

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


async def test_consumer_logs_the_raw_event(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_event(fake_message("order.created", {"pedido_id": 7}))

    stored = (await db_session.execute(select(EventLog))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "order.created"
    assert stored[0].payload == {"pedido_id": 7}
```

Antes de escrever o arquivo, ler o módulo para confirmar o nome e a assinatura da função de detecção — o teste abaixo assume `detectar_anomalias(contagens_por_dia: dict[str, list[int]], contagem_hoje: dict[str, int]) -> list[dict]`:

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/analytics-service
sed -n '1,80p' app/services/deteccao_anomalia.py
```

`back-end/analytics-service/tests/test_anomalias.py`:

```python
from app.services.deteccao_anomalia import MINIMO_DIAS_HISTORICO, detectar_anomalias


def test_threshold_is_explicit_and_conservative():
    assert MINIMO_DIAS_HISTORICO >= 5


def test_short_history_produces_no_anomaly():
    historico = {"order.created": [10] * (MINIMO_DIAS_HISTORICO - 1)}
    assert detectar_anomalias(historico, {"order.created": 900}) == []


def test_count_near_the_average_is_not_an_anomaly():
    historico = {"order.created": [10, 11, 9, 10, 12, 10, 11]}
    assert detectar_anomalias(historico, {"order.created": 10}) == []


def test_count_far_above_the_average_is_an_anomaly():
    historico = {"order.created": [10, 11, 9, 10, 12, 10, 11]}
    anomalias = detectar_anomalias(historico, {"order.created": 500})
    assert len(anomalias) == 1
    assert anomalias[0]["tipo"] == "order.created"


def test_count_far_below_the_average_is_an_anomaly():
    historico = {"order.created": [100, 110, 90, 105, 95, 100, 108]}
    assert detectar_anomalias(historico, {"order.created": 0}) != []


def test_event_type_without_history_is_skipped():
    historico = {"order.created": [10, 11, 9, 10, 12, 10, 11]}
    anomalias = detectar_anomalias(historico, {"order.created": 10, "order.stock_issue": 999})
    assert all(a["tipo"] != "order.stock_issue" for a in anomalias)


def test_zero_variance_history_does_not_divide_by_zero():
    historico = {"order.created": [10, 10, 10, 10, 10, 10, 10]}
    detectar_anomalias(historico, {"order.created": 10})
```

Se a assinatura real divergir, ajustar os testes a ela — o objetivo é congelar o comportamento atual. Se `test_zero_variance_history_does_not_divide_by_zero` levantar `ZeroDivisionError`, isso é um bug real: corrigir o serviço (desvio padrão zero significa "sem variação", logo sem anomalia) e manter o teste.

- [ ] **Step 7: Rodar e confirmar verde**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end/analytics-service
uv run pytest -v
uv run ruff check .
```

- [ ] **Step 8: Commit**

```bash
git add back-end/analytics-service
git commit -m "feat(analytics-service): import analytics-service on uv, alembic and edu-common"
```

---

### Task 15: `docker-compose` unificado, bancos e Makefile

**Files:**
- Create: `back-end/docker-compose.yml`
- Create: `back-end/.env.example`
- Create: `back-end/postgres/initdb.d/10-create-service-databases.sh`
- Create: `back-end/scripts/create-service-databases.sh`
- Modify: `Makefile`

**Interfaces:**
- Consumes: os 7 serviços das tasks 5-14, cada um já com seu `Dockerfile` escrito pela Recipe E
- Produces: `make stack-up` sobe legacy + stack novo; `make services-test` roda as 8 suítes

- [ ] **Step 0a: Restaurar os `server_default` perdidos no `auth-users-service`**

O `auth-users-service` foi importado antes de a Recipe D exigir a conferência de defaults, e sua baseline perdeu os `DEFAULT` de banco que o `schema.sql` declarava: `users.role`, `users.ativo`, `addresses.label`, `addresses.complement`, `addresses.is_favorite`, `password_reset_codes.usado`, e o `uuid_generate_v4()` dos `id`. Acrescentar `server_default` nesses models e gerar uma migration para eles (ali a baseline já foi aplicada em mais de um banco, então **não** amendar — empilhar uma migration nova).

Conferir também `learning-service`, importado no mesmo intervalo.

- [ ] **Step 0: Garantir que os sete serviços têm `.env.example`**

`api-gateway`, `auth-users-service` e `learning-service` foram importados antes desta constraint existir — provavelmente falta neles. Conferir os sete e escrever o que faltar:

```bash
cd back-end
for s in api-gateway auth-users-service learning-service commerce-service chatbot-service notification-service analytics-service; do
  test -f "$s/.env.example" && echo "$s ok" || echo "$s FALTA"
done
```

Cada um lista toda variável sem default em `app/config.py`, com valor de exemplo — nunca o valor real.

- [ ] **Step 1: Conferir que os sete Dockerfiles constroem**

Cada task de serviço já reescreveu o seu pela Recipe E — esta task só confirma que os sete constroem contra o contexto `back-end/`, que é o que o compose vai usar:

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
for s in api-gateway auth-users-service learning-service commerce-service chatbot-service notification-service analytics-service; do
  echo "→ $s"
  docker build -q -f "$s/Dockerfile" -t "edu-$s-test" . || exit 1
done
```

Expected: os sete constroem. Qualquer falha aqui é uma task de serviço que não cumpriu a Recipe E — corrigir o Dockerfile do serviço, não contornar no compose.

- [ ] **Step 2: Criar o script de criação dos bancos**

`back-end/postgres/initdb.d/10-create-service-databases.sh`:

```bash
#!/bin/bash
# Cria um banco por serviço, além do banco do legacy criado pelo POSTGRES_DB.
# Idempotente: rodar de novo num volume já inicializado não falha.
set -euo pipefail

DATABASES="auth_db learning_db commerce_db notification_db analytics_db"
DATABASES="$DATABASES auth_test learning_test commerce_test notification_test analytics_test"

for db in $DATABASES; do
  echo "Garantindo banco '$db'..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    SELECT 'CREATE DATABASE $db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done

echo "Bancos dos serviços prontos"
```

```bash
chmod +x /home/elias/programming/fiap/estuda_app/back-end/postgres/initdb.d/10-create-service-databases.sh
```

Copiar o mesmo script para `back-end/scripts/create-service-databases.sh` — `initdb.d` só roda em volume novo, e quem já tem o volume do legacy precisa rodar à mão.

- [ ] **Step 3: Escrever o `docker-compose.yml` unificado**

`back-end/docker-compose.yml` — a infra e o legacy vêm de `back-end/legacy/docker-compose.yml`, com `build.context` ajustado, mais os 7 serviços novos. Pontos obrigatórios:

- Um só `postgres` (imagem `postgres:17.4-alpine3.21`), com `./postgres/initdb.d` e `./legacy/postgres/initdb.d` montados em `/docker-entrypoint-initdb.d`.
- Um só `redis` (`redis:8.2.1-alpine`), um só `rabbitmq` (`rabbitmq:4.2.3-management-alpine`), um só `minio`.
- `api` e `worker` do legacy com `build.context: ./legacy` e porta host `${API_PORT_EXTERNAL:-8000}` — exatamente como o compose do legacy já faz. O Flutter não muda nesta fase.
- `api-gateway` com `build.context: .`, `dockerfile: api-gateway/Dockerfile`, porta host `${GATEWAY_PORT_EXTERNAL:-8100}`.
- Os 6 serviços com `build.context: .` e `dockerfile: <service>/Dockerfile`, portas host **8101-8106** (auth 8101, learning 8102, commerce 8103, chatbot 8104, notification 8105, analytics 8106). A faixa 80xx está ocupada — não usar.
- As URLs internas entre serviços (`AUTH_SERVICE_URL` etc.) usam o hostname do compose e a porta **8000 interna** do container, que não muda: `http://auth-users-service:8000`.
- Cada serviço com `DATABASE_URL` apontando para o seu banco no `postgres` compartilhado.
- Todos os serviços novos com o **mesmo** `JWT_SECRET`, vindo do `.env`.
- `depends_on` com `condition: service_healthy` em postgres e rabbitmq.

- [ ] **Step 4: Escrever o `.env.example`**

`back-end/.env.example` é a união das variáveis dos dois stacks. Copiar `back-end/legacy/.env.example` e acrescentar:

```bash
# ── Microserviços ─────────────────────────────────────────
# Mesmo segredo em todos os serviços novos: cada um valida o JWT sozinho.
JWT_SECRET=troque_por_uma_chave_secreta_grande
JWT_ALGORITHM=HS256

RABBITMQ_URL=amqp://edu:edu@rabbitmq:5672/
EXCHANGE_NAME=edu.events

# Origens liberadas no gateway (lista JSON — curinga é proibido).
CORS_ORIGINS=["http://localhost:3000"]

# APIs externas
GROQ_API_KEY=
GOOGLE_MAPS_API_KEY=

# Porta host do gateway. Os seis serviços ficam em 8101-8106, fixos no compose.
# A faixa 80xx é do legacy (API_PORT_EXTERNAL) e de outros projetos da máquina.
GATEWAY_PORT_EXTERNAL=8100
```

O `.env.example` é o contrato; o `back-end/.env` real **já existe e está em uso**. Este step só escreve o `.env.example`.

- [ ] **Step 5: Acrescentar os alvos do Makefile**

No `Makefile` da raiz, na seção Backend, acrescentar:

```makefile
SERVICES := packages/edu-common api-gateway auth-users-service learning-service commerce-service chatbot-service notification-service analytics-service

stack-up: ## Start the whole backend stack (legacy + microservices)
	cd back-end && $(COMPOSE) up -d

stack-down: ## Stop the whole backend stack
	cd back-end && $(COMPOSE) down

services-dbs: ## Create the per-service databases on an existing volume
	cd back-end && $(COMPOSE) exec -T postgres bash < scripts/create-service-databases.sh

services-migrate: ## Apply alembic migrations on every service that has a database
	@for s in auth-users-service learning-service commerce-service notification-service analytics-service; do \
		echo "→ $$s"; \
		cd back-end && $(COMPOSE) exec $$s uv run alembic upgrade head || exit 1; \
	done

services-test: ## Run every service test suite on the host
	@for s in $(SERVICES); do \
		echo "→ $$s"; \
		(cd back-end/$$s && uv run pytest -q) || exit 1; \
	done

services-lint: ## Run ruff across every service
	@for s in $(SERVICES); do \
		echo "→ $$s"; \
		(cd back-end/$$s && uv run ruff check .) || exit 1; \
	done

services-sync: ## Sync deps of every service on the host (for IDE support)
	@for s in $(SERVICES); do (cd back-end/$$s && uv sync) || exit 1; done
```

Acrescentar os nomes novos ao `.PHONY` da seção.

- [ ] **Step 6: Subir tudo e provar que os dois stacks convivem**

O `back-end/.env` já existe e está em uso — **acrescentar** as variáveis novas, nunca sobrescrever o arquivo:

```bash
cd /home/elias/programming/fiap/estuda_app
grep -q '^JWT_SECRET=' back-end/.env || {
  printf '\n# ── Microserviços ─────────────────────────────────────────\n' >> back-end/.env
  printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 32)" >> back-end/.env
  printf 'JWT_ALGORITHM=HS256\nRABBITMQ_URL=amqp://edu:edu@rabbitmq:5672/\nEXCHANGE_NAME=edu.events\n' >> back-end/.env
  printf 'CORS_ORIGINS=["http://localhost:3000"]\nGATEWAY_PORT_EXTERNAL=8100\nGROQ_API_KEY=\nGOOGLE_MAPS_API_KEY=\n' >> back-end/.env
}
make stack-up
sleep 40
make services-dbs
make services-migrate
```

Verificação — a porta do legacy vem do próprio `.env`, não é fixa:

```bash
API_PORT=$(sed -n 's/^API_PORT_EXTERNAL=//p' back-end/.env | tr -d '[:space:]')
curl -sf "http://localhost:${API_PORT:-8000}/health"   # legacy — o que o Flutter usa
curl -sf http://localhost:8100/health                  # gateway novo
for p in 8101 8102 8103 8104 8105 8106; do curl -sf "http://localhost:$p/openapi.json" >/dev/null && echo "$p ok"; done
curl -s http://localhost:8100/api/rota-inexistente | grep -q "Nenhum serviço mapeado" && echo "gateway 404 ok"
```

Expected: `{"status":"ok"}` nos dois healths, `ok` nas seis portas, e o 404 do gateway.

- [ ] **Step 7: Rodar todas as suítes**

```bash
cd /home/elias/programming/fiap/estuda_app
make services-test
make services-lint
make back-test
```

Expected: as 8 suítes novas verdes e a suíte do legacy verde.

- [ ] **Step 8: Commit**

```bash
git add back-end/docker-compose.yml back-end/.env.example back-end/postgres back-end/scripts Makefile back-end/*/Dockerfile
git commit -m "feat(infra): unify compose for legacy and microservices with per-service databases"
```

---

### Task 16: Documentação

**Files:**
- Create: `docs/back-end/microservices.md`
- Modify: `CLAUDE.md` (tabela de documentação)
- Modify: `docs/back-end/start-here.md` (aviso de que o monolito virou legacy)
- Modify: `README.md`
- Modify: `front-end-flutter/README.md` (referências a caminhos sob `back-end/`)
- Modify: `Makefile` (comentário obsoleto sobre a porta padrão 8000, ~linha 18)

**Interfaces:**
- Consumes: o estado final das tasks 1-15
- Produces: documentação que descreve o que existe, não o que se planeja

- [ ] **Step 1: Escrever `docs/back-end/microservices.md`**

Conteúdo obrigatório, todo verificado contra o código já mergeado:

1. Tabela de serviços, porta host e responsabilidade.
2. O mapa de rotas do gateway (`SERVICE_MAP`) em inglês, com a nota de que `products`, `orders`, `cart`, `payment-methods` e `support` ainda respondem 404 até a fase 2.
3. Como subir: `make stack-up`, `make services-dbs`, `make services-migrate`.
4. Como rodar testes: `make services-test`.
5. `edu-common`: o que vive lá e por quê (JWT e eventos), e por que `config.py`/`database.py` seguem duplicados.
6. Por que o legacy continua na porta que o `.env` já define (`API_PORT_EXTERNAL`, 8001 nesta máquina), o gateway na 8100 e os serviços em 8101-8106, e o que muda na fase 4.
7. Aviso: nenhum `.env` vai para o repositório; o `.env.example` é o contrato.

Boa parte do conteúdo pode ser adaptada do `README.md` da refatoração original — mas toda afirmação precisa ser conferida contra o código, porque o README original descreve o estado do zip, não o estado pós-migração.

- [ ] **Step 2: Registrar o doc na tabela do `CLAUDE.md`**

Na tabela de Documentacao, seção Backend, acrescentar a linha:

```markdown
| | [docs/back-end/microservices.md](docs/back-end/microservices.md) | Arquitetura de microservicos: gateway, servicos, edu-common, como subir e testar |
```

- [ ] **Step 3: Marcar o start-here como legacy**

No topo de `docs/back-end/start-here.md`, acrescentar:

```markdown
> **Nota:** este documento descreve o monolito modular, que vive em
> `back-end/legacy/` e continua servindo o app na porta definida por
> `API_PORT_EXTERNAL` no `back-end/.env`. A arquitetura
> de microserviços que vai substituí-lo está em
> [microservices.md](microservices.md). A migração está descrita em
> `docs/superpowers/specs/2026-08-02-microservices-migration-design.md`.
```

- [ ] **Step 4: Atualizar o README da raiz**

Na descrição da estrutura de pastas, refletir que `back-end/` agora contém os serviços e `back-end/legacy/`.

- [ ] **Step 5: Conferir que os comandos documentados funcionam**

```bash
cd /home/elias/programming/fiap/estuda_app
grep -oE 'make [a-z-]+' docs/back-end/microservices.md | sort -u
```

Para cada alvo listado, confirmar que existe:

```bash
make help | grep -E "up|services-"
```

- [ ] **Step 6: Commit**

```bash
git add docs CLAUDE.md README.md
git commit -m "docs(backend): document the microservices architecture and legacy status"
```

---

## Verificação final da fase 1

Rodar tudo e confirmar antes de declarar a fase pronta:

```bash
cd /home/elias/programming/fiap/estuda_app
make stack-up && sleep 40
make services-dbs && make services-migrate
make services-test && make services-lint
make back-test
API_PORT=$(sed -n 's/^API_PORT_EXTERNAL=//p' back-end/.env | tr -d '[:space:]')
curl -sf "http://localhost:${API_PORT:-8000}/health" && curl -sf http://localhost:8100/health
```

Critérios de aceite:

1. A suíte do legacy segue com 406 testes verdes (6 deselected, e2e) e o app continua servido na porta que o `.env` define.
2. Os 8 projetos novos (7 serviços + edu-common) têm suíte verde e ruff limpo.
3. Nenhum `print()` e nenhum `datetime.utcnow()` sobrou nos serviços importados.
4. Nenhum `.env` foi commitado; `git log --stat` não mostra nenhum arquivo `.env`.
5. Todo endpoint de listagem tem `limit` com teto, e nenhum devolve objeto ORM cru.
6. Em cada serviço com banco, `alembic revision --autogenerate` produz migration vazia.

```bash
grep -rn "print(\|utcnow" back-end/*/app/ | grep -v legacy
git log --stat | grep -E "^\s+back-end/.*\.env\b" || echo "OK: nenhum .env commitado"
```

---

## Notas de execução

**Sobre os testes de caracterização.** Vários testes deste plano assumem assinaturas (`calcular_proxima_revisao`, `decidir_acao`, `buscar_contexto_questao`) que precisam ser conferidas no código antes de escrever — os passos dizem onde olhar. Se o comportamento real divergir do que o teste espera, o teste é que se ajusta: o objetivo é congelar o que existe, não corrigir. Divergência que pareça bug de verdade vira nota para a fase 2, não correção silenciosa aqui.

**Sobre a task 15, step 1.** O empacotamento de `edu-common` dentro dos containers é o ponto mais provável de atrito do plano. A solução escolhida — reproduzir no container a mesma disposição relativa do repositório — é validada com um `docker build` isolado antes de replicar nos outros seis serviços. Se ela falhar, a alternativa é copiar `edu-common` para dentro da pasta do serviço no build e declarar um `[tool.uv.sources]` diferente para container e host.

**O que fica para a fase 2.** PKs UUID no commerce, o estado `CONFIRMADO`, snapshot de endereço e de produto, e os módulos `cart`, `payment-methods`, `products` com reviews, `orders`, `tracking` e `support` portados do legacy.
