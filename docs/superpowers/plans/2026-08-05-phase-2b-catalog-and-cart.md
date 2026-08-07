# Fase 2 — Bloco B: catálogo, reviews, carrinho e formas de pagamento

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

---

## AVISO DE PROCEDÊNCIA — leia antes de qualquer task

Este plano inteiro foi escrito **antes de qualquer execução**, igual ao do bloco A.

**Todo `Expected:` deste documento é previsão NÃO MEDIDA.** O mesmo vale para
todo bloco "Esperado:", toda contagem de linhas, todo nome de constraint, todo
nome de arquivo do legacy e toda justificativa causal. Nada disso foi observado
rodando; foi deduzido por leitura.

O bloco A mediu o custo dessa distinção: **os diagnósticos se sustentaram quase
todos, mas as previsões e as justificativas erraram sistematicamente.** Quinze
defeitos de plano só apareceram executando, e quinze afirmações factuais falsas
foram escritas em comentário, docstring e mensagem de commit — nenhuma pega por
teste, porque todas passavam verdes. Todas pegas por alguém medir.

### As três regras que valem em cima de todo `Expected:`

1. **Rode o teste ANTES do fix e confirme que ele falha pelo motivo certo.**
   Um Red que falha por outra razão (import errado, 404 que a asserção não
   distingue) não é Red — é um teste que você ainda não sabe se funciona.

2. **Toda afirmação factual precisa do comando que a produziu.** Se você não
   mediu, não escreva — nem em comentário, nem em docstring, nem em mensagem de
   commit, nem em relatório. Afirmação **auto-referencial** ("este grep acha só
   esta linha", "esta é a única ocorrência", "o arquivo tem N linhas") tem que
   ser **re-medida DEPOIS da edição**: foi exatamente assim que uma delas virou
   falsa no bloco A.

3. **Quando o plano e a medição discordam, a medição decide.** Não force a
   realidade a caber no `Expected:`. Divergência medida vira linha no relatório
   da task — é ela que a fase 4 vai ler, não o plano.

### Erratas já medidas contra este plano (medidas em 2026-08-07, antes da task B0)

Correções ao texto abaixo. Onde a errata contradiz o corpo do plano, **a errata
governa**:

- **Proibição absoluta:** nenhum `docker compose up/down/restart/build`, nenhum
  `make stack-up`, nenhum `make services-migrate`, e **nenhum
  `alembic upgrade head` contra banco real**. O stack do usuário está no ar,
  construído do checkout principal, e o compose usa o mesmo
  `COMPOSE_PROJECT_NAME` — subir substituiria os containers dele. Todo passo
  deste plano que manda `docker compose exec <svc> uv run alembic ...` vira, em
  vez disso, banco descartável no host:

  ```bash
  docker exec -i edu-postgres psql -U edu -d postgres -c 'CREATE DATABASE syncchk_commerce;'
  cd back-end/commerce-service
  DATABASE_URL='postgresql+asyncpg://edu:<senha>@localhost:5433/syncchk_commerce' uv run alembic upgrade head
  DATABASE_URL='postgresql+asyncpg://edu:<senha>@localhost:5433/syncchk_commerce' uv run alembic revision --autogenerate -m "sync check"
  # inspecionar a revision gerada, apagá-la
  docker exec -i edu-postgres psql -U edu -d postgres -c 'DROP DATABASE syncchk_commerce;'
  ```

  O container do Postgres chama-se **`edu-postgres`**, não `postgres`. Leitura
  (`SELECT count(*)`) contra `commerce_db` é permitida — é só leitura.

- **O `Makefile` fica na RAIZ do repositório**, não em `back-end/`. `make
  services-test` e `make services-lint` rodam no host, sem compose — são
  permitidos.

- **Lockfiles:** `uv run pytest` reescreve o `uv.lock` de analytics, auth-users
  e chatbot; `make services-lint` reescreve o dos seis que dependem do
  `edu-common`. Rode `git status` depois de todo teste/lint e **reverta só os
  lockfiles** que você não mudou de propósito.

- **Baseline medido neste worktree em 2026-08-07** (`make services-test`, saída
  0): 402 testes na frota — edu-common 59, api-gateway 36, auth-users 61,
  learning 78, **commerce 88**, chatbot 23, notification 24, analytics 33.
  Nenhum número pode diminuir.

- **A dependência de usuário autenticado tem DOIS nomes**, medido em
  `commerce-service/app/dependencies.py`: `get_current_user` devolve `dict`
  (com a chave `raw_token`, confirmada em
  `packages/edu-common/src/edu_common/deps.py`), e `get_current_user_id`
  devolve `str`. O plano usa `get_current_user` e `user["raw_token"]` — os dois
  existem.

- **Redis de teste: `fakeredis`, não o Redis real.** Decisão do usuário em
  2026-08-07. A fixture do conftest (task B2/Step 6) usa `fakeredis.aioredis`,
  não `settings.redis_url_test` — o `edu-redis` no ar é o do usuário, e
  `flushdb` numa instância viva não é do escopo deste bloco. `redis_url_test`
  continua declarada em config, sem consumidor na suíte. Registre a divergência
  no relatório da B2.

- **`/payment-methods` e `/cart` seguem SEM paginação.** Decisão do usuário em
  2026-08-07: entre a constraint 18 deste plano (réplica exata) e a regra 4 do
  `CLAUDE.md` (listagem paginada obrigatória), **o plano governa**. Registre a
  divergência no relatório da B9 e no portão B11 para o revisor final não a
  confundir com esquecimento.

- **O app Flutter fala DIRETO com o monolito legado na porta 8001**, não com o
  `api-gateway`. Nenhum cliente chega ao `SERVICE_MAP`. Consequência para toda
  afirmação de contrato deste plano: mudança só no gateway não quebra o app, e
  conserto só no gateway não o ajuda. Medido: `api-gateway/app/routing.py`
  mapeia `products`, `cart` e `payment-methods` para `commerce` — as duas
  últimas são as lacunas que este bloco fecha.

- **Ambiente medido em 2026-08-07:** estão no ar `edu-postgres` (5433),
  `edu-redis` (6380), `edu-rabbitmq` e os sete microserviços (8100–8106).
  **NÃO** estão no ar o `minio` nem o `api` legado (8001), e a porta 9000 do
  host está ocupada por `maquina-minio-1`, de outro projeto. Passos que exigem
  MinIO (B2/Step 7, B10/Step 5) precisam de provisionamento próprio, autorizado
  pelo usuário — container novo, nome próprio, porta livre, **nunca** via
  compose.

---

**Goal:** Fazer o `commerce-service` servir `/products`, `/cart` e `/payment-methods` byte a byte como o legacy os serve hoje, para que a fase 4 seja uma troca de `API_BASE_URL` e não uma reconciliação.

**Architecture:** O agregado `produtos` vira `products` — tabela, colunas e PK UUID — porque é o primeiro agregado do commerce a ganhar cliente. `reviews`, `carts`, `cart_items` e `payment_methods` são portados inteiros do legacy: não existem no commerce. `image_url` guarda **chave de objeto**, não URL; a serialização a transforma em URL presignada memoizada no Redis. Nada aqui toca pedido — isso é o bloco C.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, pytest, ruff, uv, PostgreSQL, Redis, MinIO (S3 via aioboto3), RabbitMQ.

**Spec:** [`docs/superpowers/specs/2026-08-04-microservices-migration-phase-2-design.md`](../specs/2026-08-04-microservices-migration-phase-2-design.md) — bloco B.
**Depende de:** [bloco A](2026-08-05-phase-2a-security-and-fleet.md) concluído. Em especial a task 19 (`get_current_user_id` é o nome canônico) e a task 16 (`httpx` saiu do runtime do commerce — a task B7 o devolve).

---

## Global Constraints

Valem em **todas** as tasks. Idênticas às do bloco A; repetidas aqui porque cada plano é executado em sessão própria.

**Do `CLAUDE.md`:**

1. Nunca concatenar input do usuário em SQL — sempre ORM com bind params. `ilike(f"%{q}%")` com `q` **como parâmetro bound** é permitido e é o que o legacy faz; `text(f"... {q} ...")` não.
2. Todo endpoint com controle de acesso explícito **e** filtro de ownership.
3. Read→write em recurso compartilhado é atômico: `with_for_update()` ou expressão SQL atômica.
4. Todo input com limite: `max_length` no model **e** no schema; listagem paginada; upload com teto server-side.
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
15. **`default=` do SQLAlchemy é client-side** — use `server_default=` junto onde o legacy tem DEFAULT no banco.
16. **Comentário que era verdade e virou mentira** — releia o arquivo inteiro ao mudar comportamento.
17. **`docker ps` reporta saudável container que não serve** — `docker compose restart` antes de acreditar num health check.

**Constraints próprias deste bloco:**

18. **Réplica exata é o critério, e ele é binário.** Toda task de rota começa **portando o arquivo de teste do legacy**. O teste portado é o Red. Se ele passar de primeira, você portou errado (provavelmente esqueceu de tirar o `/api` e está batendo em 404 que o `assert` não distingue).
19. **Reproduzir as inconsistências é o trabalho, não um bug.** `/products` e `/cart` devolvem envelope; `/payment-methods` devolve array puro; dinheiro é string. Não "arrume" nada disso.
20. **Nunca mude uma asserção portada sem registrar por quê.** Cada asserção alterada vira uma linha no relatório da task. É esse relatório que a fase 4 vai ler.

**Comandos:**

```bash
cd back-end/commerce-service && uv run pytest -q
cd back-end/commerce-service && uv run ruff check . && uv run ruff format --check .
make services-test            # toda a frota
make stack-up                 # legacy + microserviços
```

---

## File Structure

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `commerce-service/pyproject.toml` | `aioboto3`, `redis`, `uuid-utils`, `httpx` de volta ao runtime | B1, B7 |
| `commerce-service/app/config.py` | `redis_url`, `r2_*`, `media_*`, `auth_service_url` | B1, B7 |
| `commerce-service/app/ids.py` | **novo** — `new_uuid()` UUIDv7 | B1 |
| `commerce-service/app/storage.py` | **novo** — `ObjectStorage` + `get_storage` | B2 |
| `commerce-service/app/redis_client.py` | **novo** — `get_redis` | B2 |
| `commerce-service/app/services/media.py` | **novo** — `presigned_image_url` | B2 |
| `commerce-service/app/models/produto.py` | `Produto` → `Product`, PK UUID, colunas novas | B3, B4, B5 |
| `commerce-service/app/models/review.py` | **novo** — `Review` | B7 |
| `commerce-service/app/models/carrinho.py` | **novo** — `Cart`, `CartItem` | B8 |
| `commerce-service/app/models/pagamento.py` | **novo** — `PaymentMethod` | B9 |
| `commerce-service/app/schemas/produto.py` | `ProductOut`/`ProductList`/`CategoryOut`/`CategoryList` | B3, B6 |
| `commerce-service/app/schemas/review.py` | **novo** — `ReviewIn`/`ReviewOut`/`ReviewList` | B7 |
| `commerce-service/app/schemas/carrinho.py` | **novo** — `CartItemIn`/`CartItemOut`/`CartOut` | B8 |
| `commerce-service/app/schemas/pagamento.py` | **novo** — `PaymentMethodIn`/`Patch`/`Out` + enum | B9 |
| `commerce-service/app/routers/produtos.py` | as 5 rotas de `/products` | B6, B7 |
| `commerce-service/app/routers/carrinho.py` | **novo** — 3 rotas de `/cart` | B8 |
| `commerce-service/app/routers/pagamento.py` | **novo** — 4 rotas de `/payment-methods` | B9 |
| `commerce-service/app/services/produtos.py` | **novo** — list/get/categorias/reviews | B6, B7 |
| `commerce-service/app/services/carrinho.py` | **novo** — get/add/remove + `build_cart_out` | B8 |
| `commerce-service/app/services/pagamento.py` | **novo** — CRUD + regra de default | B9 |
| `commerce-service/app/services/auth_client.py` | **novo** — `get_me()` com repasse do bearer | B7 |
| `commerce-service/app/services/substituicao_ia.py` | ids UUID em vez de int | B4 |
| `commerce-service/app/routers/ocorrencias.py` | `_montar_detalhe` acompanha o rename e o UUID | B3, B4 |
| `commerce-service/app/seeds/products.py` | **novo** — seed do catálogo | B10 |
| `commerce-service/alembic/versions/*` | quatro revisions | B3, B4, B5, B7–B9 |
| `back-end/docker-compose.yml` | env de Redis/MinIO/auth no commerce | B1, B7 |
| `Makefile` | alvo `services-seed` | B10 |

---

### Task B0: meça as duas divergências de porte antes de portar qualquer coisa

Portar um arquivo de teste do legacy para o commerce-service exige duas adaptações mecânicas — e uma delas **não é mecânica**: é uma diferença de comportamento que o spec não mediu.

**Files:** nenhum. Produz um relatório e uma decisão registrada.

- [ ] **Step 1: Meça o prefixo**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app/back-end
grep -n "prefix" legacy/app/main.py | head
grep -n 'router = APIRouter' commerce-service/app/routers/produtos.py
grep -n '"products"' api-gateway/app/routing.py
```

Esperado: o legacy monta os módulos sob `/api`; o commerce monta `/products` cru; o gateway mapeia `/api/products` → commerce. **Conclusão:** toda URL num teste portado perde o `/api`. Isso é mecânico e não muda contrato — no dia do corte o app continua chamando `/api/products`, só que via gateway.

- [ ] **Step 2: Meça o código de "sem credencial nenhuma"**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app/back-end
grep -n "401\|403" legacy/app/modules/auth/dependencies.py
grep -n "HTTP_403_FORBIDDEN\|HTTP_401_UNAUTHORIZED" packages/edu-common/src/edu_common/deps.py
grep -rn "requires_auth\|requires_authentication" commerce-service/tests/ | head
```

Esperado:
- Legacy: header `Authorization` ausente → **401**.
- `edu-common`: header ausente → **403** "Não autenticado"; token presente mas inválido/expirado → **401**. O docstring em `deps.py:16-22` explica que a distinção é deliberada e existe para não depender do default do FastAPI.
- As 69 suítes atuais do commerce **assertam 403** para header ausente (ex.: `test_create_order_requires_authentication`).

- [ ] **Step 3: Decida e registre**

Os testes portados do legacy assertam `401` onde o commerce responde `403`. São exatamente os testes da classe `TestAuthRequired` de cada módulo.

**Decisão desta task:** manter o `403` do `edu-common` e adaptar a asserção portada, **registrando cada uma**. Razão: mudar `edu-common` mexeria nos sete serviços e invalidaria as 92 suítes que já assertam 403, para alinhar um caso que o app quase não exercita — o header só falta quando o usuário não está logado, e nesse estado ele está na tela de login. O caso que importa de verdade — **token expirado** — é 401 nos dois, então `TokenRefresher.refresh()` continua disparando igual.

**Esta é uma divergência real do "réplica exata", e a primeira medida depois do spec.** Escreva-a no relatório da task com esta forma exata, porque a fase 4 vai precisar dela:

```
DIVERGÊNCIA DE CONTRATO — não coberta pelo spec da fase 2
Rota:      todas as rotas autenticadas
Caso:      requisição SEM header Authorization
Legacy:    401
Commerce:  403 "Não autenticado"
Caso token expirado/inválido: 401 nos dois (o que o TokenRefresher usa)
Decisão:   mantido o 403; asserções portadas adaptadas, N ocorrências
Risco no corte: o app mostra erro genérico em vez de mandar para o login
                quando alcança uma rota autenticada sem token nenhum.
```

- [ ] **Step 4: Conte as ocorrências**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app/back-end/legacy
grep -rn "== 401" tests/modules/products/ tests/modules/cart/ tests/modules/payment_methods/ | wc -l
grep -rn "== 401" tests/modules/products/ tests/modules/cart/ tests/modules/payment_methods/
```

Anote o número no relatório — é o `N` do bloco acima, e é o total de asserções que a constraint 20 obriga a justificar.

- [ ] **Step 5: Relate**

Nada a commitar. O relatório desta task é entrada obrigatória para B6, B8, B9 e para o plano da fase 4.

---

### Task B1: dependências, config e ambiente para Redis e armazenamento de objeto

O `commerce-service` não fala com Redis nem com MinIO hoje. Os dois já sobem no compose (o legacy os usa); falta o serviço saber deles.

**Files:**
- Modify: `back-end/commerce-service/pyproject.toml`
- Modify: `back-end/commerce-service/app/config.py`
- Create: `back-end/commerce-service/app/ids.py`
- Modify: `back-end/commerce-service/.env.example`
- Modify: `back-end/docker-compose.yml`
- Test: `back-end/commerce-service/tests/test_config.py` (novo)

**Interfaces:**
- Produces:
  - `settings.redis_url: str`, `settings.redis_url_test: str`
  - `settings.r2_endpoint_url: str`, `r2_public_endpoint_url: str | None`, `r2_access_key_id: str`, `r2_secret_access_key: str`, `r2_region: str`, `r2_bucket: str`
  - `settings.media_presign_ttl_seconds: int`, `media_presign_cache_ttl_seconds: int`, `media_max_upload_bytes: int`
  - `app.ids.new_uuid() -> uuid.UUID` (UUIDv7)

- [ ] **Step 1: Escreva o teste que falha**

Crie `back-end/commerce-service/tests/test_config.py`:

```python
import uuid

from app.config import settings
from app.ids import new_uuid


def test_media_settings_have_the_legacy_defaults():
    """Os defaults têm que bater com `legacy/app/core/config.py` — o mesmo
    MinIO serve os dois enquanto o legacy estiver de pé, e a URL presignada
    é assinada contra o mesmo bucket."""
    assert settings.r2_bucket == "edu-media"
    assert settings.r2_region == "auto"
    assert settings.media_presign_ttl_seconds == 86400
    assert settings.media_presign_cache_ttl_seconds == 82800
    assert settings.media_max_upload_bytes == 5 * 1024 * 1024


def test_presign_cache_ttl_is_shorter_than_the_url_ttl():
    """Se o cache durasse mais que a assinatura, o Redis devolveria uma URL
    já expirada — imagem quebrada no app, sem erro em lugar nenhum."""
    assert settings.media_presign_cache_ttl_seconds < settings.media_presign_ttl_seconds


def test_new_uuid_is_time_ordered():
    """UUIDv7 preserva localidade de inserção no índice B-tree do Postgres.
    Dois ids gerados em sequência têm que sair ordenados."""
    primeiro = new_uuid()
    segundo = new_uuid()
    assert isinstance(primeiro, uuid.UUID)
    assert primeiro.bytes < segundo.bytes
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_config.py -v`

Expected: `ImportError`/`AttributeError` — nem `app.ids` nem os campos existem.

- [ ] **Step 3: Acrescente as dependências**

Em `back-end/commerce-service/pyproject.toml`, em `[project].dependencies`:

```toml
    "redis>=5.2.0",
    "aioboto3>=13.2.0",
    "uuid-utils>=0.10.0",
```

E em `[dependency-groups].dev` (`fakeredis` cobre o teste de `presigned_image_url` sem exigir um Redis de pé; se preferir o Redis real do compose, use `redis_url_test` — decida em B2):

```toml
    "fakeredis>=2.26.0",
```

Run: `cd back-end/commerce-service && uv sync`

- [ ] **Step 4: Acrescente os campos de config**

Em `back-end/commerce-service/app/config.py`, dentro de `Settings`:

```python
    # Redis — memoização da URL presignada (ver app/services/media.py). O
    # serviço não tinha nenhuma dependência de runtime além de Postgres e
    # RabbitMQ; esta é a primeira das duas que a fase 2 acrescenta.
    redis_url: str = "redis://:edu@redis:6379/0"
    redis_url_test: str = "redis://:edu@redis:6379/14"

    # Armazenamento de objeto (MinIO em dev, R2 em prod). Os defaults batem
    # com `legacy/app/core/config.py` de propósito: o mesmo bucket serve os
    # dois enquanto o legacy estiver de pé, e uma chave gravada por um tem
    # que ser presignável pelo outro.
    #
    # `r2_public_endpoint_url` é o host contra o qual a URL é ASSINADA — tem
    # que ser alcançável pelo aparelho, não o hostname interno do docker.
    r2_endpoint_url: str = "http://minio:9000"
    r2_public_endpoint_url: str | None = None
    r2_access_key_id: str = "edu"
    r2_secret_access_key: str = "edu-secret"  # noqa: S105 — credencial de dev do MinIO
    r2_region: str = "auto"
    r2_bucket: str = "edu-media"

    # `media_presign_cache_ttl_seconds` TEM que ser menor que
    # `media_presign_ttl_seconds`: o cache guarda a URL assinada, então um
    # cache mais longo que a assinatura devolveria URL expirada.
    media_presign_ttl_seconds: int = 86400
    media_presign_cache_ttl_seconds: int = 82800
    media_max_upload_bytes: int = 5 * 1024 * 1024
```

> **Constraint 12:** `redis_url_test` usa o banco **14**, não o 15 — o legacy usa o 15 (`REDIS_URL_TEST` em `legacy/app/core/config.py:22`) e as duas suítes fazem `flushdb`. Rodar as duas ao mesmo tempo no mesmo banco derruba uma delas de forma intermitente.

- [ ] **Step 5: Escreva `app/ids.py`**

Crie `back-end/commerce-service/app/ids.py`:

```python
import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """Gera um UUIDv7 (ordenado no tempo) como `uuid.UUID` da stdlib.

    Mesma função de `legacy/app/core/ids.py`. Id ordenado no tempo preserva
    a localidade de inserção no índice B-tree do Postgres; UUIDv4 aleatório
    fragmenta o índice a cada insert.
    """
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
```

- [ ] **Step 6: Declare no `.env.example` e no compose**

Em `back-end/commerce-service/.env.example`, acrescente `REDIS_URL`, `REDIS_URL_TEST`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` com os mesmos valores de dev.

Em `back-end/docker-compose.yml`, no bloco `commerce-service`, acrescente ao `environment:` (abaixo de `GOOGLE_MAPS_API_KEY`):

```yaml
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      REDIS_URL_TEST: redis://:${REDIS_PASSWORD}@redis:6379/14
      R2_ENDPOINT_URL: http://minio:9000
      # Assina a URL presignada contra o IP LAN do host, para o aparelho
      # físico alcançar o MinIO. Mesma linha que `api` e `worker` já têm.
      R2_PUBLIC_ENDPOINT_URL: "http://${HOST_IP:-10.0.2.2}:9000"
```

e ao `depends_on`, que hoje é `*depends-db-mq`, acrescente o Redis. Como o anchor é compartilhado, **não** o edite — escreva o bloco inteiro no commerce:

```yaml
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_started
```

> O `minio` do compose não declara healthcheck, então `service_started` é o que dá para pedir. Se você acrescentar um healthcheck a ele, troque para `service_healthy` — mas isso é mudança fora do escopo desta task.

- [ ] **Step 7: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS.

- [ ] **Step 8: Confirme que o container sobe com o env novo**

Run:
```bash
cd back-end && docker compose up -d commerce-service && sleep 3
docker compose exec -T commerce-service python -c "from app.config import settings; print(settings.r2_bucket, settings.redis_url)"
curl -s localhost:8103/health
```

Expected: `edu-media redis://:...@redis:6379/0` e `{"status":"ok"}`. **Constraint 17:** se não responder, `docker compose restart commerce-service`.

- [ ] **Step 9: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/pyproject.toml back-end/commerce-service/uv.lock \
        back-end/commerce-service/app/config.py back-end/commerce-service/app/ids.py \
        back-end/commerce-service/.env.example back-end/commerce-service/tests/test_config.py \
        back-end/docker-compose.yml
git diff --staged
git commit -m "feat(commerce): declare redis and object storage settings

The catalog serves image_url as a presigned URL memoized in Redis, so the
service gains its first two runtime dependencies beyond Postgres and
RabbitMQ. Defaults mirror legacy/app/core/config.py because the same MinIO
bucket serves both stacks until the cutover.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B2: `ObjectStorage`, cliente Redis e `presigned_image_url`

Porte de `legacy/app/core/storage.py`, `redis_client.py` e a metade de **leitura** de `media.py`. `validate_image_bytes` e `new_image_key` ficam para a fase 3 (upload).

**Files:**
- Create: `back-end/commerce-service/app/storage.py`
- Create: `back-end/commerce-service/app/redis_client.py`
- Create: `back-end/commerce-service/app/services/media.py`
- Test: `back-end/commerce-service/tests/test_media.py` (portado de `legacy/tests/core/test_media.py`)
- Test: `back-end/commerce-service/tests/test_storage.py` (portado, só a metade de leitura)

**Interfaces:**
- Produces:
  - `app.storage.ObjectStorage` com `put_object(key, body, content_type)`, `delete_object(key)`, `generate_presigned_get(key, *, expires_in) -> str`
  - `app.storage.get_storage() -> ObjectStorage` (dependência FastAPI)
  - `app.redis_client.get_redis() -> redis.Redis` (dependência FastAPI)
  - `app.services.media.presigned_image_url(key: str, *, storage: ObjectStorage, redis: redis.Redis) -> str`

- [ ] **Step 1: Porte os testes do legacy (Red)**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp legacy/tests/core/test_media.py commerce-service/tests/test_media.py
cp legacy/tests/core/test_storage.py commerce-service/tests/test_storage.py
```

Abra os dois e adapte **só** o que é estrutural:
- `from app.core.media import ...` → `from app.services.media import ...`
- `from app.core.storage import ...` → `from app.storage import ...`
- `from app.core.config import settings` → `from app.config import settings`
- `settings.MEDIA_PRESIGN_TTL_SECONDS` → `settings.media_presign_ttl_seconds` (e os demais, minúsculos)
- Apague os testes de `validate_image_bytes` e `new_image_key` — **é o carve-out declarado no spec** (upload é fase 3). Anote no relatório quantos saíram.
- Apague os testes de escrita de `test_storage.py` (`put_object`, `delete_object`) pelo mesmo motivo. `generate_presigned_get` fica.

> **Constraint 20:** cada teste apagado é uma linha do relatório. "Carve-out fase 3: `test_validate_image_bytes_rejects_wrong_magic`" e assim por diante.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_media.py tests/test_storage.py -v`

Expected: `ModuleNotFoundError: No module named 'app.storage'`. Se der outra coisa, você deixou um import do legacy para trás.

- [ ] **Step 3: Porte `ObjectStorage`**

Crie `back-end/commerce-service/app/storage.py` com o conteúdo de `legacy/app/core/storage.py`, trocando as referências de settings para minúsculas e ajustando o docstring:

```python
import aioboto3
from botocore.config import Config

from app.config import settings


class ObjectStorage:
    """Cliente S3-compatível assíncrono (MinIO em dev, R2 em prod).

    Porte de `legacy/app/core/storage.py`. O bucket é privado; a leitura
    acontece por GET presignado, nunca por URL pública.

    O `put_object`/`delete_object` existem porque o seed do catálogo (B10)
    os usa. O endpoint de upload de imagem é fase 3.
    """

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._bucket = settings.r2_bucket
        self._config = Config(signature_version="s3v4", s3={"addressing_style": "path"})

    def _client(self, *, public: bool = False):
        endpoint = settings.r2_public_endpoint_url if public else settings.r2_endpoint_url
        return self._session.client(
            "s3",
            endpoint_url=endpoint or settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region,
            config=self._config,
        )

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
            )

    async def delete_object(self, key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def generate_presigned_get(self, key: str, *, expires_in: int) -> str:
        # Assina contra o endpoint público para que o host da URL seja
        # alcançável pelo app (emulador, aparelho na LAN), e não o hostname
        # interno do docker.
        async with self._client(public=True) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )


_storage = ObjectStorage()


def get_storage() -> ObjectStorage:
    return _storage
```

- [ ] **Step 4: Porte o cliente Redis**

Crie `back-end/commerce-service/app/redis_client.py`:

```python
import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Cliente Redis assíncrono de módulo, sobre um pool único.

    `decode_responses=True` porque o único uso hoje guarda URL presignada
    como string — `presigned_image_url` devolve o valor do cache direto.
    """
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def get_redis() -> redis.Redis:
    """Dependência FastAPI que entrega o cliente Redis."""
    return get_redis_client()
```

- [ ] **Step 5: Porte `presigned_image_url`**

Crie `back-end/commerce-service/app/services/media.py`:

```python
import redis.asyncio as aioredis

from app.config import settings
from app.storage import ObjectStorage


def _public_endpoint() -> str:
    """Endpoint contra o qual a URL é assinada. Entra na chave de cache para
    que um endpoint trocado (novo IP LAN do host, por exemplo) produza chave
    nova em vez de servir URL velha apontando para um host inalcançável."""
    return settings.r2_public_endpoint_url or settings.r2_endpoint_url


async def presigned_image_url(
    key: str,
    *,
    storage: ObjectStorage,
    redis: aioredis.Redis,
) -> str:
    """Transforma uma chave de objeto numa URL GET presignada, memoizada no
    Redis para que a mesma chave devolva a MESMA URL dentro da janela.

    A memoização não é otimização de custo de assinatura — é o que mantém o
    cache de imagem do app funcionando. Sem ela, cada listagem devolveria uma
    URL diferente para a mesma foto, e o Flutter rebaixaria o próprio cache a
    cada scroll.

    Chave vazia devolve string vazia: produto sem imagem não vira URL.
    """
    if not key:
        return ""
    cache_key = f"presign:{_public_endpoint()}:{key}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return cached
    url = await storage.generate_presigned_get(key, expires_in=settings.media_presign_ttl_seconds)
    await redis.set(cache_key, url, ex=settings.media_presign_cache_ttl_seconds)
    return url
```

- [ ] **Step 6: Dê ao conftest a fixture de Redis**

Em `back-end/commerce-service/tests/conftest.py`, acrescente:

```python
@pytest.fixture
async def redis_client() -> AsyncIterator[aioredis.Redis]:
    """Redis de teste no banco 14 (o legacy usa o 15 — ver `settings`).

    `flushdb` nas duas pontas: a memoização de `presigned_image_url` é o
    ponto todo do módulo, então um teste que herde chave de outro passaria
    sem exercitar a assinatura.
    """
    client = aioredis.from_url(
        settings.redis_url_test, encoding="utf-8", decode_responses=True
    )
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
```

com `import redis.asyncio as aioredis` no topo, e registre o override no fixture `client` (que hoje só sobrescreve `get_db`):

```python
    async def _override_get_redis() -> aioredis.Redis:
        return redis_client

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
```

acrescentando `redis_client` aos parâmetros de `client` e `from app.redis_client import get_redis` ao topo.

> A suíte passa a exigir um Redis alcançável. `make services-test` roda no host, então o `redis_url_test` do `.env` do serviço precisa apontar para `localhost:6380` (a porta publicada — confira `REDIS_PORT_EXTERNAL` no `back-end/.env`), não para `redis:6379`. Ajuste `commerce-service/.env.example` e diga isso no relatório: é a primeira suíte do commerce que depende de infra além do Postgres.

- [ ] **Step 7: Rode e confirme que passa**

Run: `cd back-end && docker compose up -d redis minio && cd commerce-service && uv run pytest tests/test_media.py tests/test_storage.py -v`

Expected: PASS.

- [ ] **Step 8: Prove que a memoização é real (constraint 11)**

Acrescente, se o teste portado não cobrir:

```python
async def test_the_same_key_returns_the_same_url_within_the_window(redis_client, monkeypatch):
    """Sem a memoização o app rebaixa o próprio cache de imagem a cada listagem."""
    assinaturas = 0

    class _StorageQueContaAssinaturas:
        async def generate_presigned_get(self, key, *, expires_in):
            nonlocal assinaturas
            assinaturas += 1
            return f"http://minio/{key}?sig={assinaturas}"

    storage = _StorageQueContaAssinaturas()
    primeira = await presigned_image_url("products/x.jpg", storage=storage, redis=redis_client)
    segunda = await presigned_image_url("products/x.jpg", storage=storage, redis=redis_client)

    assert primeira == segunda
    assert assinaturas == 1
```

Depois, comente o `await redis.set(...)` de `media.py`, rode, confirme `assert 2 == 1`, reaplique.

- [ ] **Step 9: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/storage.py back-end/commerce-service/app/redis_client.py \
        back-end/commerce-service/app/services/media.py \
        back-end/commerce-service/tests/conftest.py \
        back-end/commerce-service/tests/test_media.py back-end/commerce-service/tests/test_storage.py \
        back-end/commerce-service/.env.example
git diff --staged
git commit -m "feat(commerce): port object storage and the presigned image URL

image_url holds an object key, not a URL; serialization turns it into a
short-lived presigned GET memoized in Redis so the same key yields the same
URL within the window — without that the app re-downloads every image on
every listing. Upload validation stays in phase 3.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B3: rename mecânico `produtos` → `products`

**Só o rename.** Nenhuma coluna nova, PK ainda `Integer`, nenhuma rota nova. Mecânico em tudo, **exceto um ponto medido na execução** (task-B3-report.md): o campo exposto por `ProductOut` muda de `category` para `type` — não é substituição de nome, é mudança de contrato declarada, porque `validation_alias` só afeta a direção de entrada e o campo que `GET /products` já expunha antes desta task era `category` (inglês), não `categoria`. A troca alinha com o `ProductOut` do legacy (`back-end/legacy/app/modules/products/schemas.py`), que já expõe `type: str`, evitando que a B5/B6 desfizessem esse mesmo rename adiante. As duas asserções de teste afetadas por essa mudança estão registradas no relatório da task. Fora esse ponto, a suíte tem que estar verde antes e depois, e o diff tem que ser lível como uma substituição de nomes. É a mitigação que o spec pede para o risco "a tradução tem raio maior que o agregado".

Mapeamento: `produtos`→`products`, `nome`→`name`, `descricao`→`description`, `preco`→`price`, `categoria`→**`type`**, `imagem_url`→`image_url`.

> `categoria` e `type` são o mesmo conceito com dois nomes — os valores do seed do legacy são `apostila`, `curso`, `digital`. Colapsam em `type` aqui, e não numa coluna a mais.

**Files:**
- Modify: `back-end/commerce-service/app/models/produto.py`
- Modify: `back-end/commerce-service/app/schemas/produto.py`
- Modify: `back-end/commerce-service/app/routers/produtos.py`
- Modify: `back-end/commerce-service/app/routers/ocorrencias.py` (`_montar_detalhe`)
- Modify: `back-end/commerce-service/app/schemas/ocorrencia.py` (`ProdutoSugeridoOut`)
- Modify: `back-end/commerce-service/app/services/substituicao_ia.py`
- Modify: `back-end/commerce-service/app/models/pedido.py` (`PedidoItem.produto_id` FK aponta para `products.id`)
- Create: `back-end/commerce-service/alembic/versions/<hash>_rename_produtos_to_products.py`
- Modify: as suítes do commerce que citam `Produto`/`produtos`

**Interfaces:**
- Produces: `app.models.produto.Product` (a classe `Produto` deixa de existir). Colunas: `id: int`, `name: str`, `description: str | None`, `price: Decimal`, `type: str | None`, `image_url: str | None`.
- `ProductOut` deixa de usar `validation_alias` — os nomes passam a bater.

- [ ] **Step 1: Meça o raio antes de mexer**

Run:
```bash
cd back-end/commerce-service
grep -rn "Produto\b\|produtos\|\.nome\|\.preco\|\.categoria\|\.imagem_url\|\.descricao" app/ tests/ alembic/ | grep -v "produto_id\|produto_escolhido_id\|produtos_sugeridos" > /tmp/raio-b3.txt
wc -l /tmp/raio-b3.txt && cat /tmp/raio-b3.txt
```

Esse arquivo é a lista de trabalho da task. Registre a contagem no relatório: é ela que torna o risco verificável.

- [ ] **Step 2: Confirme a suíte verde ANTES**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS. Anote a contagem de testes. Se não estiver verde, pare — o rename não pode começar sobre suíte vermelha, porque aí não dá para saber o que ele quebrou.

- [ ] **Step 3: Renomeie o model**

Em `back-end/commerce-service/app/models/produto.py`:

```python
class Product(Base):
    """Catálogo. Em inglês — tabela e colunas — porque este é o primeiro
    agregado do commerce a ganhar cliente (o app Flutter, na fase 4), e a
    regra do design é: o agregado que ganha cliente vira inglês; o que não
    ganha, fica.

    `fornecedores`, `estoque` e `ocorrencias` continuam em português pelo
    mesmo critério — nenhum tem cliente.

    `type` absorveu `categoria`: eram o mesmo conceito com dois nomes. Os
    valores do seed do legacy são `apostila`, `curso`, `digital`.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    type = Column(String(50), nullable=True)
    image_url = Column(String(255), nullable=True)
```

`Fornecedor` e `Estoque` ficam como estão, exceto o `ForeignKey`:

```python
    produto_id = Column(Integer, ForeignKey("products.id"))
```

Em `app/models/pedido.py`, o mesmo em `PedidoItem`:

```python
    produto_id = Column(Integer, ForeignKey("products.id"))
```

Em `app/models/ocorrencia.py`, os dois FKs:

```python
    produto_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    produto_escolhido_id = Column(Integer, ForeignKey("products.id"), nullable=True)
```

> `estoque.produto_id`, `pedido_itens.produto_id` e `ocorrencias.produto_id` **não** são renomeados: são colunas de agregados sem cliente, e a regra é por agregado. Só o alvo do `ForeignKey` muda.

- [ ] **Step 4: Simplifique o schema**

Em `back-end/commerce-service/app/schemas/produto.py`:

```python
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    price: Decimal
    type: str | None = None
    image_url: str | None = None
```

Os `validation_alias` somem — eles existiam só para traduzir português→inglês na serialização, e agora os nomes batem. Atualize o docstring do módulo, que hoje explica a tradução (constraint 16).

- [ ] **Step 5: Atualize os chamadores**

Percorra `/tmp/raio-b3.txt`. Os pontos que **não** são substituição de nome:

- `app/routers/produtos.py`: `Produto.categoria == category` → `Product.type == category`, `order_by(Produto.id)` → `order_by(Product.id)`.
- `app/routers/ocorrencias.py::_montar_detalhe`: `ProdutoSugeridoOut(id=p.id, nome=p.nome, preco=float(p.preco), imagem_url=p.imagem_url)` → os campos do schema `ProdutoSugeridoOut` **continuam em português** (é um schema de `ocorrencias`, agregado sem cliente), mas os atributos lidos viram os do model novo: `nome=p.name, preco=float(p.price), imagem_url=p.image_url`.
- `app/services/substituicao_ia.py`: só nomes de atributo.

> Este é o ponto exato da "regra de língua de schema" do spec: o schema segue a **tabela**, não o router. `ProdutoSugeridoOut` vive em `ocorrencias`, cuja tabela não mudou, então seus campos ficam em português — mesmo lendo de um model inglês.

- [ ] **Step 6: Gere a migration**

Run:
```bash
cd back-end && docker compose up -d && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "rename produtos to products"
```

**Leia a revision gerada e conserte-a.** O autogenerate do Alembic **não** detecta rename: ele gera `drop_table("produtos")` + `create_table("products")`, que apaga dado. Substitua por renames explícitos:

```python
def upgrade() -> None:
    op.rename_table("produtos", "products")
    op.alter_column("products", "nome", new_column_name="name")
    op.alter_column("products", "descricao", new_column_name="description")
    op.alter_column("products", "preco", new_column_name="price")
    op.alter_column("products", "categoria", new_column_name="type")
    op.alter_column("products", "imagem_url", new_column_name="image_url")


def downgrade() -> None:
    op.alter_column("products", "image_url", new_column_name="imagem_url")
    op.alter_column("products", "type", new_column_name="categoria")
    op.alter_column("products", "price", new_column_name="preco")
    op.alter_column("products", "description", new_column_name="descricao")
    op.alter_column("products", "name", new_column_name="nome")
    op.rename_table("products", "produtos")
```

> As FKs de `estoque`, `pedido_itens` e `ocorrencias` acompanham o rename da tabela sozinhas no Postgres — a constraint referencia o OID, não o nome. Não escreva `drop_constraint`/`create_foreign_key` aqui; confirme no Step 8 que o autogenerate concorda.

- [ ] **Step 7: Atualize as suítes**

Substitua `Produto` por `Product` e os nomes de atributo nos arquivos de teste do commerce. **Nenhuma asserção de comportamento muda** — se você precisou mudar uma, o rename deixou de ser mecânico e a task passou do escopo.

- [ ] **Step 8: Rode e confirme a suíte verde DEPOIS, e o sync-check**

```bash
cd back-end/commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic upgrade head
docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS com **a mesma contagem de testes do Step 2**, e a revision de sync-check **vazia**. Apague o arquivo gerado.

> Contagem diferente do Step 2 significa que um teste sumiu ou nasceu num rename que deveria ser mecânico. Investigue antes de commitar.

- [ ] **Step 9: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "refactor(commerce): rename produtos to products, table and columns

Mechanical rename, no behaviour change: the products aggregate is the first
in this service to get a client, and the design rule is per aggregate — the
one that gains a client turns English, the one that does not stays.
categoria collapses into type; they were the same concept under two names.
fornecedores, estoque and ocorrencias are untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B4: `products.id` vira UUID e arrasta seis referências

O Flutter faz `as String` sobre `id`. Inteiro levanta `TypeError` que o tratamento de erro do app não captura — a tela quebra sem virar mensagem. UUID também elimina id enumerável.

A cascata, medida no spec: `estoque.produto_id` · `pedido_itens.produto_id` · `ocorrencias.produto_id` · `ocorrencias.produto_escolhido_id` · **`ocorrencias.produtos_sugeridos`** (JSONB com lista de ids) · e `substituicao_ia.py`, que produz e consome essa lista.

`fornecedores.id` continua `Integer`: sem cliente, e não enumerável de fora.

**Files:**
- Modify: `back-end/commerce-service/app/models/produto.py`, `pedido.py`, `ocorrencia.py`
- Modify: `back-end/commerce-service/app/schemas/produto.py`, `ocorrencia.py`
- Modify: `back-end/commerce-service/app/routers/produtos.py`, `ocorrencias.py`
- Modify: `back-end/commerce-service/app/services/substituicao_ia.py`
- Create: `back-end/commerce-service/alembic/versions/<hash>_products_uuid_pk.py`
- Modify: as suítes do commerce que constroem produtos

**Interfaces:**
- Produces: `Product.id: uuid.UUID` (`UUID(as_uuid=True)`, `default=new_uuid`, `server_default=text("gen_random_uuid()")`).
  `sugerir_substitutos(db, produto_id: uuid.UUID) -> list[str]` — devolve **lista de UUID em string**, porque o retorno vai direto para uma coluna JSONB e JSON não tem tipo UUID.

- [ ] **Step 1: Meça o dado que existe (portão)**

Run:
```bash
cd back-end && docker compose exec -T postgres psql -U edu -d commerce_db -c "
  SELECT 'products' AS t, count(*) FROM products
  UNION ALL SELECT 'estoque', count(*) FROM estoque
  UNION ALL SELECT 'pedido_itens', count(*) FROM pedido_itens
  UNION ALL SELECT 'ocorrencias', count(*) FROM ocorrencias;"
```

- **Todas 0:** a suposição do spec está confirmada. A migration pode ser **reconstrução declarada** (drop + create com o tipo novo).
- **Qualquer uma > 0:** pare. A migration vira preservadora (`ALTER ... TYPE uuid USING`, backfill, remapeamento do JSONB) e isso é decisão de escopo, não de execução. Leve ao autor do spec.

> Esta é a mesma medição da task 25 do bloco A. Refaça-a mesmo assim: entre um bloco e outro alguém pode ter rodado um seed.

- [ ] **Step 2: Escreva o teste que falha**

Em `back-end/commerce-service/tests/test_products_routes.py`:

```python
async def test_product_id_is_a_uuid_string_in_the_response(client, db_session):
    """O Flutter faz `as String` sobre `id`. Inteiro levanta TypeError que o
    tratamento de erro do app não captura — a tela quebra sem virar mensagem."""
    produto = Product(name="Guia", price=Decimal("49.90"), type="apostila")
    db_session.add(produto)
    await db_session.commit()

    response = await client.get("/products", headers=headers_for("student"))

    assert response.status_code == 200
    item = response.json()[0]
    assert isinstance(item["id"], str)
    uuid.UUID(item["id"])  # levanta se não for um UUID


async def test_suggested_products_are_stored_as_uuid_strings(db_session):
    """`ocorrencias.produtos_sugeridos` é JSONB. JSON não tem tipo UUID, então
    a lista guarda strings — e `substituicao_ia` tem que produzi-las assim."""
    alvo = Product(name="Guia", price=Decimal("49.90"), type="apostila")
    similar = Product(name="Guia Avançado", price=Decimal("59.90"), type="apostila")
    db_session.add_all([alvo, similar])
    await db_session.commit()

    sugeridos = await sugerir_substitutos(db_session, alvo.id)

    assert all(isinstance(s, str) for s in sugeridos)
    for s in sugeridos:
        uuid.UUID(s)
```

> O primeiro teste asserta sobre a forma **atual** de `GET /products` (array puro). O envelope entra em B6 — não antecipe.

- [ ] **Step 3: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_products_routes.py -k "uuid" -v`

Expected: FALHAM — `assert isinstance(1, str)`.

- [ ] **Step 4: Troque o tipo da PK e das seis referências**

Em `app/models/produto.py`:

```python
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.ids import new_uuid


class Product(Base):
    __tablename__ = "products"

    # `default=` cobre insert pelo ORM; `server_default` cobre insert que
    # passa por fora dele (psql, seed em SQL, SQLAdmin) — constraint 15.
    # `new_uuid` é UUIDv7 (ordenado no tempo), `gen_random_uuid()` é v4: o
    # server_default é rede de segurança, não o caminho normal.
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
```

Em `estoque`, `pedido_itens`, `ocorrencias.produto_id` e `ocorrencias.produto_escolhido_id`:

```python
    produto_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), ...)
```

mantendo `index=True`/`nullable=` como estão hoje.

Em `app/schemas/produto.py`: `id: uuid.UUID`.
Em `app/schemas/ocorrencia.py`: `ProdutoSugeridoOut.id: uuid.UUID`, e `FaltaEstoqueIn.produto_id`/`ResolverOcorrenciaIn.produto_escolhido_id` viram `uuid.UUID`.
Em `app/routers/ocorrencias.py`: nada além dos tipos — o `Produto.id.in_(ocorrencia.produtos_sugeridos)` continua funcionando, porque o asyncpg converte string→uuid no bind.

- [ ] **Step 5: Ajuste `substituicao_ia.py`**

Leia o arquivo. Onde ele devolve ids, converta para string:

```python
    # A lista vai direto para `ocorrencias.produtos_sugeridos`, que é JSONB.
    # JSON não tem tipo UUID — devolver `uuid.UUID` faria o driver estourar
    # na serialização, e devolver int (o que era antes) deixaria de casar
    # com `products.id`.
    return [str(produto_id) for produto_id in ids_similares]
```

e a assinatura:

```python
async def sugerir_substitutos(db: AsyncSession, produto_id: uuid.UUID) -> list[str]:
```

- [ ] **Step 6: Escreva a migration como reconstrução declarada**

Run: `cd back-end && docker compose exec -T commerce-service uv run alembic revision -m "products uuid pk"`

(Sem `--autogenerate`: o autogenerate não sabe converter tipo de PK e geraria algo que apaga dado sem dizer.)

```python
"""products uuid pk

Reconstrução declarada, não sequência de ALTER com conversão de tipo.

`commerce_db` nunca teve dado de produção: o app fala com o legacy desde
sempre, o serviço não tem seed nem script de insert, e o initdb.d só cria
bancos vazios. A contagem de linhas foi conferida antes de gerar esta
revision (ver o relatório da task B4/Step 1) e deu zero em products,
estoque, pedido_itens e ocorrencias.

Se algum dia esta revision rodar contra um banco com dado, ela o apaga. Por
isso o `upgrade` começa checando, e falha alto em vez de destruir em
silêncio.
"""

import sqlalchemy as sa
from alembic import op

revision = "<hash gerado>"
down_revision = "<hash do rename>"
branch_labels = None
depends_on = None

_TABELAS_AFETADAS = ("products", "estoque", "pedido_itens", "ocorrencias")


def _falhar_se_houver_dado(conn) -> None:
    for tabela in _TABELAS_AFETADAS:
        total = conn.execute(sa.text(f"SELECT count(*) FROM {tabela}")).scalar_one()  # noqa: S608
        if total:
            raise RuntimeError(
                f"{tabela} tem {total} linhas. Esta revision é uma reconstrução "
                "declarada e as apagaria. Ver docs/superpowers/plans/"
                "2026-08-05-phase-2b-catalog-and-cart.md, task B4."
            )


def upgrade() -> None:
    conn = op.get_bind()
    _falhar_se_houver_dado(conn)

    # Ordem: solta as FKs, troca o tipo do lado referenciado, troca o tipo do
    # lado referenciador, refaz as FKs.
    op.drop_constraint("estoque_produto_id_fkey", "estoque", type_="foreignkey")
    op.drop_constraint("pedido_itens_produto_id_fkey", "pedido_itens", type_="foreignkey")
    op.drop_constraint("ocorrencias_produto_id_fkey", "ocorrencias", type_="foreignkey")
    op.drop_constraint(
        "ocorrencias_produto_escolhido_id_fkey", "ocorrencias", type_="foreignkey"
    )

    op.execute("ALTER TABLE products ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE products ALTER COLUMN id TYPE uuid USING gen_random_uuid()")
    op.execute("ALTER TABLE products ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("DROP SEQUENCE IF EXISTS produtos_id_seq")

    for tabela, coluna in (
        ("estoque", "produto_id"),
        ("pedido_itens", "produto_id"),
        ("ocorrencias", "produto_id"),
        ("ocorrencias", "produto_escolhido_id"),
    ):
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} TYPE uuid USING NULL")  # noqa: S608

    op.create_foreign_key(
        "estoque_produto_id_fkey", "estoque", "products", ["produto_id"], ["id"]
    )
    op.create_foreign_key(
        "pedido_itens_produto_id_fkey", "pedido_itens", "products", ["produto_id"], ["id"]
    )
    op.create_foreign_key(
        "ocorrencias_produto_id_fkey", "ocorrencias", "products", ["produto_id"], ["id"]
    )
    op.create_foreign_key(
        "ocorrencias_produto_escolhido_id_fkey",
        "ocorrencias",
        "products",
        ["produto_escolhido_id"],
        ["id"],
    )

    # `produtos_sugeridos` é JSONB com lista de ids. Sem dado, basta zerar.
    op.execute("UPDATE ocorrencias SET produtos_sugeridos = NULL")


def downgrade() -> None:
    raise RuntimeError(
        "Sem downgrade: a conversão int -> uuid descartou os ids originais. "
        "Restaure de backup ou refaça a baseline."
    )
```

> **Confira os nomes reais das constraints antes de rodar:**
> `docker compose exec -T postgres psql -U edu -d commerce_db -c "\d estoque"` (e as demais). Os nomes acima são o padrão do Postgres — se a baseline os nomeou de outro jeito, use os reais. Uma `drop_constraint` com nome errado estoura na hora, o que é o comportamento certo.
>
> `ALTER COLUMN produto_id TYPE uuid USING NULL` só é válido em coluna nullable. `estoque.produto_id` e `pedido_itens.produto_id` são nullable no model atual — confirme. Se alguma for `NOT NULL`, a migration precisa soltar o `NOT NULL` antes e devolvê-lo depois, ou (mais simples, já que a tabela está vazia) `DROP TABLE` + `CREATE`.

- [ ] **Step 7: Aplique, rode e confirme o sync-check**

```bash
cd back-end
docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio**. Apague o gerado.

- [ ] **Step 8: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "refactor(commerce): make products.id a UUID

The Flutter model does `as String` on id; an integer raises a TypeError the
app's error handling does not catch, so the screen breaks without becoming
a message. UUID also removes an enumerable id. Six references follow,
including ocorrencias.produtos_sugeridos, which is JSONB and therefore
holds UUIDs as strings.

The migration is a declared rebuild, guarded by a row-count check that
fails loudly rather than destroying data in silence.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B5: as colunas que o contrato do app exige

`products` ganha `subtype`, `rating_avg`, `rating_count`, `created_at`, `updated_at`, e os campos existentes ganham o tamanho e a nulidade do legacy.

**Files:**
- Modify: `back-end/commerce-service/app/models/produto.py`
- Modify: `back-end/commerce-service/app/schemas/produto.py`
- Create: `back-end/commerce-service/alembic/versions/<hash>_products_catalog_columns.py`
- Test: `back-end/commerce-service/tests/test_products_routes.py`

**Interfaces:**
- Produces: `Product` com o conjunto completo de colunas do `legacy/app/modules/products/models.py::Product`, menos a `relationship` de reviews (que nasce em B7).

- [ ] **Step 1: Escreva o teste que falha**

```python
async def test_product_carries_the_catalog_fields(client, db_session):
    produto = Product(
        name="Guia de Redação Nota 1000",
        type="apostila",
        subtype="Apostila Digital",
        description="Estruturas prontas",
        price=Decimal("49.90"),
        image_url="products/seed-0.jpg",
        rating_avg=4.5,
        rating_count=128,
    )
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    assert produto.subtype == "Apostila Digital"
    assert float(produto.rating_avg) == 4.5
    assert produto.rating_count == 128
    assert produto.created_at is not None
    assert produto.updated_at is not None


async def test_rating_defaults_to_zero_for_a_product_without_reviews(db_session):
    produto = Product(name="Sem review", type="digital", price=Decimal("10.00"))
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    assert float(produto.rating_avg) == 0.0
    assert produto.rating_count == 0
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_products_routes.py -k "catalog_fields or defaults_to_zero" -v`

Expected: `TypeError: 'subtype' is an invalid keyword argument`.

- [ ] **Step 3: Acrescente as colunas**

```python
class Product(Base):
    __tablename__ = "products"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(160), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True)
    subtype = Column(String(64), nullable=False, default="", server_default=text("''"))
    description = Column(Text, nullable=False, default="", server_default=text("''"))
    price = Column(Numeric(10, 2), nullable=False)
    # Chave de objeto (`products/<uuid>.jpg`), NÃO uma URL. A serialização a
    # transforma em GET presignado de vida curta — ver app/services/media.py.
    image_url = Column(String(512), nullable=False, default="", server_default=text("''"))
    # Agregados desnormalizados, mantidos em sincronia na criação da review
    # sob lock de linha (ver app/services/produtos.py::criar_review), para a
    # listagem não precisar de um join por linha.
    rating_avg = Column(Numeric(3, 2), nullable=False, default=0, server_default=text("0"))
    rating_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

> **Constraint 15** em cada `default=`: os `server_default` acompanham porque o seed e uma futura inserção fora do ORM precisam deles. Os tamanhos (`160`, `64`, `512`) são os do legacy — não invente outros, senão um produto que cabe lá não cabe aqui.
>
> `type` vira `nullable=False`. A tabela está vazia (B4/Step 1 provou), então não precisa de backfill — mas a migration declara o `server_default` para o caso de haver linha.

Em `app/schemas/produto.py`, `ProductOut` ganha os campos e o serializador de dinheiro:

```python
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    subtype: str = ""
    description: str = ""
    price: Decimal
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("price")
    def _price_as_string(self, value: Decimal) -> str:
        # O contrato original serializa dinheiro como string ("49.90") para o
        # cliente nunca herdar erro de arredondamento de float. Isso é
        # contrato, não formatação — o app o lê como String.
        return f"{value:.2f}"
```

- [ ] **Step 4: Gere e revise a migration**

Run: `cd back-end && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "products catalog columns"`

Revise o gerado: deve haver `add_column` para `subtype`, `rating_avg`, `rating_count`, `created_at`, `updated_at`; `alter_column` para os tamanhos e nulidades. Confirme que **todo** `nullable=False` novo traz `server_default` — senão a migration falha em tabela com linha.

- [ ] **Step 5: Aplique, rode e sincronize**

```bash
cd back-end && docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio** (é aqui que `compare_server_default=True` prova seu valor — sem ele, um `server_default` faltando passaria batido).

- [ ] **Step 6: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): give products the catalog columns the app reads

subtype, the denormalized rating aggregates and the timestamps, with the
legacy column sizes so a product that fits there fits here. price
serializes as a string: that is the contract, not formatting.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B6: `GET /products`, `/categories` e `/{id}` como réplica exata

**Files:**
- Create: `back-end/commerce-service/app/services/produtos.py`
- Modify: `back-end/commerce-service/app/routers/produtos.py`
- Modify: `back-end/commerce-service/app/schemas/produto.py`
- Test: `back-end/commerce-service/tests/test_products_parity.py` (portado)

**Interfaces:**
- Produces:
  - `services.listar_produtos(db, *, q: str | None, limit: int, offset: int) -> tuple[list[Product], int]`
  - `services.listar_categorias(db) -> list[tuple[str, int]]`
  - `services.buscar_produto(db, product_id: uuid.UUID) -> Product` (levanta `ProductNotFound`)
  - `app.exceptions.ProductNotFound`
  - Schemas `ProductList{items,total,limit,offset}`, `CategoryOut{type,count}`, `CategoryList{items}`

- [ ] **Step 1: Porte o teste do legacy (Red)**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp legacy/tests/modules/products/test_routes.py commerce-service/tests/test_products_parity.py
```

Adapte **só** o estrutural:
1. Toda URL perde o `/api`: `/api/products` → `/products`.
2. `from app.modules.products.models import Product` → `from app.models.produto import Product`.
3. As fixtures `created_user`/`auth_headers` de `legacy/tests/modules/products/conftest.py` não existem aqui. Troque por `headers_for("student")`, o helper que os testes do commerce já usam (ver `tests/test_orders_routes.py:11`). Copie `seeded_products` para o topo do arquivo portado como fixture local, adaptando os imports.
4. `assert r.status_code == 401` em `TestAuthRequired` → `403`, **com um comentário apontando para o relatório da task B0**:
   ```python
   # 403, não 401: ver a divergência registrada na task B0 do plano do bloco B.
   # O `edu-common` responde 403 para header ausente e 401 para token
   # inválido/expirado; o legacy responde 401 nos dois.
   ```
5. Apague a classe de teste de review (ela entra em B7) e a de upload (fase 3). Registre as duas remoções.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_products_parity.py -v`

Expected: FALHAM em massa. Os sintomas esperados: `KeyError: 'total'` (a rota devolve array puro, não envelope), `assert 200 == 422` (não há teto de `limit`), 404 em `/products/categories`.

> **Constraint 18:** se algum teste passar aqui, confira se ele está mesmo batendo na rota certa. Um `/api/products` esquecido devolve 404, e um `assert r.status_code == 401` contra 404 falha — mas um `assert len(items) == 0` contra 404 pode passar por acidente.

- [ ] **Step 3: Escreva a camada de serviço**

Crie `back-end/commerce-service/app/exceptions.py`:

```python
class ProductNotFound(Exception):
    """Produto inexistente. O router a traduz em 404 "Product not found"."""
```

Crie `back-end/commerce-service/app/services/produtos.py`:

```python
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ProductNotFound
from app.models.produto import Product


async def listar_produtos(
    db: AsyncSession, *, q: str | None = None, limit: int, offset: int
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    if q:
        # `ilike` com parâmetro bound — o pattern vai como valor, nunca
        # concatenado na string SQL (regra 1 do CLAUDE.md).
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))

    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def listar_categorias(db: AsyncSession) -> list[tuple[str, int]]:
    stmt = (
        select(Product.type, func.count().label("count"))
        .group_by(Product.type)
        .order_by(Product.type)
    )
    return [(row.type, row.count) for row in (await db.execute(stmt)).all()]


async def buscar_produto(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise ProductNotFound()
    return product
```

- [ ] **Step 4: Acrescente os schemas de envelope**

Em `app/schemas/produto.py`:

```python
class ProductList(BaseModel):
    """Envelope, não array puro. O app faz `jsonDecode(body)['items']` — um
    array puro levanta `TypeError` que o tratamento de erro dele não captura.
    Isso é contrato."""

    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class CategoryOut(BaseModel):
    type: str
    count: int


class CategoryList(BaseModel):
    items: list[CategoryOut]
```

- [ ] **Step 5: Reescreva o router**

`back-end/commerce-service/app/routers/produtos.py`:

```python
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import ProductNotFound
from app.models.produto import Product
from app.redis_client import get_redis
from app.schemas.produto import (
    CategoryList,
    CategoryOut,
    ProductList,
    ProductOut,
)
from app.services import produtos as services
from app.services.media import presigned_image_url
from app.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/products", tags=["products"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


async def _product_out(
    product: Product, *, storage: ObjectStorage, redis: aioredis.Redis
) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.image_url = await presigned_image_url(product.image_url, storage=storage, redis=redis)
    return out


@router.get("", response_model=ProductList)
async def listar_produtos(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductList:
    """Catálogo. Exige autenticação (qualquer papel) — não restringe por papel
    porque não há razão de negócio: o aluno monta carrinho, e separador,
    entregador e admin também precisam consultar o catálogo.

    `limit` 1–100 com default 20, `q` até 160 caracteres, envelope com
    `total`/`limit`/`offset`: os quatro são contrato, medidos contra o
    legacy. Mudar qualquer um quebra o app na fase 4.
    """
    items, total = await services.listar_produtos(db, q=q, limit=limit, offset=offset)
    return ProductList(
        items=[await _product_out(p, storage=storage, redis=redis) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/categories", response_model=CategoryList)
async def listar_categorias(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryList:
    rows = await services.listar_categorias(db)
    return CategoryList(items=[CategoryOut(type=t, count=c) for t, c in rows])


@router.get("/{product_id}", response_model=ProductOut)
async def detalhe_produto(
    product_id: uuid.UUID,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProductOut:
    try:
        product = await services.buscar_produto(db, product_id)
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return await _product_out(product, storage=storage, redis=redis)
```

> **A ordem das rotas importa.** `/categories` tem que ser declarada **antes** de `/{product_id}`, senão o FastAPI casa `categories` como `product_id` e devolve 422 (UUID inválido) em vez de a listagem. O legacy tem a mesma ordem pelo mesmo motivo.
>
> O parâmetro `category` que a rota tinha antes **some**: o legacy não o tem, e réplica exata é o alvo. Se alguma suíte do commerce o exercitava, ela some junto — registre isso.

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS, incluindo `test_products_parity.py` inteiro.

- [ ] **Step 7: Prove que o envelope é travado (constraint 11)**

Troque o `response_model=ProductList` por `list[ProductOut]` e devolva `items`. Rode `tests/test_products_parity.py -k envelope`. Confirme FAIL com `KeyError: 'total'` ou `TypeError`. Reaplique.

- [ ] **Step 8: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): serve the products catalog as an exact replica

Envelope with total/limit/offset, limit 1-100 defaulting to 20, q bounded
at 160, price as a string, 404 \"Product not found\", image_url presigned.
The legacy products route suite is ported and passes; the only adapted
assertions are the 403-vs-401 ones recorded in task B0.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B7: `reviews` e o cliente HTTP para `/auth/me`

`POST /products/{id}/reviews` grava o **nome** do autor junto com a review. O JWT carrega `sub`, `role`, `type`, `iat`, `exp`, `jti` — **não carrega `name`**. Pôr o nome no token o colocaria em todo header `Authorization`, que vai para log de acesso. Por isso a chamada HTTP.

**Files:**
- Create: `back-end/commerce-service/app/models/review.py`
- Create: `back-end/commerce-service/app/schemas/review.py`
- Create: `back-end/commerce-service/app/services/auth_client.py`
- Modify: `back-end/commerce-service/app/services/produtos.py`
- Modify: `back-end/commerce-service/app/routers/produtos.py`
- Modify: `back-end/commerce-service/app/config.py` (`auth_service_url`)
- Modify: `back-end/commerce-service/pyproject.toml` (`httpx` volta ao runtime)
- Modify: `back-end/docker-compose.yml`
- Create: `back-end/commerce-service/alembic/versions/<hash>_reviews.py`
- Test: `back-end/commerce-service/tests/test_products_parity.py`, `test_auth_client.py` (novo)

**Interfaces:**
- Produces:
  - `Review` (`reviews`): `id UUID PK`, `product_id UUID FK products.id ON DELETE CASCADE`, `user_id UUID`, `author String(120)`, `rating Integer` com CHECK 1–5, `comment String(2000)`, `created_at`
  - `ReviewIn{rating: int 1..5, comment: str ≤2000}`, `ReviewOut{id,author,rating,comment,created_at}`, `ReviewList{items,total,rating_avg,rating_count}`
  - `auth_client.get_me(raw_token: str) -> dict` — levanta `AuthServiceUnavailable`
  - `services.listar_reviews(db, product_id, *, limit, offset) -> tuple[list[Review], int]`
  - `services.criar_review(db, product_id, *, user_id, author, data) -> Review`

> **Nota de sequência:** a task 16 do bloco A tirou `httpx` do runtime do commerce porque nada em `app/` o importava. `auth_client.py` o importa de verdade. Devolvê-lo aqui é o comportamento certo, não um retrocesso.

- [ ] **Step 1: Porte os testes de review (Red)**

Traga de volta, para `tests/test_products_parity.py`, as classes de review que o Step 1 de B6 removeu (`TestListReviews`, `TestCreateReview` ou o nome que o legacy usa), com as mesmas adaptações: sem `/api`, `headers_for("student")`, 403 no lugar de 401.

O legacy resolve `author` de `user.name` (tem o usuário no banco). Aqui isso vira uma chamada HTTP, então acrescente o teste que trava a origem do nome:

```python
async def test_review_author_comes_from_the_auth_service(client, db_session, monkeypatch):
    """O JWT não carrega `name` — pôr o nome no token o colocaria em todo
    header Authorization, que vai para log de acesso."""
    produto = Product(name="Guia", type="apostila", price=Decimal("49.90"))
    db_session.add(produto)
    await db_session.commit()

    async def _me_falso(raw_token: str) -> dict:
        return {"id": str(uuid.uuid4()), "name": "Ana Souza", "email": "a@b.c", "role": "student"}

    monkeypatch.setattr("app.routers.produtos.get_me", _me_falso)

    response = await client.post(
        f"/products/{produto.id}/reviews",
        json={"rating": 5, "comment": "Excelente"},
        headers=headers_for("student"),
    )

    assert response.status_code == 201
    assert response.json()["author"] == "Ana Souza"


async def test_review_returns_503_when_auth_is_unreachable(client, db_session, monkeypatch):
    produto = Product(name="Guia", type="apostila", price=Decimal("49.90"))
    db_session.add(produto)
    await db_session.commit()

    async def _me_que_falha(raw_token: str) -> dict:
        raise AuthServiceUnavailable()

    monkeypatch.setattr("app.routers.produtos.get_me", _me_que_falha)

    response = await client.post(
        f"/products/{produto.id}/reviews",
        json={"rating": 5},
        headers=headers_for("student"),
    )
    assert response.status_code == 503
```

> **Constraint 14:** o alvo do monkeypatch é `app.routers.produtos.get_me`, o nome onde o **chamador** importa — `from app.services.auth_client import get_me` cria um nome novo no namespace do router. Remendar `app.services.auth_client.get_me` não afetaria essa cópia.

Crie também `tests/test_auth_client.py`, espelhando `chatbot-service/tests/test_diagnostico_client.py` (leia-o primeiro — é o padrão a copiar):

```python
async def test_get_me_forwards_the_students_bearer(monkeypatch):
    capturado = {}

    class _RespostaFalsa:
        status_code = 200

        def json(self):
            return {"id": "x", "name": "Ana", "email": "a@b.c", "role": "student"}

        def raise_for_status(self):
            pass

    class _ClienteFalso:
        def __init__(self, **kwargs):
            capturado["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            capturado["url"] = url
            capturado["headers"] = headers
            return _RespostaFalsa()

    monkeypatch.setattr("app.services.auth_client.httpx.AsyncClient", _ClienteFalso)

    resultado = await get_me("token-do-aluno")

    assert resultado["name"] == "Ana"
    assert capturado["headers"]["Authorization"] == "Bearer token-do-aluno"
    assert capturado["url"].endswith("/auth/me")
    assert capturado["timeout"] == 10.0


async def test_get_me_never_puts_the_raw_token_in_the_error(monkeypatch):
    """O token bruto não pode aparecer em corpo de erro nem em log."""
    class _ClienteQueFalha:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            raise httpx.ConnectError("recusado")

    monkeypatch.setattr("app.services.auth_client.httpx.AsyncClient", _ClienteQueFalha)

    with pytest.raises(AuthServiceUnavailable) as exc:
        await get_me("segredo-nao-pode-vazar")

    assert "segredo-nao-pode-vazar" not in str(exc.value)
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_products_parity.py tests/test_auth_client.py -v`

Expected: `ModuleNotFoundError: No module named 'app.services.auth_client'` e 404 nas rotas de review.

- [ ] **Step 3: Devolva `httpx` ao runtime e declare `auth_service_url`**

Em `pyproject.toml`, mova `"httpx>=0.28.0"` de `[dependency-groups].dev` de volta para `[project].dependencies`. `uv sync`.

Em `app/config.py`:

```python
    # Chamada serviço-a-serviço para resolver dados que o JWT não carrega:
    # `GET /auth/me` (nome do autor da review) e, a partir do bloco C,
    # `GET /auth/addresses/{id}` (snapshot de entrega no checkout).
    auth_service_url: str = "http://auth-users-service:8000"
```

Em `docker-compose.yml`, no bloco `commerce-service`:

```yaml
      AUTH_SERVICE_URL: http://auth-users-service:8000
```

e acrescente `auth-users-service` ao `depends_on` do commerce.

- [ ] **Step 4: Escreva o cliente**

Crie `back-end/commerce-service/app/services/auth_client.py`, espelhando `chatbot-service/app/services/diagnostico_client.py`:

```python
"""Cliente HTTP para o auth-users-service.

Espelha `chatbot-service/app/services/diagnostico_client.py`: repassa o
MESMO bearer do aluno, em vez de o commerce ter credencial própria. Assim a
autorização continua sendo do serviço de destino, e o commerce não vira um
principal com poderes que o aluno não tem.

O `raw_token` NUNCA vai para log nem para corpo de erro — ele é a credencial
viva de quem chamou.
"""

import httpx
from loguru import logger

from app.config import settings

_TIMEOUT_SECONDS = 10.0


class AuthServiceUnavailable(Exception):
    """auth-users-service inalcançável ou respondendo 5xx. Vira 503."""


async def get_me(raw_token: str) -> dict:
    """`GET /auth/me` — devolve `{id, name, email, role}`.

    O JWT carrega `sub`, `role`, `type`, `iat`, `exp`, `jti` e nada mais.
    `name` não está lá de propósito: pôr o nome no token o colocaria em todo
    header `Authorization`, que vai para log de acesso.
    """
    url = f"{settings.auth_service_url}/auth/me"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {raw_token}"})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        # Nem a exceção nem o log carregam o token — só a URL e o status.
        logger.warning("auth_client: /auth/me respondeu {}", exc.response.status_code)
        raise AuthServiceUnavailable("auth-users-service indisponível") from None
    except httpx.HTTPError:
        logger.warning("auth_client: /auth/me inalcançável em {}", url)
        raise AuthServiceUnavailable("auth-users-service indisponível") from None
```

> `raise ... from None` de propósito: `from exc` anexaria a exceção original ao traceback, e o `repr` de um `httpx.HTTPStatusError` inclui a requisição — com o header `Authorization`. Isso vaza o token para o log de erro do FastAPI.

- [ ] **Step 5: Escreva o model e o schema**

Crie `back-end/commerce-service/app/models/review.py`:

```python
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.ids import new_uuid


class Review(Base):
    """Avaliação de produto.

    Em inglês porque `products` é o agregado que ganhou cliente.

    `user_id` é FK lógica para o auth-users-service (banco diferente, sem FK
    física possível). `author` é o nome desnormalizado, resolvido via
    `GET /auth/me` no momento da criação — o JWT não carrega o nome.
    """

    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),)

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    author = Column(String(120), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(String(2000), nullable=False, default="", server_default=text("''"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

Crie `back-end/commerce-service/app/schemas/review.py` com `ReviewIn`, `ReviewOut` e `ReviewList` copiados de `legacy/app/modules/products/schemas.py` (eles já estão em inglês e não precisam de tradução).

Acrescente a `relationship` em `Product`:

```python
    reviews = relationship(
        "Review", back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
```

e `product = relationship("Product", back_populates="reviews")` em `Review`.

Registre `app.models.review` no `test_engine` do `conftest.py` (a lista de imports em `tests/conftest.py:19-21`), senão `Base.metadata.create_all` não cria a tabela e a suíte falha com "relation reviews does not exist".

- [ ] **Step 6: Escreva os serviços**

Em `app/services/produtos.py`:

```python
async def listar_reviews(
    db: AsyncSession, product_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Review], int]:
    # Valida que o produto existe (404 caso contrário) antes de listar.
    await buscar_produto(db, product_id)

    stmt = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count()).select_from(Review).where(Review.product_id == product_id)
        )
    ).scalar_one()
    return items, total


async def criar_review(
    db: AsyncSession,
    product_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    author: str,
    data: ReviewIn,
) -> Review:
    # Lock na linha do produto para que reviews concorrentes atualizem os
    # agregados desnormalizados atomicamente (regra 3 do CLAUDE.md). O
    # SELECT ... FOR UPDATE e o UPDATE dividem a transação da sessão e
    # commitam juntos; o lock vale até o commit.
    product = (
        await db.execute(select(Product).where(Product.id == product_id).with_for_update())
    ).scalar_one_or_none()
    if product is None:
        raise ProductNotFound()

    review = Review(
        product_id=product_id,
        user_id=user_id,
        author=author,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)

    new_count = product.rating_count + 1
    new_avg = (float(product.rating_avg) * product.rating_count + data.rating) / new_count
    product.rating_count = new_count
    product.rating_avg = round(new_avg, 2)

    await db.commit()
    await db.refresh(review)
    logger.info("products: review criada id={} product={}", review.id, product_id)
    return review
```

- [ ] **Step 7: Acrescente as duas rotas**

Em `app/routers/produtos.py`:

```python
@router.get("/{product_id}/reviews", response_model=ReviewList)
async def listar_reviews(
    product_id: uuid.UUID,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewList:
    """`rating_avg` e `rating_count` vêm do PRODUTO, não da página de reviews:
    são o agregado do catálogo inteiro, e a página é só um recorte. Trocar um
    pelo outro faria a nota cair conforme o usuário paginasse."""
    try:
        product = await services.buscar_produto(db, product_id)
        items, total = await services.listar_reviews(db, product_id, limit=limit, offset=offset)
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return ReviewList(
        items=[ReviewOut.model_validate(r) for r in items],
        total=total,
        rating_avg=float(product.rating_avg),
        rating_count=product.rating_count,
    )


@router.post(
    "/{product_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED
)
async def criar_review(
    product_id: uuid.UUID,
    payload: ReviewIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewOut:
    try:
        me = await get_me(user["raw_token"])
    except AuthServiceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de usuários indisponível",
        ) from exc

    try:
        review = await services.criar_review(
            db,
            product_id,
            user_id=uuid.UUID(user["sub"]),
            author=me["name"],
            data=payload,
        )
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc
    return ReviewOut.model_validate(review)
```

- [ ] **Step 8: Gere a migration, aplique, rode**

```bash
cd back-end && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "reviews table"
docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio**. Confirme que a revision traz o `CheckConstraint` de rating e o `ondelete="CASCADE"`.

- [ ] **Step 9: Prove que o lock trava (constraint 11)**

Tire o `.with_for_update()` de `criar_review`, rode o teste de review concorrente do arquivo portado (se o legacy tiver um; se não, escreva-o), confirme FAIL, reaplique.

- [ ] **Step 10: Commit (dois: o cliente e a feature)**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/services/auth_client.py \
        back-end/commerce-service/app/config.py back-end/commerce-service/pyproject.toml \
        back-end/commerce-service/uv.lock back-end/commerce-service/tests/test_auth_client.py \
        back-end/docker-compose.yml
git commit -m "feat(commerce): add an auth-users-service client that forwards the bearer

Mirrors chatbot-service/app/services/diagnostico_client.py: the student's
own token is forwarded, so authorization stays with the destination service
and commerce never becomes a principal with powers the student lacks. The
raw token never reaches a log or an error body — hence 'raise from None'.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): add product reviews with denormalized aggregates

rating_avg/rating_count live on the product and are updated under a row
lock, so a listing needs no per-row join. The author name comes from
GET /auth/me because the JWT deliberately does not carry it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B8: carrinho

Não existe no commerce. Porte inteiro de `legacy/app/modules/cart/`.

**Files:**
- Create: `back-end/commerce-service/app/models/carrinho.py`
- Create: `back-end/commerce-service/app/schemas/carrinho.py`
- Create: `back-end/commerce-service/app/services/carrinho.py`
- Create: `back-end/commerce-service/app/routers/carrinho.py`
- Modify: `back-end/commerce-service/app/main.py` (registrar o router)
- Create: `back-end/commerce-service/alembic/versions/<hash>_cart.py`
- Test: `back-end/commerce-service/tests/test_cart_parity.py` (portado de `legacy/tests/modules/cart/test_routes.py` **e** `test_services.py`)

**Interfaces:**
- Produces:
  - `Cart` (`carts`): `id UUID PK`, `user_id UUID UNIQUE`, `created_at`, `updated_at`
  - `CartItem` (`cart_items`): `id UUID PK`, `cart_id UUID FK ON DELETE CASCADE`, `product_id UUID`, `quantity Integer`, `created_at`, `updated_at`; `UNIQUE(cart_id, product_id)`; `CHECK(quantity > 0)`
  - `services.get_or_create_cart(db, user_id) -> Cart`
  - `services.montar_cart_out(db, cart_id) -> CartOut`
  - `services.obter_carrinho(db, user_id) -> CartOut`
  - `services.adicionar_item(db, user_id, data: CartItemIn) -> CartOut`
  - `services.remover_item(db, user_id, product_id, quantity: int | None) -> CartOut`
  - `CartProductNotFound`, `CartItemNotFound` em `app/exceptions.py`

- [ ] **Step 1: Porte os dois testes do legacy (Red)**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp legacy/tests/modules/cart/test_routes.py commerce-service/tests/test_cart_parity.py
cp legacy/tests/modules/cart/test_services.py commerce-service/tests/test_cart_services_parity.py
```

Adaptações: sem `/api`; `app.modules.cart.*` → `app.models.carrinho`/`app.services.carrinho`; `app.modules.products.models` → `app.models.produto`; fixtures de auth para `headers_for("student", sub=...)`; 401 → 403 em `TestAuthRequired` com o comentário de B0.

**Atenção ao ownership:** o legacy resolve o carrinho por `user.id` do objeto `User`. Aqui é `uuid.UUID(user["sub"])`. Os testes que criam dois usuários e conferem que um não vê o carrinho do outro precisam de dois `sub` diferentes em `headers_for`.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_cart_parity.py tests/test_cart_services_parity.py -v`

Expected: `ModuleNotFoundError` / 404 em todas as rotas.

- [ ] **Step 3: Porte model, schema, serviço e router**

Copie de `legacy/app/modules/cart/` para os quatro arquivos novos, com estas mudanças e **nenhuma outra**:
- `__tablename__ = "cart_carts"` → `"carts"`; `"cart_items"` fica.
- `from app.core.database import Base` → `from app.database import Base`; `from app.core.ids import new_uuid` → `from app.ids import new_uuid`.
- `from app.modules.products.models import Product` → `from app.models.produto import Product`.
- Todo `default=new_uuid` ganha `server_default=text("gen_random_uuid()")` ao lado (constraint 15).
- No router, `user: User = Depends(get_current_user)` → `user: dict = Depends(get_current_user)`, e `user.id` → `uuid.UUID(user["sub"])`.
- `get_session` → `get_db`; `app.core.media` → `app.services.media`; `app.core.storage` → `app.storage`; `app.core.redis_client` → `app.redis_client`.

Preserve **literalmente**:
- `POST /cart/items` responde **201**, não 200.
- `DELETE /cart/items/{product_id}` sem `quantity` remove o item inteiro; com `quantity` menor, decrementa.
- 404 `"Product not found"` no add, 404 `"Item not in cart"` no remove.
- `build_cart_out` **omite** o item cujo produto saiu do catálogo, em vez de 500.
- Os dois `with_for_update()` (na linha do carrinho e na do item).
- `subtotal` por item e `total`, os dois serializados como string.

Registre o router em `app/main.py` junto dos demais.

Registre `app.models.carrinho` no `test_engine` do `conftest.py`.

- [ ] **Step 4: Gere a migration, aplique, rode**

```bash
cd back-end && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "cart tables"
docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio**. Confirme que a revision traz `UNIQUE(cart_id, product_id)` e `CHECK(quantity > 0)` — o autogenerate às vezes perde `CheckConstraint` nomeado; se perdeu, acrescente à mão e refaça o sync-check.

- [ ] **Step 5: Prove que o 201 está travado (constraint 11)**

Troque `status_code=status.HTTP_201_CREATED` por 200 em `POST /cart/items`, rode o teste portado, confirme FAIL, reaplique. Esse 201 é uma das quatro divergências que a fase 1 mediu — se ele voltar a 200 sem nada quebrar, o teste portado não está fazendo seu trabalho.

- [ ] **Step 6: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): port the cart from the legacy monolith

Carts, items and the three routes, kept byte-identical: POST /cart/items
answers 201, DELETE without quantity removes the whole item, money is a
string, and an item whose product left the catalog is omitted rather than
raising. Both row locks come along — the cart is a shared resource.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B9: formas de pagamento

**Files:**
- Create: `back-end/commerce-service/app/models/pagamento.py`
- Create: `back-end/commerce-service/app/schemas/pagamento.py` (inclui o enum `PaymentMethodType`)
- Create: `back-end/commerce-service/app/services/pagamento.py`
- Create: `back-end/commerce-service/app/routers/pagamento.py`
- Modify: `back-end/commerce-service/app/main.py`
- Create: `back-end/commerce-service/alembic/versions/<hash>_payment_methods.py`
- Test: `back-end/commerce-service/tests/test_payment_methods_parity.py` (portado)

**Interfaces:**
- Produces: `PaymentMethod` (`payment_methods`) com as colunas de `legacy/app/modules/payment_methods/models.py`, os dois `CheckConstraint`, e as quatro rotas: `GET` (array puro, default primeiro), `POST` 201, `PATCH` só `is_default`, `DELETE` 204.

- [ ] **Step 1: Porte o teste (Red)**

```bash
cp legacy/tests/modules/payment_methods/test_routes.py \
   commerce-service/tests/test_payment_methods_parity.py
```

Mesmas adaptações de B6/B8.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_payment_methods_parity.py -v`

Expected: 404 em todas.

- [ ] **Step 3: Porte os quatro arquivos**

Mesmas substituições de import de B8. `__tablename__ = "payment_methods_methods"` → `"payment_methods"`.

Preserve **literalmente**:
- `model_config = ConfigDict(extra="forbid", ...)` em `PaymentMethodIn` — é o que rejeita PAN e CVV. **Não afrouxe.**
- Os dois `CheckConstraint` (tipo permitido e `char_length(card_last4) = 4`).
- `_require_fields_by_type`: cartão exige `card_last4`, `card_brand`, `cardholder_name`, `card_expiry`; PIX e boleto não.
- Ordenação `is_default DESC, created_at ASC` — o default vem primeiro.
- O primeiro método criado vira default sozinho.
- Ao apagar o default, o mais antigo restante é promovido.
- `GET` devolve **array puro**, sem envelope.

> **Isto é `/payment-methods`, não `/cart`.** Reproduzir a inconsistência é o trabalho (constraint 19): `/products` e `/cart` têm envelope, este não tem.

Acrescente o que o legacy **não** tem e o `CLAUDE.md` exige: paginação no `GET`? **Não.** O legacy não pagina, e réplica exata é o alvo — o conjunto é limitado por usuário e por natureza. Registre a decisão no relatório para que a revisão não a confunda com esquecimento.

Registre `app.models.pagamento` no `test_engine`.

- [ ] **Step 4: Migration, aplicar, rodar, sincronizar**

```bash
cd back-end && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "payment methods"
docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio**; os dois CHECK presentes na revision.

- [ ] **Step 5: Prove que `extra="forbid"` está travado (constraint 11)**

Escreva, se o teste portado não cobrir:

```python
async def test_a_full_card_number_is_rejected(client):
    response = await client.post(
        "/payment-methods",
        json={
            "type": "credit_card",
            "card_last4": "4242",
            "card_brand": "Visa",
            "cardholder_name": "ANA SOUZA",
            "card_expiry": "1230",
            "card_number": "4242424242424242",
            "cvv": "123",
        },
        headers=headers_for("student"),
    )
    assert response.status_code == 422
```

Troque `extra="forbid"` por `extra="ignore"`, rode, confirme que passa a aceitar (201), reaplique.

- [ ] **Step 6: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): port saved payment methods

Masked display data only — extra=\"forbid\" is what rejects a PAN or CVV,
and the two check constraints keep the shape honest at the database level.
GET returns a bare array with the default first: that is the contract,
inconsistent with /products and /cart on purpose.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B10: seed do catálogo

Sem catálogo em `commerce_db`, o marketplace abre vazio no dia do corte. O seed do legacy espelha `mock_marketplace.dart` e baixa as fotos para o MinIO em `products/seed-{i}.jpg`, gravando a **chave** em `image_url`.

**Files:**
- Create: `back-end/commerce-service/app/seeds/__init__.py`
- Create: `back-end/commerce-service/app/seeds/products.py`
- Modify: `Makefile`
- Test: `back-end/commerce-service/tests/test_products_seed.py` (portado de `legacy/tests/seeds/test_products_seed.py`)

**Interfaces:**
- Produces: `seed_products(db, *, storage: ObjectStorage | None = None, fetch_image=...) -> int` — devolve quantos produtos inseriu. Idempotente por `name`.
- Alvo `make services-seed`.

- [ ] **Step 1: Porte o teste (Red)**

```bash
cp legacy/tests/seeds/test_products_seed.py commerce-service/tests/test_products_seed.py
```

Adapte imports (`app.seeds.products`, `app.models.produto`). O teste do legacy já injeta um `fetch_image` falso — **é por isso que ele não vai à rede**. Confirme que a injeção sobreviveu ao porte; se o teste passar a baixar de verdade, você perdeu o parâmetro.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_products_seed.py -v`

Expected: `ModuleNotFoundError: No module named 'app.seeds'`.

- [ ] **Step 3: Porte o seed**

Copie `legacy/app/seeds/products.py` para `back-end/commerce-service/app/seeds/products.py`. Mudanças:
- `from app.core.database import SessionLocal` → `from app.database import async_session`
- `from app.modules.products.models import Product, Review` → `from app.models.produto import Product` e `from app.models.review import Review`
- `settings.MEDIA_MAX_UPLOAD_BYTES` → `settings.media_max_upload_bytes`
- `from app.core.storage import ObjectStorage` → `from app.storage import ObjectStorage`

**Não mude `SEED_PRODUCTS`.** Os seis produtos, os preços, os `type`/`subtype` e as reviews de amostra são o catálogo que o app mostra hoje com mocks — mudar um valor faz a tela do corte não bater com a de antes.

`_solid_png` fica: é o fallback stdlib para uma entrada futura sem `photo_url`, e o legacy o mantém pelo mesmo motivo.

- [ ] **Step 4: Acrescente o alvo de Makefile**

No `Makefile`, junto dos alvos `services-*`:

```makefile
services-seed: ## Seed the commerce catalog (idempotent; downloads photos into MinIO)
	cd $(BACK_ROOT) && $(COMPOSE) exec -T commerce-service uv run python -m app.seeds.products
```

e acrescente `services-seed` à linha `.PHONY` dos alvos de serviço.

- [ ] **Step 5: Rode o seed de verdade e confira**

```bash
cd back-end/commerce-service && uv run pytest -q
cd /home/elias/programming/fiap/estuda_app && make stack-up && make services-seed
cd back-end && docker compose exec -T postgres psql -U edu -d commerce_db -c \
  "SELECT name, type, price, image_url FROM products ORDER BY name;"
curl -s "localhost:8103/products" -H "Authorization: Bearer <token de aluno>" | head -c 400
```

Expected: seis produtos, `image_url` com a chave `products/seed-N.jpg` no banco, e a resposta HTTP trazendo `image_url` **como URL presignada** (começa com `http://` e traz `X-Amz-Signature`). Se vier a chave crua, `_product_out` não está sendo aplicado.

Rode `make services-seed` **duas vezes** e confirme que a contagem continua seis — idempotência.

- [ ] **Step 6: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/seeds/ back-end/commerce-service/tests/test_products_seed.py Makefile
git diff --staged
git commit -m "feat(commerce): port the catalog seed

Without it commerce_db has no catalog and the marketplace opens empty on
cutover day. The six products mirror mock_marketplace.dart, photos land in
MinIO under products/seed-N.jpg, and image_url stores the key. Idempotent
by product name.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task B11: portão do bloco B

**Files:** nenhum. Produz um relatório.

- [ ] **Step 1: As suítes portadas, contadas**

Run: `cd back-end/commerce-service && uv run pytest -q --tb=no`

Registre: total de testes, e quantos vieram de cada arquivo portado (`test_products_parity`, `test_cart_parity`, `test_cart_services_parity`, `test_payment_methods_parity`, `test_products_seed`, `test_media`, `test_storage`).

Compare com o legacy:

```bash
cd back-end/legacy && uv run pytest --collect-only -q \
  tests/modules/products/test_routes.py tests/modules/products/test_services.py \
  tests/modules/cart/ tests/modules/payment_methods/ \
  tests/seeds/test_products_seed.py tests/core/test_media.py tests/core/test_storage.py 2>/dev/null | tail -5
```

A diferença tem que ser **exatamente** os carve-outs declarados: `test_image_upload.py` (não portado), a metade de escrita de `test_storage.py`, e os testes de `validate_image_bytes`/`new_image_key` de `test_media.py`. Qualquer outro teste faltando é um buraco.

- [ ] **Step 2: Toda asserção adaptada, listada**

Junte os relatórios das tasks B0, B2, B6, B8 e B9 numa lista só, no formato:

```
arquivo:linha | asserção original | asserção atual | razão
```

Esta lista é a resposta à pergunta que a fase 4 vai fazer: "onde exatamente o commerce não é o legacy?"

- [ ] **Step 3: Frota verde**

Run: `make services-test && make services-lint`

Expected: PASS nos oito alvos.

- [ ] **Step 4: Sync-check dos cinco bancos**

```bash
cd back-end && grep -l compare_server_default */alembic/env.py | wc -l   # tem que dar 5
for s in auth-users-service learning-service commerce-service notification-service analytics-service; do
  echo "→ $s"
  docker compose exec -T $s uv run alembic upgrade head
  docker compose exec -T $s uv run alembic revision --autogenerate -m "sync check $s"
done
```

Cada revision gerada tem que estar vazia. Apague as cinco.

- [ ] **Step 5: Prove as rotas contra o serviço de pé**

Com o stack up e um token de aluno em mãos:

```bash
TOKEN="<bearer de aluno>"
curl -s -H "Authorization: Bearer $TOKEN" "localhost:8103/products?limit=2" | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" "localhost:8103/products/categories" | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" "localhost:8103/cart" | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" "localhost:8103/payment-methods" | python -m json.tool
```

Confira, um a um, contra a tabela "Rotas que o app consome" do spec: envelope onde tem que ter, array puro onde tem que ser, `price` como string, `id` como string UUID, `image_url` presignada.

E contra o legacy, lado a lado:

```bash
curl -s -H "Authorization: Bearer <token do legacy>" "localhost:8001/api/products?limit=2" | python -m json.tool
```

As **chaves** dos dois JSON têm que ser idênticas. Os valores não (bancos diferentes).

- [ ] **Step 6: Relate**

Relatório com: contagem de testes portados vs. legacy, a lista de asserções adaptadas, o resultado dos sync-checks, e o diff de chaves entre commerce e legacy nas quatro rotas. Nada a commitar.

---

## Notas de sequência para os outros blocos

- **B7** devolveu `httpx` ao runtime do commerce e criou `auth_client.py` com `get_me`. O **bloco C** acrescenta `get_address` ao mesmo arquivo — não crie um segundo cliente.
- **B4** deixou `pedido_itens.produto_id` como UUID apontando para `products.id`. O **bloco C** renomeia a coluna para `product_id` junto com o resto da tabela.
- **B2** deu ao commerce o `presigned_image_url`. O **bloco C** o aplica também em `order_items`, que carrega o snapshot de imagem.
- **B0** registrou a divergência 403-vs-401. Ela vale para as rotas do bloco C também — não a redescubra.
