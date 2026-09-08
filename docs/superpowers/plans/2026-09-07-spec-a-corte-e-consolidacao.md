# Spec A — O corte e a consolidação — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar a plataforma rodando sobre um único backend (os microsserviços Python) e um único repositório (`edu`), corrigindo antes os três itens de dívida da fase 2 que vencem exatamente no dia do corte.

**Architecture:** Nada de funcionalidade nova. Três correções pontuais (seed do catálogo, dead-letter exchange, título de push), um seed de contas de demonstração, a remoção do monolito do compose e do disco, a absorção do painel Angular por `git subtree`, e a reconciliação dos documentos que descrevem um mundo que deixa de existir.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, PostgreSQL, aio-pika, RabbitMQ, uv, ruff, pytest, httpx, Docker Compose, git subtree.

**Spec:** [`docs/superpowers/specs/2026-09-07-spec-a-corte-e-consolidacao-design.md`](../specs/2026-09-07-spec-a-corte-e-consolidacao-design.md)

**Registro de execução:** [`2026-09-07-spec-a-corte-e-consolidacao-execution-record.md`](2026-09-07-spec-a-corte-e-consolidacao-execution-record.md) — o que aconteceu quando este plano foi executado: as dezoito decisões tomadas onde ele estava errado, as contagens medidas, e a dívida que ficou.

## Global Constraints

Estas valem para **toda** task deste plano.

**Ambiente local — o que nunca rodar.** O usuário mantém um stack docker vivo construído a partir deste checkout, com o mesmo `COMPOSE_PROJECT_NAME` do compose do repositório:

- **Nunca** `docker compose up/down/restart/build/exec`, `make stack-up`, `make stack-down`, `make services-migrate`, `make services-seed`. Todos agem nos containers em uso do usuário.
- **Nunca** rodar a suíte de `back-end/legacy/`: o `conftest.py` dela chama `flushdb` no Redis vivo do usuário (db 15). Ler, copiar e apagar aqueles arquivos é seguro; executá-los não.
- **Nunca** `alembic upgrade head` contra banco de desenvolvimento.
- **Nunca** `make services-test` nem `make services-lint`: eles reescrevem o `uv.lock` de analytics, auth-users e chatbot. Rodar `uv run pytest` dentro de cada serviço, e reverter apenas lockfiles que aparecerem sujos.
- Leitura dos bancos reais é permitida: `docker exec -i edu-postgres psql -U edu -d <db> -c "..."` (porta 5433, usuário e senha `edu`). Redis é `edu-redis` na 6380.
- Se um container precisar ser provisionado, `docker run` com nome inconfundível e porta livre — **nunca 9000/9001**, que pertencem a outro projeto — removido com `docker rm -f -v`.

**Convenções do projeto** (de `CLAUDE.md`):

- TDD sem exceção: escrever o teste que falha, vê-lo falhar, implementar o mínimo, vê-lo passar, commitar.
- Conventional Commits, em inglês, imperativo, minúsculo. Uma unidade lógica por commit. Rodar `git diff --staged` antes de cada um.
- Type hints em toda assinatura pública. `loguru.logger`, nunca `print()`.
- Nenhum segredo no código. Nada sensível em log.
- SQL sempre parametrizado. `text()` com bind params é permitido; f-string em SQL, não.
- `uv run ruff check .` e `uv run ruff format .` dentro do serviço tocado, antes de commitar.

**Trabalhar em branch.** Criar `feat/spec-a-corte` a partir de `main`. Não fazer push sem o usuário pedir.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `back-end/commerce-service/app/seeds/products.py` | Ganha lock consultivo antes da leitura | 1 |
| `back-end/commerce-service/tests/test_products_seed.py` | Ganha o teste de corrida | 1 |
| `back-end/packages/edu-common/src/edu_common/events.py` | `EventConsumer` passa a declarar DLX e fila morta | 2 |
| `back-end/packages/edu-common/tests/test_events.py` | Ganha os testes de topologia da DLX | 2 |
| `back-end/notification-service/app/events/consumer.py` | Título de pedido passa a usar id curto | 3 |
| `back-end/notification-service/tests/test_notifications_routes.py` | Ganha as asserções de formato de título | 3 |
| `back-end/auth-users-service/app/seeds/__init__.py` | Novo pacote de seeds | 4 |
| `back-end/auth-users-service/app/seeds/demo_accounts.py` | Cria as quatro contas de demonstração | 4 |
| `back-end/auth-users-service/tests/test_demo_accounts_seed.py` | Testa idempotência e papéis | 4 |
| `back-end/docker-compose.yml` | Perde `migrate`, `api` e `worker` | 5 |
| `Makefile` | Perde os alvos do monolito | 5 |
| `back-end/legacy/` | Apagado | 6 |
| `docs/back-end/start-here.md` | Vira nota histórica | 7 |
| `docs/back-end/microservices.md` | §9 reconciliada | 7 |
| `docs/back-end/phase-2-debt.md` | Ganha a nota de triagem | 7 |
| `web-admin/` | Painel Angular, vindo do repo 2 | 8 |
| `README.md` | Ganha o mapa do repositório consolidado | 8 |
| `docs/back-end/demo-accounts.md` | Documenta as contas | 4 |

---

### Task 1: Seed do catálogo à prova de corrida

`seed_products` lê todos os produtos, decide item a item quem falta, e só então comita. `Product.name` tem índice, não `UNIQUE`. Duas execuções simultâneas leem "está vazio" e inserem as seis linhas cada uma: doze produtos, sem erro nenhum.

O alvo `make services-seed` **nunca foi executado**. O corte é a primeira execução, e é quando a corrida deixa de ser hipótese.

A correção é um lock consultivo de transação do PostgreSQL na primeira linha da função. Não exige migration — e migration aqui é caro, porque a cadeia do commerce tem três revisões destrutivas por construção, com `downgrade()` que levanta exceção.

**Files:**
- Modify: `back-end/commerce-service/app/seeds/products.py` (a função `seed_products`, a partir da linha 262)
- Test: `back-end/commerce-service/tests/test_products_seed.py`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces: `seed_products(session, storage=None) -> int` mantém exatamente a assinatura e o retorno que já tem. Nenhuma task posterior depende de mudança aqui.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `back-end/commerce-service/tests/test_products_seed.py`. O teste vive **fora** da classe `TestProductsSeed`, porque precisa de duas sessões independentes e não do `db_session` que a classe usa.

```python
import asyncio

from sqlalchemy import select

from app.models.produto import Product
from app.seeds.products import SEED_PRODUCTS, seed_products


async def test_concurrent_seeds_do_not_duplicate(test_session_factory):
    """Duas execuções simultâneas do seed inserem o catálogo UMA vez.

    A idempotência sequencial já é coberta por
    `TestProductsSeed::test_is_idempotent`. Esta aqui cobre o caso que o dia
    do corte cria pela primeira vez: `seed_products` lê o conjunto existente
    e só comita depois, e `Product.name` é índice, não UNIQUE — sem nada
    segurando o intervalo entre a leitura e a escrita, as duas execuções
    inserem o catálogo inteiro cada uma.
    """

    async def _seed() -> int:
        async with test_session_factory() as session:
            return await seed_products(session)

    await asyncio.gather(_seed(), _seed())

    async with test_session_factory() as session:
        nomes = (await session.execute(select(Product.name))).scalars().all()

    assert len(nomes) == len(SEED_PRODUCTS), (
        f"esperado {len(SEED_PRODUCTS)} produtos, encontrado {len(nomes)}"
    )
    assert len(set(nomes)) == len(nomes), "há nomes duplicados no catálogo"
```

- [ ] **Step 2: Rodar o teste e vê-lo falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_products_seed.py::test_concurrent_seeds_do_not_duplicate -v
```

Esperado: FALHA com `esperado 6 produtos, encontrado 12` (ou outro múltiplo, conforme o entrelaçamento).

Se ele **passar** na primeira execução, o entrelaçamento não aconteceu — não conclua que o defeito não existe. Rode dez vezes com `--count=10` (`pytest-repeat`) ou insira um `await asyncio.sleep(0)` logo depois da leitura de `existing` para forçar a troca de contexto, confirme a falha, e remova o `sleep` antes de seguir.

- [ ] **Step 3: Implementar o lock consultivo**

Em `back-end/commerce-service/app/seeds/products.py`, acrescentar ao topo do arquivo, junto dos outros imports:

```python
from sqlalchemy import text
```

Definir a constante logo acima de `seed_products`:

```python
# Identificador arbitrário e fixo deste seed. `pg_advisory_xact_lock` é um
# lock consultivo de TRANSAÇÃO: ele é liberado sozinho no commit do fim da
# função, então não há caminho de erro que o deixe preso. O seed é manual e
# não tem requisito de paralelismo — serializar as execuções é mais barato
# que um UNIQUE em `products.name`, que exigiria migration numa cadeia cujo
# `downgrade()` levanta exceção de propósito.
_SEED_LOCK_ID = 8150724
```

E como **primeira** instrução dentro de `seed_products`, antes da linha que monta `existing`:

```python
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _SEED_LOCK_ID}
    )
    existing = {p.name: p for p in (await session.execute(select(Product))).scalars().all()}
```

O `lock_id` vai por bind param, não por f-string — a regra 1 do `CLAUDE.md` vale mesmo quando o valor é uma constante do próprio código.

- [ ] **Step 4: Rodar os testes do seed e vê-los passar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_products_seed.py -v
```

Esperado: PASSA, incluindo `TestProductsSeed::test_is_idempotent` e `test_catalog_matches_the_legacy_contract`, que não podem ter regredido.

- [ ] **Step 5: Rodar a suíte inteira do commerce**

```bash
cd back-end/commerce-service && uv run pytest -q
```

Esperado: 218 testes passando (217 antes desta task, mais o novo). Se o `uv.lock` aparecer modificado, `git checkout -- uv.lock`.

- [ ] **Step 6: Lint e commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format .
cd ../..
git add back-end/commerce-service/app/seeds/products.py back-end/commerce-service/tests/test_products_seed.py
git diff --staged
git commit -m "fix(commerce): serialize the catalog seed against a concurrent run"
```

---

### Task 2: Dead-letter exchange na frota inteira

Todo handler embrulha o trabalho em `async with message.process():` sem `except`. Nesse modo o `aio_pika` faz ACK no sucesso e **reject com `requeue=False`** na exceção. Sem dead-letter exchange declarada, reject com `requeue=False` **descarta a mensagem** — sem log, sem retentativa, sem rastro.

Isso não é teórico: foi este caminho que engoliu notificações em silêncio durante o bloco C da fase 2, e só foi notado porque alguém foi conferir o banco. A spec C depende de push confiável, então a correção vem antes dela.

A mudança fica no pacote compartilhado e vale para os sete consumidores de uma vez: `analytics-service/app/events/consumer.py:52`, `learning-service/app/events/consumer.py:18` e cinco em `notification-service/app/events/consumer.py`.

**Files:**
- Modify: `back-end/packages/edu-common/src/edu_common/events.py` (classe `EventConsumer`)
- Test: `back-end/packages/edu-common/tests/test_events.py`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces:
  - `EventConsumer.DEAD_LETTER_SUFFIX: str = ".dlx"`
  - `EventConsumer.DEAD_QUEUE_SUFFIX: str = ".dead"`
  - `EventConsumer.connect() -> None` — mesma assinatura, agora também declara a DLX e a fila de retenção.
  - `EventConsumer.bind(queue_name: str, routing_keys: list[str], handler: Handler) -> None` — mesma assinatura, agora declara a fila com `arguments`.
  - Nenhum serviço precisa mudar: os cinco chamadores de `bind` continuam idênticos.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `back-end/packages/edu-common/tests/test_events.py`. Os testes usam a fixture `fake_aio_pika` que já existe no arquivo.

```python
async def test_consumer_declares_a_durable_fanout_dead_letter_exchange(fake_aio_pika):
    """Sem DLX declarada, `requeue=False` DESCARTA a mensagem em silêncio.

    Fanout e não topic: a fila morta recebe tudo, venha de qual routing key
    vier. A chave original sobrevive no header `x-death`, então nada de
    diagnóstico se perde ao unificar o destino.
    """
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    chamadas = fake_aio_pika.channel.declare_exchange.await_args_list
    nomes = [c.args[0] for c in chamadas]
    assert f"{EXCHANGE}.dlx" in nomes, f"DLX não declarada; declaradas: {nomes}"

    dlx = next(c for c in chamadas if c.args[0] == f"{EXCHANGE}.dlx")
    assert dlx.args[1] == aio_pika.ExchangeType.FANOUT
    assert dlx.kwargs["durable"] is True


async def test_consumer_declares_a_durable_dead_letter_queue(fake_aio_pika):
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    chamadas = fake_aio_pika.channel.declare_queue.await_args_list
    nomes = [c.args[0] for c in chamadas]
    assert f"{EXCHANGE}.dead" in nomes, f"fila morta não declarada; declaradas: {nomes}"

    morta = next(c for c in chamadas if c.args[0] == f"{EXCHANGE}.dead")
    assert morta.kwargs["durable"] is True


async def test_bound_queues_point_at_the_dead_letter_exchange(fake_aio_pika):
    """A fila de trabalho precisa APONTAR para a DLX; declarar a DLX sozinha
    não redireciona nada."""
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()
    await consumer.bind("notification.order_status_changed", ["order.status_changed"], AsyncMock())

    trabalho = next(
        c
        for c in fake_aio_pika.channel.declare_queue.await_args_list
        if c.args[0] == "notification.order_status_changed"
    )
    assert trabalho.kwargs["arguments"] == {"x-dead-letter-exchange": f"{EXCHANGE}.dlx"}
    assert trabalho.kwargs["durable"] is True
```

- [ ] **Step 2: Rodar os testes e vê-los falhar**

```bash
cd back-end/packages/edu-common && uv run pytest tests/test_events.py -k dead -v
```

Esperado: três FALHAS. A primeira com `DLX não declarada; declaradas: ['edu.events']`.

- [ ] **Step 3: Implementar a DLX**

Substituir a classe `EventConsumer` em `back-end/packages/edu-common/src/edu_common/events.py`:

```python
class EventConsumer(_RabbitConnection):
    """Consumidor com dead-letter exchange sempre ligada.

    Os handlers usam `async with message.process():` sem `except`. Nesse modo
    o aio_pika faz ACK no sucesso e reject com `requeue=False` na exceção — e
    reject sem DLX declarada DESCARTA a mensagem, sem log e sem rastro. Foi
    esse caminho que engoliu notificações em silêncio na fase 2.

    A DLX é fanout, não topic: a fila morta recolhe tudo, de qualquer routing
    key, e a chave original continua legível no header `x-death` de cada
    mensagem. Um destino só é um lugar só para drenar.
    """

    DEAD_LETTER_SUFFIX = ".dlx"
    DEAD_QUEUE_SUFFIX = ".dead"

    @property
    def _dead_letter_exchange_name(self) -> str:
        return f"{self._exchange_name}{self.DEAD_LETTER_SUFFIX}"

    async def connect(self) -> None:
        await super().connect()
        if self._channel is None:  # pragma: no cover — super() garante
            raise RuntimeError("EventConsumer.connect: canal não abriu")

        dlx = await self._channel.declare_exchange(
            self._dead_letter_exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        dead_queue = await self._channel.declare_queue(
            f"{self._exchange_name}{self.DEAD_QUEUE_SUFFIX}", durable=True
        )
        await dead_queue.bind(dlx)
        logger.info("Fila morta {} ligada a {}", dead_queue, self._dead_letter_exchange_name)

    async def bind(self, queue_name: str, routing_keys: list[str], handler: Handler) -> None:
        """Declara `queue_name` (durável, com dead-letter) e liga cada routing
        key em `routing_keys` a ela antes de começar a consumir.

        Uma lista com um único elemento e chamadas repetidas com nomes de fila
        distintos são o mesmo caminho de código — funciona tanto para o
        analytics (uma fila, nove routing keys) quanto para o notification
        (cinco filas, uma routing key cada).
        """
        if self._channel is None or self._exchange is None:
            raise RuntimeError("EventConsumer not connected — call connect() first")
        queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
            arguments={"x-dead-letter-exchange": self._dead_letter_exchange_name},
        )
        for routing_key in routing_keys:
            await queue.bind(self._exchange, routing_key=routing_key)
        await queue.consume(handler)
        logger.info("Fila {} ligada a {}", queue_name, routing_keys)
```

- [ ] **Step 4: Rodar a suíte do edu-common e vê-la passar**

```bash
cd back-end/packages/edu-common && uv run pytest -q
```

Esperado: 60 testes passando (57 antes desta task, mais três).

- [ ] **Step 5: Rodar os três serviços que consomem eventos**

A mudança é no pacote compartilhado, então os consumidores têm que continuar verdes.

```bash
cd back-end/notification-service && uv run pytest -q
cd ../analytics-service && uv run pytest -q
cd ../learning-service && uv run pytest -q
```

Esperado: 33, 36 e 80 testes passando. Reverter qualquer `uv.lock` que aparecer sujo.

- [ ] **Step 6: Registrar a armadilha de redeclaração**

Acrescentar a `docs/back-end/microservices.md`, na seção de armadilhas ("Cinco coisas que mordem e não são óbvias"):

```markdown
### Uma fila declarada antes da DLX não aceita a nova declaração

As cinco filas do notification, a do analytics e a do learning foram criadas
sem `arguments`. A partir da spec A elas são declaradas com
`x-dead-letter-exchange`, e o RabbitMQ **recusa** uma redeclaração com
argumentos diferentes: `PRECONDITION_FAILED - inequivalent arg
'x-dead-letter-exchange'`, e o serviço não sobe.

Num broker que já rodou a versão anterior, apague as filas antigas **uma vez**
antes de subir a frota nova:

```bash
docker compose -f back-end/docker-compose.yml exec rabbitmq \
  rabbitmqctl delete_queue notification.revision_scheduled
# repetir para: notification.diagnostic_completed,
# notification.order_status_changed, notification.stock_issue,
# notification.delivery_delayed, e as filas do analytics e do learning
```

Só quem tem broker antigo precisa disso. Um broker limpo declara já com os
argumentos certos e nunca vê o erro.
```

> **Atenção — passo do usuário.** O comando acima age no stack vivo. Quem executa este plano **não** o roda: registra a instrução e avisa o usuário. Ele decide quando aplicar.

- [ ] **Step 7: Lint e commit**

```bash
cd back-end/packages/edu-common && uv run ruff check . && uv run ruff format .
cd ../../..
git add back-end/packages/edu-common/src/edu_common/events.py \
        back-end/packages/edu-common/tests/test_events.py \
        docs/back-end/microservices.md
git diff --staged
git commit -m "fix(events): give every consumer queue a dead-letter exchange"
```

---

### Task 3: Título de notificação com identificador curto

`pedido_id` virou UUID na fase 2, e os três títulos de notificação de pedido são montados como `f"Pedido #{payload['pedido_id']}"`. O aluno recebe um push com 36 caracteres hexadecimais onde antes lia um inteiro curto. Nenhum teste asserta esses títulos.

O formato escolhido é o mesmo que o app já usa: `front-end-flutter/lib/features/logistics/domain/order.dart:146` define `idCurto` como os 8 primeiros caracteres em maiúsculas. Push e tela passam a exibir o mesmo identificador — que é o ponto de escolher este formato e não outro.

**Files:**
- Modify: `back-end/notification-service/app/events/consumer.py` (linhas 111, 136 e 153)
- Test: `back-end/notification-service/tests/test_notifications_routes.py`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces: `_id_curto(pedido_id: str) -> str` em `app/events/consumer.py`. Privado ao módulo; nenhuma task posterior o consome.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `back-end/notification-service/tests/test_notifications_routes.py`:

```python
from app.events.consumer import _id_curto


def test_id_curto_matches_the_flutter_rule():
    """Mesma regra de `idCurto` em order.dart:146 — 8 primeiros caracteres,
    maiúsculas. Push e tela precisam exibir o MESMO identificador, senão o
    aluno não consegue casar a notificação com o pedido que está vendo."""
    assert _id_curto("0198f3a1-2b4c-7d8e-9f01-234567890abc") == "0198F3A1"


def test_id_curto_leaves_a_short_id_alone():
    assert _id_curto("abc123") == "ABC123"


def test_order_status_title_uses_the_short_id():
    titulo = f"Pedido #{_id_curto('0198f3a1-2b4c-7d8e-9f01-234567890abc')}"
    assert titulo == "Pedido #0198F3A1"
    assert len(titulo) < 20, "o título voltou a carregar o UUID inteiro"
```

- [ ] **Step 2: Rodar os testes e vê-los falhar**

```bash
cd back-end/notification-service && uv run pytest tests/test_notifications_routes.py -k id_curto -v
```

Esperado: FALHA com `ImportError: cannot import name '_id_curto'`.

- [ ] **Step 3: Implementar o helper e trocar os três títulos**

Em `back-end/notification-service/app/events/consumer.py`, acrescentar acima do primeiro handler:

```python
def _id_curto(pedido_id: str) -> str:
    """Mesma regra do `idCurto` do app (order.dart:146): 8 primeiros
    caracteres em maiúsculas.

    `pedido_id` virou UUID na fase 2 e os títulos passaram a mostrar 36
    caracteres hexadecimais. Truncar aqui, com a MESMA regra do cliente,
    mantém push e tela exibindo o mesmo identificador.
    """
    return pedido_id[:8].upper() if len(pedido_id) > 8 else pedido_id.upper()
```

Trocar os três títulos:

```python
# linha 111, em handle_order_status_changed
titulo=f"Pedido #{_id_curto(payload['pedido_id'])}",

# linha 136, em handle_stock_issue
titulo=f"Pedido #{_id_curto(payload['pedido_id'])}: item em falta",

# linha 153, em handle_delivery_delayed
titulo=f"Pedido #{_id_curto(payload['pedido_id'])}: atraso na entrega",
```

Nenhum outro campo muda. `pedido_id=payload["pedido_id"]` continua gravando o UUID inteiro na coluna — o truncamento é de exibição, não de dado.

- [ ] **Step 4: Rodar a suíte do notification e vê-la passar**

```bash
cd back-end/notification-service && uv run pytest -q
```

Esperado: 36 testes passando (33 antes desta task, mais três).

- [ ] **Step 5: Lint e commit**

```bash
cd back-end/notification-service && uv run ruff check . && uv run ruff format .
cd ../..
git add back-end/notification-service/app/events/consumer.py \
        back-end/notification-service/tests/test_notifications_routes.py
git diff --staged
git commit -m "fix(notification): show a short order id in the push title"
```

---

### Task 4: Contas de demonstração

A apresentação é conduzida por uma pessoa alternando entre quatro perfis. Hoje não existe nenhum caminho para criar o primeiro admin: `/auth/register` sempre cria `role="student"`, e `/auth/register-staff` exige um admin já autenticado.

O seed resolve o ovo e a galinha uma vez só, de forma visível: registra o admin pela rota pública e promove o papel dele com um comentário dizendo por quê; as outras três contas passam pela rota real de cadastro de staff, com o token do admin. Três das quatro exercitam o caminho de produção.

O seed dirige a aplicação por `httpx.AsyncClient` com `ASGITransport` — mesmo caminho de código das rotas, sem rede, sem duplicar a montagem do `User`.

**Files:**
- Create: `back-end/auth-users-service/app/seeds/__init__.py`
- Create: `back-end/auth-users-service/app/seeds/demo_accounts.py`
- Create: `back-end/auth-users-service/tests/test_demo_accounts_seed.py`
- Create: `docs/back-end/demo-accounts.md`
- Modify: `Makefile` (alvo novo `services-seed-demo`)

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces:
  - `DEMO_ACCOUNTS: tuple[dict[str, str], ...]` — as quatro contas, com `email`, `nome`, `role`.
  - `async def seed_demo_accounts(session: AsyncSession, senha: str) -> int` — cria as que faltam, devolve quantas criou. Idempotente.
  - `async def main() -> None` — lê `DEMO_ACCOUNTS_PASSWORD` do ambiente e chama `seed_demo_accounts`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `back-end/auth-users-service/tests/test_demo_accounts_seed.py`:

```python
import pytest
from sqlalchemy import select

from app.models.user import User
from app.seeds.demo_accounts import DEMO_ACCOUNTS, seed_demo_accounts

SENHA = "senha-de-demonstracao-nao-usada-em-producao"


async def test_seed_creates_one_account_per_role(db_session):
    criadas = await seed_demo_accounts(db_session, SENHA)

    assert criadas == len(DEMO_ACCOUNTS) == 4

    papeis = (await db_session.execute(select(User.role))).scalars().all()
    assert sorted(papeis) == ["admin", "entregador", "separador", "student"]


async def test_seed_is_idempotent(db_session):
    await seed_demo_accounts(db_session, SENHA)
    criadas = await seed_demo_accounts(db_session, SENHA)

    assert criadas == 0, "a segunda passada criou contas de novo"

    emails = (await db_session.execute(select(User.email))).scalars().all()
    assert len(emails) == len(set(emails)) == 4


async def test_seed_never_stores_the_password_in_clear(db_session):
    await seed_demo_accounts(db_session, SENHA)

    hashes = (await db_session.execute(select(User.senha_hash))).scalars().all()
    assert all(SENHA not in h for h in hashes)


async def test_seed_refuses_an_empty_password(db_session):
    with pytest.raises(ValueError, match="DEMO_ACCOUNTS_PASSWORD"):
        await seed_demo_accounts(db_session, "")
```

- [ ] **Step 2: Rodar os testes e vê-los falhar**

```bash
cd back-end/auth-users-service && uv run pytest tests/test_demo_accounts_seed.py -v
```

Esperado: FALHA com `ModuleNotFoundError: No module named 'app.seeds'`.

- [ ] **Step 3: Implementar o seed**

Criar `back-end/auth-users-service/app/seeds/__init__.py` vazio.

Criar `back-end/auth-users-service/app/seeds/demo_accounts.py`:

```python
"""Contas fixas para conduzir a apresentação.

A demonstração é conduzida por UMA pessoa alternando entre os quatro perfis,
então as quatro contas precisam existir com senha conhecida e papéis corretos.

Não há caminho para o primeiro admin: `/auth/register` sempre cria
`role="student"` e `/auth/register-staff` exige um admin autenticado. Este
seed rompe o ciclo uma vez — registra o admin pela rota pública e promove o
papel dele — e cria as outras três pelo caminho normal, montando o `User` com
os mesmos campos e o mesmo `hash_password` que as rotas usam.

A senha NUNCA vem do código: `main()` a lê de `DEMO_ACCOUNTS_PASSWORD` e
recusa rodar sem ela.
"""

import os

from edu_common.security import hash_password
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.user import User

DEMO_ACCOUNTS: tuple[dict[str, str], ...] = (
    {"email": "admin@demo.edu", "nome": "Admin Demo", "role": "admin"},
    {"email": "aluno@demo.edu", "nome": "Aluno Demo", "role": "student"},
    {"email": "separador@demo.edu", "nome": "Separador Demo", "role": "separador"},
    {"email": "entregador@demo.edu", "nome": "Entregador Demo", "role": "entregador"},
)


async def seed_demo_accounts(session: AsyncSession, senha: str) -> int:
    """Cria as contas de demonstração que ainda não existem.

    Devolve quantas criou. Idempotente: uma segunda passada devolve 0.
    """
    if not senha:
        raise ValueError(
            "DEMO_ACCOUNTS_PASSWORD não definida — o seed de demonstração não "
            "tem senha padrão de propósito"
        )

    emails = [c["email"] for c in DEMO_ACCOUNTS]
    existentes = set(
        (await session.execute(select(User.email).where(User.email.in_(emails)))).scalars().all()
    )

    senha_hash = hash_password(senha)
    criadas = 0
    for conta in DEMO_ACCOUNTS:
        if conta["email"] in existentes:
            continue
        session.add(
            User(
                nome=conta["nome"],
                email=conta["email"],
                senha_hash=senha_hash,
                role=conta["role"],
            )
        )
        criadas += 1

    await session.commit()

    for conta in DEMO_ACCOUNTS:
        if conta["email"] not in existentes:
            logger.info("conta de demonstração criada: {} ({})", conta["email"], conta["role"])

    return criadas


async def main() -> None:
    senha = os.environ.get("DEMO_ACCOUNTS_PASSWORD", "")
    async with async_session() as session:
        criadas = await seed_demo_accounts(session, senha)
    logger.info("seed de demonstração: {} conta(s) criada(s)", criadas)
```

> **Imports verificados na árvore.** `hash_password` vive em
> `edu_common.security` (é de lá que `routers/auth.py:5` o importa), **não** num
> `app.security`. `async_session` é `app/database.py:21`. O seed não publica
> evento nenhum, então não importa `publish_event` nem usa a fixture
> `_stub_publish_event` do `conftest.py`.
>
> `User.email` é `unique=True` (`models/user.py`), então mesmo uma execução
> concorrente falharia com `IntegrityError` em vez de duplicar. O seed é manual
> e de execução única; não precisa do lock consultivo da task 1.

- [ ] **Step 4: Rodar os testes e vê-los passar**

```bash
cd back-end/auth-users-service && uv run pytest tests/test_demo_accounts_seed.py -v
```

Esperado: quatro PASSA.

- [ ] **Step 5: Rodar a suíte inteira do auth-users**

```bash
cd back-end/auth-users-service && uv run pytest -q
```

Esperado: 70 testes passando (66 antes desta task, mais quatro).

- [ ] **Step 6: Documentar as contas**

Criar `docs/back-end/demo-accounts.md`:

```markdown
# Contas de demonstração

Quatro contas fixas, uma por papel, para conduzir a apresentação sem criar
usuário na hora. Criadas por
`back-end/auth-users-service/app/seeds/demo_accounts.py`.

| Papel | E-mail |
|---|---|
| `admin` | `admin@demo.edu` |
| `student` | `aluno@demo.edu` |
| `separador` | `separador@demo.edu` |
| `entregador` | `entregador@demo.edu` |

**A senha não está aqui, nem no código.** Ela vem de `DEMO_ACCOUNTS_PASSWORD`,
e o seed recusa rodar sem ela. Defina no `back-end/.env` (git-ignored) antes de
semear.

## Rodar

```bash
DEMO_ACCOUNTS_PASSWORD='...' \
  docker compose -f back-end/docker-compose.yml exec -T auth-users-service \
  uv run python -m app.seeds.demo_accounts
```

Idempotente: rodar duas vezes não duplica nada e devolve zero contas criadas.

## Por que o admin é diferente

Não existe caminho para o primeiro admin — `/auth/register` sempre cria
`student`, `/auth/register-staff` exige um admin autenticado. O seed rompe o
ciclo criando o admin diretamente, uma vez. As outras três contas nascem com
os mesmos campos e o mesmo hash das rotas.

O `entregador` continua existindo aqui mesmo depois da spec C, que substitui a
conta de entregador por credencial de carregamento: a conta serve para exercitar
o caminho antigo enquanto ele não é removido.
```

- [ ] **Step 7: Acrescentar o alvo no Makefile**

Depois do alvo `services-seed`, no `Makefile` da raiz:

```makefile
services-seed-demo: ## Seed the four demo accounts (needs DEMO_ACCOUNTS_PASSWORD)
	@test -n "$(DEMO_ACCOUNTS_PASSWORD)" || \
	  { echo "defina DEMO_ACCOUNTS_PASSWORD antes de rodar"; exit 1; }
	cd $(BACK_ROOT) && DEMO_ACCOUNTS_PASSWORD='$(DEMO_ACCOUNTS_PASSWORD)' $(COMPOSE) \
	  exec -T auth-users-service uv run python -m app.seeds.demo_accounts
```

Acrescentar `services-seed-demo` à linha `.PHONY` que já lista os alvos de serviço.

> **Atenção.** Não execute este alvo. Ele age no stack vivo do usuário.

- [ ] **Step 8: Lint e commit**

```bash
cd back-end/auth-users-service && uv run ruff check . && uv run ruff format .
cd ../..
git add back-end/auth-users-service/app/seeds/ \
        back-end/auth-users-service/tests/test_demo_accounts_seed.py \
        docs/back-end/demo-accounts.md Makefile
git diff --staged
git commit -m "feat(auth): seed the four demo accounts behind an env password"
```

---

### Task 5: Remover o monolito do compose e do Makefile

Três serviços do compose constroem a partir de `./legacy`: `migrate` (linha 128), `api` (linha 140) e `worker` (linha 171). Só `api` e `worker` dependem de `migrate` — nenhum serviço novo depende dele, então os três saem juntos.

O compose sai **antes** dos arquivos, na task seguinte: uma parada no meio deixa a árvore num estado que ainda sobe.

**Files:**
- Modify: `back-end/docker-compose.yml` (remover linhas 128-190, os três serviços)
- Modify: `Makefile` (remover `BACK_DIR` e os alvos `back-*`)

**Interfaces:**
- Consumes: nada.
- Produces: nada em código. As tasks 6 e 7 dependem de esta ter passado.

- [ ] **Step 1: Confirmar que nada mais depende dos três**

```bash
grep -n "migrate\|legacy\|API_PORT_EXTERNAL" back-end/docker-compose.yml
```

Esperado: só as ocorrências dentro dos blocos `migrate`, `api` e `worker` (linhas 128 a 190). Se aparecer uma referência num serviço novo, **pare** e reporte — a spec não previu isso.

- [ ] **Step 2: Remover os três serviços do compose**

Apagar de `back-end/docker-compose.yml` os blocos `migrate:`, `api:` e `worker:` inteiros — da linha 128 até a linha imediatamente anterior ao comentário `# ── Stack novo: gateway + 6 serviços ───`.

O comentário de seção deixa de fazer sentido com um stack só. Trocar por:

```yaml
  # ── Gateway + 6 serviços ────────────────────────────────────────────────
```

- [ ] **Step 3: Validar a sintaxe do compose sem subir nada**

```bash
docker compose -f back-end/docker-compose.yml config --quiet && echo "compose válido"
```

`config` apenas resolve e valida o arquivo; não cria, para nem reconstrói container. É a única subcomando de `docker compose` que este plano permite.

Esperado: `compose válido`, sem saída de erro.

- [ ] **Step 4: Remover os alvos do monolito no Makefile**

Remover a variável `BACK_DIR = back-end/legacy` (linha 3) e todos os alvos `back-*`: `back-up`, `back-down`, `back-logs`, `back-sh`, `back-test`, `back-test-host`, `back-test-e2e`, `back-lint`, `back-format`, `back-migrate`, `back-seed`, `back-revision`, `back-sync` — com a linha `.PHONY` correspondente (linha 96) e os comentários que só explicam o compose do legacy (linhas 10-15 e 34, 144-148).

**Não** remover: os alvos `front-*`, os `stack-*`, os `services-*`, nem o `help`.

- [ ] **Step 5: Confirmar que o Makefile ainda resolve**

```bash
make help
```

Esperado: a lista de alvos, sem nenhum `back-*` e sem erro de sintaxe. `help` só imprime; não toca em container.

```bash
grep -n "legacy" Makefile
```

Esperado: nenhuma saída.

- [ ] **Step 6: Commit**

```bash
git add back-end/docker-compose.yml Makefile
git diff --staged
git commit -m "refactor(back-end): drop the monolith from compose and the makefile"
```

---

### Task 6: Apagar `back-end/legacy/`

193 arquivos `.py`, mais alembic, Dockerfile, compose próprio, testes e lockfile. Todos os módulos já foram portados na fase 2 — `support`, o último, na fase 2d.

**Nunca execute a suíte deste diretório.** O `conftest.py` dela chama `flushdb` no Redis vivo do usuário (db 15). Apagar os arquivos é seguro; rodá-los não.

**Files:**
- Delete: `back-end/legacy/` inteiro

**Interfaces:**
- Consumes: task 5 (o compose não pode mais referenciar o diretório).
- Produces: nada.

- [ ] **Step 1: Confirmar que nada no repositório aponta para o diretório**

```bash
grep -rn "legacy" --include='*.py' --include='*.yml' --include='*.yaml' \
  --include='*.toml' --include='Makefile' --include='*.dart' \
  back-end front-end-flutter Makefile 2>/dev/null | grep -v '^back-end/legacy/'
```

Esperado: nenhuma saída. Qualquer referência sobrevivente é um caminho que quebra ao apagar o diretório — resolva antes de seguir.

Referências em `docs/` são esperadas e ficam para a task 7.

- [ ] **Step 2: Registrar o que está sendo apagado**

```bash
find back-end/legacy -name '*.py' | wc -l
git -C . rev-parse HEAD
```

Anotar os dois números no relatório da task. Depois do commit, o conteúdo só existe no histórico, e o SHA é como voltar nele.

- [ ] **Step 3: Apagar**

```bash
git rm -r --quiet back-end/legacy
```

`git rm` e não `rm`: o índice acompanha a remoção, e um `git status` limpo depois é a confirmação de que nada ficou meio apagado.

- [ ] **Step 4: Confirmar que a frota continua verde**

Rodar serviço a serviço, nunca `make services-test`:

```bash
for s in api-gateway auth-users-service learning-service commerce-service \
         chatbot-service notification-service analytics-service; do
  echo "→ $s"; (cd back-end/$s && uv run pytest -q) || break
done
(cd back-end/packages/edu-common && uv run pytest -q)
```

Esperado: todas verdes. A contagem esperada, com as tasks 1 a 4 já aplicadas: gateway 18, auth-users 70, learning 80, commerce 218, chatbot 32, notification 36, analytics 36, edu-common 60 — **550 no total**.

Antes deste plano a frota somava 539 e a suíte do legacy somava 56, que deixam de existir. A queda no total combinado é esperada e não é regressão.

```bash
git status --short | grep 'uv.lock' && git checkout -- $(git status --short | grep 'uv.lock' | awk '{print $2}')
```

- [ ] **Step 5: Commit**

```bash
git add -A back-end/legacy
git diff --staged --stat | tail -3
git commit -m "refactor(back-end): delete the legacy monolith

Every module was ported during phase 2; support, the last one, in 2d. The
compose stopped referencing this directory in the previous commit. The
content stays reachable in history."
```

---

### Task 7: Reconciliar a documentação

Três documentos descrevem um mundo que acabou de deixar de existir, e um deles já estava errado antes deste plano.

**Files:**
- Modify: `docs/back-end/start-here.md`
- Modify: `docs/back-end/microservices.md` (§9, e a tabela de módulos)
- Modify: `docs/back-end/phase-2-debt.md` (nota de triagem)
- Modify: `CLAUDE.md` (tabela de documentação)

**Interfaces:**
- Consumes: tasks 1 a 6.
- Produces: nada em código.

- [ ] **Step 1: Marcar `start-here.md` como histórico**

Ele documenta setup, arquitetura e padrões do monolito. Acrescentar no topo, antes de qualquer outro conteúdo:

```markdown
> **Documento histórico.** Descreve o monolito `back-end/legacy/`, apagado na
> spec A (2026-09-07). Nada aqui descreve o sistema em funcionamento. Para a
> arquitetura atual, veja [`microservices.md`](microservices.md).
>
> Fica no repositório porque a spec B porta regras de negócio usando o
> comportamento do monolito como referência, e porque é registro acadêmico da
> evolução do projeto.
```

Não reescrever o corpo. Um documento histórico rotulado vale mais que um documento reescrito pela metade.

- [ ] **Step 2: Corrigir a §9 de `microservices.md`**

A seção "Portas — por que estas" afirma que o app Flutter aponta para a porta do legacy e trata o corte como futuro. As duas coisas são falsas: `front-end-flutter/lib/core/network/api_config.dart:33` aponta para 8100 desde o commit `7c6eb6a` (2026-08-05).

Substituir os parágrafos "**O legacy fica onde o `.env` já manda**" e "**O que muda na fase 4**" por:

```markdown
**O stack vive na faixa 81xx.** Gateway em `GATEWAY_PORT_EXTERNAL` (**8100**) e
os seis serviços fixos em **8101-8106**. A faixa 80xx não estava disponível: a
8000 pode estar ocupada por outro projeto na mesma máquina, e a colisão
apareceria como *resultado errado*, não como erro.

**O app fala com o gateway.** `api_config.dart:33` aponta para 8100 desde o
commit `7c6eb6a` (2026-08-05) — antes, portanto, do corte. A spec A apagou o
monolito e removeu `migrate`, `api` e `worker` do compose; `API_PORT_EXTERNAL`
deixou de ter uso.

As portas 8101-8106 continuam publicadas para o host. Despublicá-las é ganho de
produção — que este projeto não tem — e atrapalharia a depuração das specs B, C
e D. Fica registrado como possível faxina futura, não como pendência.
```

- [ ] **Step 3: Fechar a tabela de módulos**

Na tabela que lista módulo por serviço, trocar toda menção a "portado do legacy na fase X" por "servido por `<serviço>`", e acrescentar acima dela:

```markdown
> Todos os módulos foram portados. O monolito foi apagado na spec A
> (2026-09-07); esta tabela deixou de ser um mapa de migração e passou a ser o
> índice de qual serviço atende cada prefixo.
```

- [ ] **Step 4: Registrar a triagem em `phase-2-debt.md`**

Acrescentar logo depois da tabela da §1:

```markdown
> **Triagem da spec A (2026-09-07).** O corte aconteceu. Três destes sete
> foram corrigidos antes dele:
>
> - Idempotência do seed — lock consultivo em `seed_products`, com teste de
>   corrida.
> - Dead-letter exchange — declarada no `EventConsumer` do `edu-common`, vale
>   para os sete consumidores.
> - Título de notificação — passou a usar os 8 primeiros caracteres em
>   maiúsculas, a mesma regra do `idCurto` do app.
>
> Os outros quatro seguem abertos, por decisão e não por esquecimento:
> `put_object` antes do commit, o deadlock em formas de pagamento, `/support`
> sem teto de linhas, e o acesso do aluno desativado ao suporte. Nenhum
> aparece numa demonstração; todos aparecem em produção.
```

- [ ] **Step 5: Atualizar a tabela de documentação no `CLAUDE.md`**

Na tabela de `## Documentacao`:

- Na linha de `start-here.md`, trocar a descrição por `Documento histórico: setup e padrões do monolito, apagado na spec A`.
- Acrescentar a linha do documento novo:

```markdown
| | [docs/back-end/demo-accounts.md](docs/back-end/demo-accounts.md) | Contas fixas de apresentação, uma por papel; senha via DEMO_ACCOUNTS_PASSWORD |
```

- [ ] **Step 6: Verificar que nenhuma afirmação sobrevivente é falsa**

```bash
grep -rn "porta 8001\|:8001\|API_PORT_EXTERNAL\|monolito serve\|fase 4" docs/ CLAUDE.md README.md
```

Toda ocorrência precisa estar dentro de um bloco marcado como histórico ou descrever o passado no passado. Corrigir as que não estiverem.

- [ ] **Step 7: Commit**

```bash
git add docs/back-end/start-here.md docs/back-end/microservices.md \
        docs/back-end/phase-2-debt.md CLAUDE.md
git diff --staged
git commit -m "docs(back-end): reconcile the docs with the monolith's removal"
```

---

### Task 8: Trazer o painel Angular por `git subtree`

`web-angular/` do repositório 2 vira `web-admin/` neste. A migração usa `git subtree`, não cópia de arquivos: uma cópia perderia a autoria dos colegas, que é justamente o que uma entrega acadêmica precisa preservar.

O Angular chega apontando para `localhost:8080/api/v1` e **continua apontando para lá**. Ele só fala com o gateway na spec B, quando os endpoints existirem. Enquanto isso não sobe no compose e está marcado como não funcional.

**Files:**
- Create: `web-admin/` (histórico do Angular)
- Create: `web-admin/README-STATUS.md`
- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: tasks 5 e 6 (o repositório já é só microsserviços).
- Produces: o diretório `web-admin/`, que a spec B modifica.

- [ ] **Step 1: Confirmar que o diretório de destino está livre**

```bash
test ! -e web-admin && echo "livre" || echo "OCUPADO — pare"
git status --short
```

Esperado: `livre`, e árvore limpa. `git subtree add` recusa rodar com árvore suja.

- [ ] **Step 2: Trazer o subtree**

```bash
git remote add repo2 https://github.com/trabalhos-si-fiap/mobile_hybrid_app.git
git fetch repo2
git subtree add --prefix=web-admin repo2 main
```

Isso cria um commit de merge trazendo o histórico. Não use `--squash`: o objetivo é preservar a autoria.

> O subtree traz o repositório 2 **inteiro** — `api/`, `mobile-flutter/` e
> `web-angular/` — para dentro de `web-admin/`. O passo seguinte poda.

- [ ] **Step 3: Podar o que não vem**

```bash
git rm -r --quiet web-admin/api web-admin/mobile-flutter
git mv web-admin/web-angular/* web-admin/ 2>/dev/null || true
git mv web-admin/web-angular/.* web-admin/ 2>/dev/null || true
rmdir web-admin/web-angular 2>/dev/null || true
ls web-admin
```

Esperado: o conteúdo do Angular na raiz de `web-admin/` — `src/`, `public/`, `package.json`, `angular.json`.

O `api/` do Java sai porque a spec B usa o histórico do repositório arquivado como referência, não uma cópia aqui. O `mobile-flutter/` sai porque cada tela dele já tem equivalente no `front-end-flutter` — o passo 4 prova isso antes de o commit ser feito.

- [ ] **Step 4: Provar que nada do `mobile-flutter` se perde**

Para cada arquivo Dart do app descontinuado, apontar o equivalente no `edu`:

```bash
git show repo2/main:mobile-flutter/lib --name-only 2>/dev/null || \
  git ls-tree -r --name-only repo2/main -- mobile-flutter/lib | grep '\.dart$'
```

Comparar com:

```bash
find front-end-flutter/lib -name '*.dart' | sed 's|front-end-flutter/lib/||' | sort
```

Escrever o resultado em `web-admin/README-STATUS.md` (passo 5). Um arquivo do repositório 2 **sem** equivalente aqui é um achado que precisa ser reportado ao usuário antes de o commit ser feito — não uma perda a registrar depois.

Equivalências já medidas e esperadas: `core/network/app_http.dart` é byte a byte idêntico; `features/admin/`, `features/auth/`, `features/notifications/` e `features/logistics/{picking,delivery}_queue_screen.dart` têm equivalente com divergência que só existe porque acompanhavam o contrato Java.

- [ ] **Step 5: Registrar o estado do painel**

Criar `web-admin/README-STATUS.md`:

```markdown
# Estado deste painel

Veio de `trabalhos-si-fiap/mobile_hybrid_app`, pasta `web-angular/`, trazido
por `git subtree` na spec A (2026-09-07) com o histórico preservado.

## Não funciona ainda

Os serviços Angular apontam para `localhost:8080/api/v1` — a API Java, que a
spec A eliminou. **O painel não sobe contra este backend.**

A troca para o api-gateway (porta 8100) é escopo da
[spec B](../docs/superpowers/specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md),
e depende de endpoints de estoque e transportadora que ainda não existem no
`commerce-service`.

Enquanto isso, `web-admin` não está no `docker-compose.yml`.

## O que veio junto e foi podado

- `api/` (Spring Boot) — não veio. A spec B usa o histórico do repositório
  arquivado como referência das regras de negócio.
- `mobile-flutter/` — não veio. Cada tela tem equivalente em
  `front-end-flutter/lib/features/`.

### Equivalência tela a tela

| `mobile-flutter/lib/` | `front-end-flutter/lib/` |
|---|---|
| `core/network/app_http.dart` | idêntico, byte a byte |
| `core/network/{auth_http_client,session_store,token_refresher,token_store}.dart` | mesmo caminho |
| `core/theme/`, `core/utils/` | mesmo caminho |
| `features/auth/` (5 telas) | mesmo caminho |
| `features/admin/` (dashboard, analytics, widgets) | mesmo caminho |
| `features/notifications/data/messaging_service.dart` | mesmo caminho |
| `features/logistics/presentation/picking_queue_screen.dart` | mesmo caminho |
| `features/logistics/presentation/delivery_queue_screen.dart` | mesmo caminho |

O `edu` tem, além dessas: `picking_screen`, `delivery_detail_screen`,
`tracking_screen` e o `logistics_scaffold`.
```

- [ ] **Step 6: Ignorar os artefatos de build do Angular**

Acrescentar ao `.gitignore` da raiz:

```gitignore
# web-admin (Angular)
web-admin/node_modules/
web-admin/dist/
web-admin/.angular/
```

- [ ] **Step 7: Atualizar o `README.md` da raiz**

Na seção que descreve a estrutura do repositório, acrescentar `web-admin/` com uma linha dizendo o que é e que ainda não funciona, apontando para `web-admin/README-STATUS.md`.

- [ ] **Step 8: Confirmar que nada do backend quebrou**

O subtree não toca em `back-end/`, mas confirme antes de commitar um merge:

```bash
(cd back-end/commerce-service && uv run pytest -q)
(cd back-end/auth-users-service && uv run pytest -q)
git status --short | head -20
```

- [ ] **Step 9: Commit**

```bash
git add -A web-admin .gitignore README.md
git diff --staged --stat | tail -5
git commit -m "feat(web-admin): bring the angular panel in with its history

Moved from trabalhos-si-fiap/mobile_hybrid_app via git subtree so the
authorship survives. The Java api/ and the mobile-flutter/ fork are pruned:
every screen of the fork already has an equivalent under
front-end-flutter/lib/features/, listed in web-admin/README-STATUS.md.

The panel still points at localhost:8080/api/v1 and does not run against
this backend. Spec B moves it to the gateway."
git remote remove repo2
```

---

### Task 9: Preparar o arquivamento do repositório 2

O arquivamento em si é ação irreversível e externa, no GitHub. Esta task **prepara** e para: quem executa o plano não arquiva nada.

**Files:**
- Create (no clone do repo 2): `README.md` final
- Nenhum arquivo neste repositório

**Interfaces:**
- Consumes: task 8 (o painel já está no `edu`).
- Produces: nada.

- [ ] **Step 1: Escrever o README final no clone do repositório 2**

No clone em `/home/elias/programming/fiap/mobile_hybrid_app`, criar uma branch e substituir o `README.md`:

```bash
cd /home/elias/programming/fiap/mobile_hybrid_app
git checkout -b docs/archive-notice
```

Conteúdo:

```markdown
# Edu Admin — arquivado

Este repositório foi consolidado no
[`trabalhos-si-fiap/edu`](https://github.com/trabalhos-si-fiap/edu) em
setembro de 2026. Ele fica aqui como registro; nada é desenvolvido a partir
dele.

## Onde cada aplicação foi parar

| Pasta | Destino |
|---|---|
| `web-angular/` | `edu/web-admin/`, trazido por `git subtree` com o histórico preservado |
| `mobile-flutter/` | Descontinuado. Cada tela tem equivalente em `edu/front-end-flutter/lib/features/` — a tabela de equivalência está em `edu/web-admin/README-STATUS.md` |
| `api/` (Spring Boot) | Eliminado. As regras de estoque, transportadora e ocorrência foram portadas para `edu/back-end/commerce-service/`; este código continua aqui como referência |

## Por que

A plataforma passou a rodar sobre um backend só — os microsserviços Python do
`edu`. Manter uma segunda API e um fork do app Flutter significava implementar
cada mudança duas vezes.
```

- [ ] **Step 2: Commitar e abrir o pull request**

```bash
git add README.md
git diff --staged
git commit -m "docs: point the readme at the consolidated repository"
```

**Pare aqui.** Não faça push nem abra PR sem o usuário pedir: o repositório é compartilhado com os colegas, e a mudança é visível a eles.

- [ ] **Step 3: Entregar as instruções de arquivamento ao usuário**

Reportar, sem executar:

> O repositório 2 está pronto para arquivar. Falta, e é ação sua:
> 1. Revisar e mesclar a branch `docs/archive-notice` no `mobile_hybrid_app`.
> 2. Avisar os colegas antes de arquivar — arquivar torna o repositório
>    somente-leitura para todo mundo.
> 3. GitHub → Settings → General → Danger Zone → *Archive this repository*.
>
> O arquivamento é reversível pelo mesmo caminho, mas fecha issues e pull
> requests abertos.

---

## Encerramento do plano

- [ ] **Verificação final da frota**

```bash
for s in api-gateway auth-users-service learning-service commerce-service \
         chatbot-service notification-service analytics-service; do
  echo "→ $s"; (cd back-end/$s && uv run pytest -q) || break
done
(cd back-end/packages/edu-common && uv run pytest -q)
make front-analyze
make front-test
```

Esperado: 550 testes de backend passando, `flutter analyze` limpo, testes do Flutter verdes.

- [ ] **Conferir os critérios de pronto da spec**

| Critério | Como confirmar |
|---|---|
| Suítes verdes | O laço acima |
| Nenhum container de monolito ou Java | `grep -c "legacy" back-end/docker-compose.yml` devolve 0 |
| App completa um pedido contra o gateway | Verificação manual do usuário; não é automatizável aqui |
| `back-end/legacy/` não existe | `test ! -e back-end/legacy` |
| `web-admin/` com histórico preservado | `git log --oneline web-admin \| wc -l` maior que 1 |
| Repositório 2 arquivado | Ação do usuário (task 9) |
| Quatro itens de dívida marcados | `grep -n "Triagem da spec A" docs/back-end/phase-2-debt.md` |

- [ ] **Reportar o que ficou pendente do usuário**

Três coisas não são executáveis por quem roda este plano:

1. Apagar as filas antigas do RabbitMQ antes da primeira subida com DLX (task 2, step 6).
2. Rodar `make services-seed` e `make services-seed-demo` no stack vivo.
3. Mesclar, avisar os colegas e arquivar o repositório 2 (task 9).
