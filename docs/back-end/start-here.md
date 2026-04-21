# Start Here — Back-end Edu

Guia de onboarding do back-end do **Edu - Estuda App**. Leia inteiro antes de escrever código; a arquitetura tem uma restrição central (preparar para virar microserviços) que condiciona quase todas as decisões.

---

## 1. Visão geral

O back-end nasce como um **monolito modular** em FastAPI e vai ser fatiado em microserviços conforme o projeto amadurecer. Isso é um requisito do projeto, não uma opção. A estrutura de pastas, as regras de importação e a organização do banco foram todas pensadas para que a separação futura custe o mínimo possível.

Filosofia:
- Um processo hoje, vários processos amanhã — **sem reescrever** código de domínio.
- Cada módulo em `app/modules/` é um candidato natural a virar um serviço próprio.
- A camada **BFF** (`app/bff/`) é a única que compõe dados entre módulos; é ela que, no futuro, vira o único serviço que orquestra os demais.

---

## 2. Stack

| Camada               | Ferramenta                                    |
| -------------------- | --------------------------------------------- |
| Linguagem            | Python 3.12+                                  |
| Framework web        | FastAPI (async)                               |
| ASGI server          | Granian                                       |
| ORM                  | SQLAlchemy 2.x async (estilo 2.0 `select()`)  |
| Migrações            | Alembic (modo async)                          |
| Banco                | PostgreSQL                                    |
| Tarefas assíncronas  | Celery                                        |
| Message broker       | RabbitMQ                                      |
| Cache / locks / RL   | Redis                                         |
| Package manager      | uv                                            |
| Lint / format        | ruff                                          |
| Testes               | pytest + pytest-asyncio + httpx.AsyncClient   |
| Orquestração local   | Docker + Docker Compose                       |
| Logging              | loguru                                        |
| Config               | pydantic-settings (`BaseSettings`)            |

---

## 3. Estrutura de pastas

```
back-end/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, monta routers, endpoint /health
│   ├── core/                   # infra compartilhada, sem regra de negócio
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # engine async, SessionLocal, Base, get_session
│   │   ├── celery_app.py       # instância Celery + autodiscover
│   │   └── logging.py          # configuração do loguru
│   ├── modules/                # UM SUBDIRETÓRIO POR DOMÍNIO
│   │   └── __init__.py         # (vazio — os módulos entram aqui)
│   └── bff/                    # camada agregadora para o Flutter
│       └── router.py           # APIRouter com prefix=/bff
├── alembic/
│   ├── env.py                  # env async, importa Base.metadata
│   ├── script.py.mako
│   └── versions/               # revisões geradas
├── tests/
│   ├── conftest.py             # fixture `client` (httpx.AsyncClient + ASGITransport)
│   └── test_health.py
├── pyproject.toml              # deps + ruff + pytest config
├── alembic.ini
├── Dockerfile
├── docker-compose.yml          # postgres, redis, rabbitmq, api, worker
├── .dockerignore
├── .env.example
└── .gitignore
```

### O papel de cada camada

#### `app/core/`
Só infra **genérica**. Config, engine do banco, app do Celery, logging. Nada aqui pode conhecer um domínio específico. Quando um módulo for extraído para ficar em um serviço próprio, ele leva uma **cópia** dessas primitivas — não há acoplamento de domínio pra cortar.

#### `app/modules/<dominio>/`
O coração do monolito modular. Cada módulo é **autocontido**, com a forma canônica:

```
app/modules/<dominio>/
├── __init__.py
├── models.py       # SQLAlchemy (tabelas deste domínio, com prefixo próprio)
├── schemas.py      # Pydantic (request/response)
├── services.py     # regra de negócio, usa SessionLocal
├── routes.py       # APIRouter deste domínio
└── tasks.py        # tasks Celery deste domínio (opcional)
```

**Regra de ouro:** `app/modules/A` **nunca** importa de `app/modules/B`. Se dois domínios precisam conversar, use uma das duas saídas:
1. **Síncrono** — chamar a API do outro via HTTP (`httpx.AsyncClient`). Hoje bate em `localhost`; amanhã em outro host.
2. **Assíncrono** — publicar/consumir mensagens via RabbitMQ (task Celery).

Esses dois contratos sobrevivem intactos à separação em microserviços. Qualquer `from app.modules.X import ...` feito a partir de outro módulo cria dívida que vai ter que ser paga na hora do split.

#### `app/bff/`
Única camada autorizada a compor dados de **múltiplos** módulos em uma mesma resposta — porque é exatamente isso que o Flutter precisa. Quando os módulos virarem serviços, o BFF vira um serviço separado que fala HTTP com cada um. Até lá, chama as services diretamente.

#### `alembic/`
Um único histórico de migrações por enquanto. Quando um módulo for extraído, ele leva as tabelas dele (com o prefixo `<dominio>_`) para o próprio repositório/serviço, com seu próprio histórico Alembic.

---

## 4. Estratégia de extração para microserviços

É o motivo de todas as escolhas acima. Pense nisso sempre antes de codar.

### 4.1 Isolamento de tabelas
Cada módulo prefixa **todas** as tabelas com o nome do domínio:

```python
# app/modules/auth/models.py
class User(Base):
    __tablename__ = "auth_users"
```

Nada de `users` solto. Assim, quando o módulo auth virar um serviço, basta dumpar `auth_*` e importar no banco dele.

### 4.2 Sem FK entre módulos
Foreign keys cruzando domínios amarram o split. Se o módulo `progress` precisa referenciar um `auth_users.id`, guarde só o UUID como coluna — **sem** `ForeignKey`. Valide via chamada ao módulo dono.

### 4.3 Comunicação entre módulos
- **Leitura síncrona** → HTTP (via `httpx`), mesmo que hoje seja chamada de função local. Criar uma fachada fina ajuda: `auth_client.get_user(id)` que hoje chama a service interna e amanhã faz HTTP.
- **Eventos** → publicar em RabbitMQ (`celery_app.send_task("modulo.task_name", ...)`). O consumidor resolve. Desacoplado por natureza.

### 4.4 Config por módulo
Se um módulo precisa de uma configuração própria (ex.: chave de API externa), adicione em `core/config.py` com prefixo: `AUTH_PROVIDER_KEY`, `PROGRESS_QUEUE`. Na hora do split, o módulo leva só o que tem o prefixo dele.

### 4.5 BFF como antecipação
Sempre que o Flutter precisar de dados de **mais de um** módulo, a rota vai em `app/bff/`. Evita que módulos se conheçam para "ajudar" a UI.

---

## 5. Setup inicial

### Pré-requisitos
- Docker e Docker Compose instalados.
- `make` (opcional, mas os atalhos assumem que existe).
- `uv` no host (opcional — usado só para sync local para suporte do IDE).

### Passos

1. **Copie o env**:
   ```bash
   cp back-end/.env.example back-end/.env
   ```
   Ajuste `SECRET_KEY` e, se quiser, credenciais do Postgres/RabbitMQ. Os defaults funcionam para dev local.

2. **Suba a stack**:
   ```bash
   make back-up
   ```
   Isso inicia postgres, redis, rabbitmq, api e worker. O primeiro up faz o build da imagem (1–3 min).

3. **Confira o health**:
   ```bash
   curl http://localhost:8000/health
   # {"status":"ok"}
   ```

4. **(Opcional) Sync de deps no host** para o IDE reconhecer os pacotes:
   ```bash
   make back-sync
   ```

### Endereços locais
| Serviço           | URL                        |
| ----------------- | -------------------------- |
| API               | http://localhost:8000      |
| API docs (Swagger)| http://localhost:8000/docs |
| RabbitMQ admin    | http://localhost:15672 (edu/edu) |
| Postgres          | localhost:5432 (edu/edu)   |
| Redis             | localhost:6379             |

---

## 6. Comandos do dia a dia

Todos a partir da raiz do repo.

| Comando                         | O que faz                                          |
| ------------------------------- | -------------------------------------------------- |
| `make back-up`                  | Sobe toda a stack em background                    |
| `make back-down`                | Derruba a stack                                    |
| `make back-logs`                | Tail dos logs da API                               |
| `make back-logs SVC=worker`     | Tail dos logs do worker Celery                     |
| `make back-sh`                  | Shell bash dentro do container da API              |
| `make back-test`                | Roda pytest dentro do container                    |
| `make back-lint`                | `ruff check .`                                     |
| `make back-format`              | `ruff format .`                                    |
| `make back-migrate`             | `alembic upgrade head`                             |
| `make back-revision M="msg"`    | Gera nova revisão com autogenerate                 |
| `make back-sync`                | `uv sync` no host (para IDE)                       |

---

## 7. Criando um novo módulo (receita canônica)

Siga TDD — teste primeiro, sempre. Exemplo com um módulo `auth`.

### 7.1 Estrutura de teste primeiro

```
tests/modules/auth/
├── __init__.py
├── conftest.py     # fixtures específicas do módulo (se houver)
└── test_routes.py  # ou test_services.py
```

Escreva o teste que falha **antes** de qualquer arquivo em `app/modules/auth/`.

### 7.2 Código do módulo

```
app/modules/auth/
├── __init__.py
├── models.py       # tabelas com prefixo auth_
├── schemas.py      # Pydantic com campos explícitos (ver Segurança §8)
├── services.py     # regra de negócio async
└── routes.py       # APIRouter(prefix="/auth", tags=["auth"])
```

### 7.3 Registrar o router em `app/main.py`

```python
from app.modules.auth.routes import router as auth_router
app.include_router(auth_router)
```

Não existe "auto-discovery" de routers aqui de propósito: o registro explícito força o autor a lembrar que aquele módulo vai virar serviço um dia.

### 7.4 Registrar os models no Alembic

Em `alembic/env.py`, adicione o import para o autogenerate enxergar:

```python
from app.modules.auth import models  # noqa: F401
```

### 7.5 Gerar a migração

```bash
make back-revision M="add auth tables"
make back-migrate
```

### 7.6 Tasks Celery (se houver)

Em `app/modules/auth/tasks.py`:

```python
from app.core.celery_app import celery_app

@celery_app.task(name="auth.send_welcome_email", time_limit=60, soft_time_limit=45)
def send_welcome_email(user_id: str) -> None:
    ...
```

O `autodiscover_tasks(["app.modules"])` do `celery_app.py` acha sozinho, desde que o arquivo se chame `tasks.py`.

---

## 8. Segurança — regras invioláveis

Extraídas do `CLAUDE.md`. **Toda** review passa por isso.

1. **Nunca concatenar input em SQL.** Sempre ORM com parâmetros bind.
2. **Todo endpoint tem `Depends(get_current_user)`** (ou equivalente). Autorização por ownership explícita.
3. **Read→write em recurso compartilhado é atômico.** `session.begin()` + `with_for_update()` ou expressão SQL atômica. Nunca `obj.value += x; commit()`.
4. **Limites em todos os inputs.** `max_length` no model e no schema. Paginação obrigatória. Uploads com limite server-side. Tasks Celery com `time_limit` + `soft_time_limit`.
5. **Zero segredos no código.** Tudo via `.env`. Nunca logar CPF, senha, token — mesmo em debug. `logger` do loguru, nunca `print`.
6. **Schemas com campos explícitos.** Proibido `from_attributes=True` expondo tudo. Liste cada campo.
7. **CSRF obrigatório** em operações que mudam estado via browser.
8. **Escapar HTML** com dados do usuário. Sem renderização insegura.
9. **Comparação de segredos com `hmac.compare_digest`** — nunca `==`. Proteger contra `None`.
10. **Tasks Celery idempotentes** + lock Redis em recurso compartilhado, com cleanup em `finally`.
11. **Rate limiting com primitivas atômicas** — `cache.add()` para set-if-not-exists, `cache.incr()` para contadores. Nunca read→modify→write.

---

## 9. Testes

### Filosofia — TDD (XP)
1. **Red** — escreva o teste que falha.
2. **Green** — mínimo de código para passar.
3. **Refactor** — limpe com testes verdes.

Sem exceção. Testes antes de qualquer implementação.

### Convenções
- Arquivos espelham a estrutura: `app/modules/auth/services.py` → `tests/modules/auth/test_services.py`.
- Fixtures compartilhadas em `conftest.py` no nível apropriado.
- Integração com **banco real** (não mock). Mock de banco esconde regressão de migração.
- Endpoints testados com `httpx.AsyncClient` — fixture `client` já existe em `tests/conftest.py`.

### Rodar
```bash
make back-test                          # tudo
docker compose exec api uv run pytest -x            # para no primeiro erro
docker compose exec api uv run pytest --cov         # com coverage
docker compose exec api uv run pytest tests/modules/auth/  # só um módulo
```

---

## 10. Migrações (Alembic async)

O `env.py` já está configurado em modo async e puxa a URL do `settings.DATABASE_URL`. Para que o autogenerate detecte novas tabelas, **todo** módulo novo precisa ter seus `models` importados em `alembic/env.py`.

Fluxo típico:

```bash
# 1. crie/modifique models em app/modules/<dominio>/models.py
# 2. garanta o import em alembic/env.py
make back-revision M="add user preferences table"
# 3. revise o arquivo gerado em alembic/versions/
make back-migrate
```

**Nunca** edite uma revisão já aplicada em ambiente compartilhado. Se errou, crie uma nova revisão corrigindo.

---

## 11. Convenções de código

### Python
- Formatação **obrigatória** via `ruff format` (linha 100).
- Lint via `ruff check` com regras `E, F, I, N, UP, B, A, C4, SIM, RUF, ASYNC, S` (ver `pyproject.toml`).
- Type hints em **toda** assinatura pública.
- Docstring só quando a lógica não é auto-evidente. Nome bem escolhido > comentário.
- Async por padrão em rotas e I/O.
- Logging com `from loguru import logger` — nunca `print()`.
- Config via `pydantic-settings` — nunca `os.getenv()` direto.

---

## 12. Checklist antes de abrir PR

- [ ] Testes escritos **antes** do código.
- [ ] `make back-test` passa.
- [ ] `make back-lint` sem warnings.
- [ ] `make back-format` rodado.
- [ ] Nenhum `from app.modules.X` em outro módulo.
- [ ] Tabelas novas têm prefixo `<dominio>_`.
- [ ] Nenhuma FK cruzando módulos.
- [ ] Endpoints com `Depends(get_current_user)`.
- [ ] Schemas Pydantic com campos explícitos.
- [ ] Tasks Celery com `time_limit` e `soft_time_limit`.
- [ ] Nenhum `print`, nenhum segredo em log, nenhum `==` comparando segredo.
- [ ] Alembic: models importados em `env.py`, revisão gerada e revisada.

---
