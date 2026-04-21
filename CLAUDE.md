# Edu - Estuda App

App educacional com Flutter (frontend) e Python + FastAPI (backend em microservicos com BFF).

## Tech Stack

### Frontend
- **Flutter** (Dart) — app mobile multiplataforma

### Backend
- **Python 3.12+** — linguagem principal
- **FastAPI** — framework web async
- **Granian** — ASGI server
- **SQLAlchemy 2.x** — ORM (async, estilo 2.0 com `select()`)
- **Alembic** — migrações de banco
- **PostgreSQL** — banco de dados principal
- **Celery** — tarefas assíncronas
- **RabbitMQ** — message broker para Celery
- **Redis** — cache, rate limiting e locks distribuídos

### Tooling
- **uv** — gerenciador de pacotes e virtualenvs (`uv sync`, `uv run`)
- **ruff** — linter e formatter (`ruff check`, `ruff format`)
- **pytest** — testes (`uv run pytest`)
- **Docker + Docker Compose** — ambientes dev e prod

## Arquitetura

- **BFF (Backend for Frontend)** — camada que agrega dados dos microservicos para o Flutter
- **Microservicos** — cada domínio é um servico isolado com seu próprio banco
- Comunicacao entre servicos via mensageria (RabbitMQ) ou HTTP interno
- Cada microservico tem: `routes/`, `services/`, `models/`, `schemas/`, `tasks/`

## Principios

### SOLID (Uncle Bob)
- **S** — cada módulo/classe tem uma única responsabilidade
- **O** — aberto para extensão, fechado para modificação
- **L** — subtipos devem ser substituíveis por seus tipos base
- **I** — interfaces pequenas e específicas, não interfaces gordas
- **D** — dependa de abstrações, não de implementações concretas

### KISS — Keep It Simple, Stupid
- Prefira a solução mais simples que funcione
- Não crie abstrações antes de precisar delas
- Três linhas repetidas são melhores que uma abstração prematura
- Se não precisa agora, não implemente (YAGNI)

### TDD — Test Driven Development (Extreme Programming)
- **Red** — escreva o teste que falha primeiro
- **Green** — escreva o mínimo de código para passar
- **Refactor** — limpe o código mantendo os testes verdes
- Testes antes de qualquer implementação. Sem exceção.
- Cobertura mínima de testes: toda lógica de negócio e todo endpoint

## Comandos Frequentes

```bash
# Dependências
uv sync

# Rodar testes
uv run pytest
uv run pytest -x                    # para no primeiro erro
uv run pytest --cov                 # com cobertura

# Lint e format
uv run ruff check .
uv run ruff format .

# Migrações
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "descricao"

# Docker
docker compose up -d                # subir ambiente
docker compose down                 # derrubar ambiente
docker compose logs -f <servico>    # logs
```

## Convenções de Código

### Python
- Formatação e lint via **ruff** — sem exceções
- Type hints em toda assinatura pública
- Docstrings só quando a lógica não é auto-evidente
- Logging com **loguru** (`from loguru import logger`), nunca `print()`
- Variáveis de ambiente via **pydantic-settings** (BaseSettings)
- Async por padrão em rotas e operações de I/O

### Flutter/Dart
- Seguir as convenções do `flutter analyze`
- Widgets pequenos e compostos — extrair quando passar de ~50 linhas
- Separar lógica de negócio da UI

### Testes
- Arquivos de teste espelham a estrutura do código: `services/foo.py` → `tests/test_foo.py`
- Fixtures em `conftest.py`
- Testes de integração com banco real (não mocks de banco)
- Usar `httpx.AsyncClient` para testar endpoints FastAPI

### Git
- Commits em inglês, curtos, no imperativo: `add user auth endpoint`
- Um commit por mudança lógica

---

## Security-First Development

Este projeto lida com dados sensíveis de estudantes. Segurança é requisito de primeira classe — todo código gerado ou modificado DEVE seguir estas regras.

### Regras Invioláveis

1. **Nunca concatenar input do usuário em SQL.** Sempre usar ORM (SQLAlchemy) com parâmetros bind ou queries parametrizadas.
   - **Proibido:** `.text(f"SELECT ...")`, `session.execute(f"...")`, SQL montado com f-string.
   - **Correto:** `session.execute(select(User).where(User.id == user_id))`

2. **Todo endpoint DEVE ter controle de acesso explícito.** Nenhuma rota pode existir sem `Depends(get_current_user)` ou equivalente. Validar ownership dos recursos — nunca consultar dados sem filtro de autorização.

3. **Operações em recursos compartilhados DEVEM ser atômicas.** Usar `session.begin()` + `with_for_update()` ou expressões SQL atômicas para qualquer read→write em saldos, contadores, quotas. Nunca `obj.value += x; session.commit()` sem lock.

4. **Inputs DEVEM ter limites.**
   - Campos de texto: `max_length` no model E no schema Pydantic.
   - Listagens: paginação obrigatória.
   - Uploads: limite de tamanho server-side.
   - Tasks Celery: sempre declarar `time_limit` e `soft_time_limit`.

5. **Nenhum segredo no código.** Tokens, senhas e API keys vão em variáveis de ambiente / `.env`. Nunca logar dados sensíveis (CPF, tokens, senhas) — nem em debug. Usar `loguru.logger`, nunca `print()`.

6. **Schemas com campos explícitos.** Proibido `model_config = {"from_attributes": True}` expondo todos os campos de modelos com dados sensíveis. Listar campos explicitamente nos schemas Pydantic.

7. **CSRF obrigatório** em qualquer operação que mude estado via browser. Exceções requerem justificativa documentada em comentário.

8. **Sem renderização insegura de HTML com dados do usuário.** Escapar todo output. Nunca inserir input do usuário em templates sem sanitização.

9. **Comparação de segredos em tempo constante.** Usar `hmac.compare_digest()` para comparar tokens, API keys e hashes. Nunca `==`. Proteger contra `None`: `if key and hmac.compare_digest(key, expected)`.

10. **Tasks Celery devem ser idempotentes e com lock.**
    - Tasks que mutam estado devem ser idempotentes.
    - Tasks concorrentes no mesmo recurso devem usar lock distribuído Redis com cleanup garantido em `finally`.
    - Toda task DEVE declarar `soft_time_limit` e `time_limit`.

11. **Rate limiting com primitivas atômicas.** Usar `cache.add()` (set-if-not-exists) para cooldowns, `cache.incr()` para contadores. Nunca read→modify→write (`cache.get()` + `cache.set()`).
