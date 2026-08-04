# Start Here — Back-end Edu

> **Nota:** este documento descreve o monolito modular, que vive em
> `back-end/legacy/` e continua servindo o app na porta definida por
> `API_PORT_EXTERNAL` no `back-end/.env`. A arquitetura
> de microserviços que vai substituí-lo está em
> [microservices.md](microservices.md). A migração está descrita em
> `docs/superpowers/specs/2026-08-02-microservices-migration-design.md`.
>
> Os caminhos citados abaixo são relativos a `back-end/legacy/`: onde se lê
> `app/modules/...`, o caminho completo no repositório é
> `back-end/legacy/app/modules/...`.

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
back-end/legacy/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, monta routers, endpoint /health
│   ├── core/                   # infra compartilhada, sem regra de negócio
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # engine async, SessionLocal, Base, get_session
│   │   ├── celery_app.py       # instância Celery + autodiscover
│   │   └── logging.py          # configuração do loguru
│   ├── modules/                # UM SUBDIRETÓRIO POR DOMÍNIO
│   │   ├── auth/               # users, JWT, login/register/refresh, addresses
│   │   ├── products/           # catálogo + reviews
│   │   ├── cart/               # carrinho por usuário
│   │   ├── orders/             # pedidos (checkout a partir do carrinho)
│   │   ├── addresses/          # endereços (montado sob /auth/addresses)
│   │   ├── payment_methods/    # métodos de pagamento (dados mascarados)
│   │   ├── support/            # chat de suporte
│   │   └── notifications/      # device tokens + push (FCM)
│   ├── seeds/                  # seeds idempotentes (ex.: catálogo de produtos)
│   └── bff/                    # camada agregadora para o Flutter
│       └── router.py           # APIRouter com prefix=/bff
├── alembic/
│   ├── env.py                  # env async, importa Base.metadata
│   ├── script.py.mako
│   └── versions/               # revisões geradas
├── tests/
│   ├── conftest.py             # fixture `client` (httpx.AsyncClient + ASGITransport)
│   ├── modules/<dominio>/      # testes espelhando cada módulo
│   ├── seeds/                  # testes dos seeds
│   ├── e2e/                    # testes e2e contra a stack viva (opt-in)
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
   Isso inicia postgres, redis, rabbitmq, api, worker e o **MinIO** (object storage de dev — veja §5.1). O primeiro up faz o build da imagem (1–3 min).

3. **Confira o health**:
   ```bash
   curl http://localhost:8001/health
   # {"status":"ok"}
   ```

4. **(Opcional) Popule o catálogo de produtos**:
   ```bash
   make back-seed
   ```

5. **(Opcional) Sync de deps no host** para o IDE reconhecer os pacotes:
   ```bash
   make back-sync
   ```

### Endereços locais
> Portas externas vêm do `.env` (`API_PORT_EXTERNAL`, etc.). Os defaults do
> projeto expõem a API na **8001** (a 8000 é a porta interna do container).

| Serviço           | URL                        |
| ----------------- | -------------------------- |
| API               | http://localhost:8001      |
| API docs (Swagger)| http://localhost:8001/docs |
| RabbitMQ admin    | http://localhost:15673 (edu/edu) |
| Postgres          | localhost:5433 (edu/edu)   |
| Redis             | localhost:6380             |
| MinIO (S3 API)    | http://localhost:9000      |
| MinIO console     | http://localhost:9001 (edu/edu-secret) |

---

## 5.1 Object storage (R2 / MinIO)

As imagens de produto ficam em **object storage S3-compatível**, acessado pela API
via `aioboto3` (cliente em `app/core/storage.py`). O backend é agnóstico de
provedor — só o endpoint e as credenciais mudam entre ambientes:

| Ambiente | Backend | Como é configurado |
| --- | --- | --- |
| **Dev/test** | **MinIO** (sobe no compose, console em :9001) | Defaults do código já apontam para ele (`http://minio:9000`, bucket `edu-media`, `edu`/`edu-secret`). Nada a fazer. |
| **Prod** | **Cloudflare R2** | Defina as `R2_*` no ambiente/secrets (veja `.env.example`). |

Pontos importantes:

- **O bucket é privado.** A leitura acontece sempre por **presigned GET URL** com
  expiração (`MEDIA_PRESIGN_TTL_SECONDS`), memoizada no Redis. Nada de objeto público.
- **A escolha do backend é decidida só pelas env vars `R2_*`.** Se você definir as
  `R2_*` no seu `.env` apontando para o R2 real, o **dev passa a gravar no bucket de
  produção** — mesmo com o container MinIO de pé e ocioso. Para dev isolado, deixe as
  `R2_*` comentadas (como vem no `.env.example`) e use o MinIO.
- **Presigned URL e o device:** a URL é assinada com `R2_PUBLIC_ENDPOINT_URL` (ou
  `R2_ENDPOINT_URL` se não definido). Com MinIO em dev, o host `minio:9000` não é
  alcançável pelo celular/emulador — por isso o `make back-up` detecta o IP da LAN
  do host (o mesmo `HOST_IP` do `make front`) e injeta `R2_PUBLIC_ENDPOINT_URL` via
  docker-compose. Resultado: as imagens carregam no emulador, no simulador e em
  devices físicos sem nenhuma configuração manual (fallback para `10.0.2.2` quando
  o `HOST_IP` não é detectado). A chave de cache da presigned URL no Redis é
  scopeada pelo endpoint, então trocar de IP/rede gera URLs novas na hora — sem
  precisar de flush manual do cache.

Detalhes de design: `docs/superpowers/specs/2026-06-13-marketplace-product-photos-design.md`.

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
| `make back-seed`                | Popula o catálogo de produtos (idempotente)        |
| `make back-test-e2e`            | Roda os testes e2e contra a stack viva (opt-in)    |
| `make back-revision M="msg"`    | Gera nova revisão com autogenerate                 |
| `make back-sync`                | `uv sync` no host (para IDE)                       |

> ⚠️ **`make back-down` derruba a infra compartilhada.** O compose do legacy
> declara o mesmo projeto Docker (`edu`) e os mesmos `container_name` do
> Postgres, Redis, RabbitMQ e MinIO que os sete serviços novos usam. Rodar
> `back-down` para essa infra — mas **não** para os containers dos serviços
> novos, que não estão declarados naquele arquivo. Eles ficam de pé sem banco,
> sem broker e sem cache.
>
> Isso é inerente ao desenho de infra única, não é bug. Com o stack unificado
> no ar, use **`make stack-down`**; se derrubou sem querer, `make stack-up`
> traz tudo de volta. Veja [microservices.md](microservices.md) §11.

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
app.include_router(auth_router, prefix=settings.API_PREFIX)
```

Todos os routers de módulo são montados sob o prefixo global **`/api`**
(`settings.API_PREFIX`), fiel ao contrato original do cliente (o app Kotlin usava
base `/api/`). Um `APIRouter(prefix="/auth")` vira, na prática, `/api/auth/...`.
O `GET /health` é a única exceção — fica na raiz, sem `/api`, para sondas de infra.

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

O `celery_app.py` faz autodiscovery sozinho, desde que o arquivo se chame
`tasks.py`: ele **enumera os subpacotes** de `app/modules/` e passa cada um
(`app.modules.orders`, `app.modules.notifications`, …) para
`autodiscover_tasks`. Não use `autodiscover_tasks(["app.modules"])` — isso só
procura `app.modules.tasks` e **não registra nada** dos submódulos.

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

## 13. Catálogo de módulos e endpoints (estado atual)

Todas as rotas estão sob o prefixo **`/api`** e exigem `Authorization: Bearer
<access>` (exceto `register`/`login`/`refresh` e `GET /health`). Convenções de
JSON: **snake_case**; **valores monetários como string** (`"49.90"`); IDs são
**UUIDv7**.

### `auth` (`/api/auth`)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/register` | cria usuário, retorna `{user, tokens}` |
| POST | `/auth/login` | autentica (rate-limited), retorna `{user, tokens}` |
| POST | `/auth/refresh` | rotaciona o par de tokens |
| POST | `/auth/logout` | no-op no MVP (cliente descarta tokens) |
| GET | `/auth/me` | usuário atual |
| PATCH | `/auth/me` | edita perfil (`name`, `phone`, `birth_date`) |

Política de cadastro: senha ≥8 com caractere especial; `education_level` de uma
lista fixa; telefone normalizado para dígitos; `birth_date` aceita `DD/MM/YYYY`
ou ISO.

### `addresses` (`/api/auth/addresses`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/auth/addresses` | lista (favorito primeiro) |
| POST | `/auth/addresses` | cria; 1º endereço vira favorito |
| PATCH | `/auth/addresses/{id}` | atualização parcial |
| DELETE | `/auth/addresses/{id}` | remove (204) |

Invariante: **um único favorito por usuário** (garantido em transação).

### `products` (`/api/products`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/products?q&limit&offset` | lista paginada (`{items,total,limit,offset}`) |
| GET | `/products/categories` | contagem por `type` |
| GET | `/products/{id}` | detalhe |
| GET | `/products/{id}/reviews?limit&offset` | reviews + aggregates |
| POST | `/products/{id}/reviews` | cria review (autor = usuário atual) |

`rating_avg`/`rating_count` são **denormalizados** no produto e atualizados sob
**row-lock** ao criar review (read→write atômico).

### `cart` (`/api/cart`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/cart` | carrinho do usuário |
| POST | `/cart/items` | adiciona/incrementa item |
| DELETE | `/cart/items/{product_id}?quantity` | sem `quantity` remove o item; com `quantity` decrementa |

`total`/`subtotal` são **calculados no servidor** com preço vivo do catálogo.
Mutação de quantidade é serializada com lock na linha do carrinho.

### `orders` (`/api/orders`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/orders?limit&offset` | pedidos do usuário (desc) |
| POST | `/orders` | checkout: monta pedido do carrinho e **esvazia** numa transação com lock; body opcional `{payment_method:str}` |
| POST | `/orders/{id}/rebuy` | recompõe o carrinho a partir do pedido, retorna o `Cart` |

Itens do pedido **snapshotam** o preço pago (registro histórico imutável). Cada
pedido tem um campo **`status`** (`OrderStatus`: `pending → confirmed →
separating → out_for_delivery → delivered`), exposto no `OrderOut`. O checkout
cria o pedido como `pending` e dispara o **pipeline de status** (§16), que o faz
avançar sozinho disparando notificações a cada etapa.

### `payment_methods` (`/api/payment-methods`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/payment-methods` | lista (default primeiro) |
| POST | `/payment-methods` | cria; 1º vira default |
| PATCH | `/payment-methods/{id}` | define como default |
| DELETE | `/payment-methods/{id}` | remove; promove o próximo a default |

**PCI/LGPD:** armazena só dados **mascarados** (`card_last4`, `card_brand`,
`card_expiry` MMYY, `cardholder_name`, `pix_key`). Schema com `extra="forbid"`
**rejeita** PAN completo, CVV ou CPF. Invariante de um único default por usuário.

### `support` (`/api/support`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/support` | histórico de mensagens do usuário |
| POST | `/support` | envia mensagem, retorna a lista atualizada |

### `notifications` (`/api/notifications`)
Device tokens FCM + **histórico de notificações persistido**.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/notifications?limit&offset` | histórico do usuário (mais recente primeiro) |
| POST | `/notifications/devices` | registra o token FCM deste device (idempotente, reassina dono) |
| DELETE | `/notifications/devices/{token}` | remove o token (204) |

Toda notificação é **persistida sempre** (tabela `notifications_notifications`),
mesmo que o usuário não tenha device token ou que o push falhe — o histórico
in-app nunca fica incompleto. O fluxo de envio é `notify_user()` →
`create_notification()` (persiste) → `send_push_to_user()` (push best-effort via
`core/firebase.py`, que isola o Admin SDK e purga tokens inválidos). O Flutter lê
`GET /notifications` e o `data` carrega o payload de deep-link (ex.:
`{"type":"order_status","order_id":…,"status":…}`).

### `tracking` (`/api/orders`)
Superfície de **leitura/derivação** sobre pedidos: detalhe de rastreio, predição
de ETA e a rota do mapa. O rastreio lê o **status real do pedido**: carrega o
`Order` do dono (`OrderNotFound → 404`) e o `tracking/builders.py` deriva a linha
do tempo a partir do `OrderStatus` atual e dos `items` (kit). Só a geometria de
ETA/rota segue mockada até a integração de endereços.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/orders/{id}/tracking` | payload da tela de rastreio derivado do status real (etapas, localização, kit) |
| POST | `/orders/{id}/predict-eta` | estima o tempo restante a partir da posição do entregador (Haversine + fator urbano + trânsito) |
| GET | `/orders/{id}/route` | rota real por ruas origem→destino para o mapa embutido |

`/tracking` recebe o **UUID** do pedido (id não-UUID ou de outro usuário → 404,
indistinguível de inexistente). Os três endpoints exigem `Depends(get_current_user)`.

**`GET /orders/{id}/route`** (módulo de mapa do app):
- Chama a **Google Directions API** server-side via `httpx`
  (`tracking/directions.py`). A chave vem de `settings.GOOGLE_MAPS_API_PLATAFORM`
  (em `back-end/.env`) e **nunca** é logada nem enviada ao cliente — a chave do
  Maps SDK do app é outra, separada (regra de segurança #5).
- Resultado **cacheado no Redis** por pedido (`tracking:route:{order_id}`, TTL
  `TRACKING_ROUTE_CACHE_TTL_SECONDS`, default 6 h) — origem/destino são fixos por
  pedido, então a Directions só é paga na **primeira** abertura do mapa.
- Falha do provedor (fora do ar, cota, sem rota, chave ausente) vira
  `RouteUnavailable` → resposta **503** limpa (nunca 500, nunca vaza detalhe).
- Origem (Centro de Distribuição) e destino são **mockados** até a integração de
  pedidos/endereços fornecer coordenadas reais.

Config relacionada em `core/config.py`: `GOOGLE_MAPS_API_PLATAFORM`,
`TRACKING_ROUTE_CACHE_TTL_SECONDS`, `TRACKING_AVERAGE_SPEED_KMH`,
`TRACKING_URBAN_ROUTE_FACTOR`.

---

## 14. Seams de composição entre módulos (exceções documentadas)

A regra de ouro (§4) é "um módulo nunca importa de outro". No monolito atual há
**três pontos** onde isso é flexibilizado de forma consciente e comentada no
código — todos são candidatos a virar chamada HTTP/saga na extração:

1. **`cart.services` → `products`** — lê `Product` (batch select) para montar a
   view do carrinho com nome/preço/rating vivos.
2. **`orders.services` → `cart` + `products`** — o checkout precisa ler o
   carrinho, snapshotar o produto, criar o pedido e esvaziar o carrinho **numa
   única transação com lock**. A atomicidade (regra de segurança #3) prevalece
   sobre a pureza de módulo aqui.
3. **`orders.routes` (rebuy) → `cart.services`** — recompõe o carrinho a partir
   de um pedido, no nível da rota (mantém `orders.services` desacoplado de
   escrita no carrinho).

Pagamento no pedido é uma **string descritiva** (ex.: `"Visa ••••1234"`) enviada
no body de `POST /orders`; o cliente escolhe entre os `/payment-methods` salvos.

---

## 15. Seeds

`app/seeds/products.py` popula o catálogo (6 produtos + reviews de exemplo)
espelhando o mock do Flutter. É **idempotente** (chaveado por nome — rodar de
novo insere 0). Exposto como `seed_products(session)` (testável, em
`tests/seeds/`) e `main()` runnable:

```bash
make back-seed
# ou: docker compose exec api uv run python -m app.seeds.products
```

---

## 16. Pipeline de status de pedido + notificações

Cadeia de eventos assíncrona que avança o `status` de um pedido e notifica o
dono a cada etapa. É o caso de uso real de push do app — e o modelo de
referência para qualquer máquina de estados orientada a Celery aqui.

### 16.1 Máquina de estados (`orders/lifecycle.py`)
Progressão **forward-only**: `pending → confirmed → separating →
out_for_delivery → delivered`. `pending` é o estado transitório recém-criado;
`delivered` é terminal. Cada status (exceto `pending`) tem um texto pt-BR de
notificação. Helpers: `next_status()` e `can_advance_to(current, target)` (só o
sucessor imediato).

### 16.2 A task (`orders/tasks.py` → `orders.advance_order_status`)
1. O checkout (`create_order_from_cart`) cria o pedido como `pending` e
   enfileira `advance_order_status.delay(order_id, "confirmed")`.
2. A task move **um** passo via `services.advance_order_status()`:
   `SELECT ... FOR UPDATE` na linha do pedido, avança só se `can_advance_to`,
   `commit`, e então `notifications.notify_user()` (persiste + push).
3. Se avançou e o novo status não é terminal, **reagenda a si mesma** para o
   próximo passo com `apply_async(countdown=random(10..30))`.

**Atômica** (regra de segurança #3: row-lock + read→write→commit) e
**idempotente** (regra #10): um replay encontra o pedido já no/depois do
`to_status`, `can_advance_to` retorna `False`, a task é no-op e **não reagenda** —
a cadeia nunca bifurca nem notifica em dobro.

> **Demo:** os timers de 10–30s simulam o tempo de logística real. Em produção,
> as transições viriam de eventos do serviço de logística (webhook/mensageria),
> não de timers. Trocar a fonte do evento não muda a máquina de estados.

### 16.3 Config (`core/config.py`)
`ORDER_STATUS_MIN_DELAY_SECONDS` (10), `ORDER_STATUS_MAX_DELAY_SECONDS` (30),
`ORDER_STATUS_TASK_TIME_LIMIT` (30), `ORDER_STATUS_TASK_SOFT_TIME_LIMIT` (25).
Envio FCM: `FIREBASE_CREDENTIALS_PATH`, `FCM_SEND_TIME_LIMIT`,
`FCM_SEND_SOFT_TIME_LIMIT`.

### 16.4 Pré-requisito operacional
O **worker Celery precisa estar de pé** (`make back-up` já sobe; isoladamente
`docker compose up -d worker`) — sem ele o pedido fica em `pending`. Verifique as
tasks registradas com:

```bash
docker compose exec worker celery -A app.core.celery_app.celery_app inspect registered
# deve listar orders.advance_order_status e notifications.send_push_to_user
```

> **RabbitMQ:** o broker provisiona o usuário do `.env`
> (`RABBITMQ_USER`/`RABBITMQ_PASSWORD`) via `RABBITMQ_DEFAULT_USER/PASS` no
> compose, **apenas na primeira inicialização do volume** `rabbitmq_data`. Se o
> volume foi criado antes desse mapeamento existir, o worker leva
> `AccessRefused (403)`: recrie o volume (`docker compose down -v` em dev) ou
> crie o usuário à mão (`rabbitmqctl add_user … && set_permissions`).

---
