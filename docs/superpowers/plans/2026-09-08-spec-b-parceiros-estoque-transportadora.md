# Spec B — Comércio: parceiros, estoque e transportadora — Plano de implementação

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para implementar este plano task a task. Os
> passos usam caixa de seleção (`- [ ]`) para rastreamento.

**Objetivo:** Fazer o `commerce-service` ser dono de estoque com auditoria,
transportadora, parceiro e origem de expedição, com o app Flutter abrindo uma
seção de parceiros e o painel Angular operando tudo pelo gateway.

**Arquitetura:** Nenhum serviço novo. Todo o backend novo vive dentro do
`commerce-service`, sobre entidades que já existem (`Fornecedor` vira o
parceiro, `Estoque` já é o `Inventory` do Java, `Ocorrencia` absorve a
dimensão de transportadora). O gateway ganha duas entradas de roteamento. O
`web-admin` é reescrito para falar com o gateway em vez da API Java morta.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.x async + Alembic +
PostgreSQL 17; Flutter/Dart; Angular 22 (standalone, signals-free, RxJS).

**Spec:** [`../specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md`](../specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md)

**Registro da spec anterior (leitura obrigatória antes da task 1):**
[`2026-09-07-spec-a-corte-e-consolidacao-execution-record.md`](2026-09-07-spec-a-corte-e-consolidacao-execution-record.md)

---

## Baselines medidos em 2026-09-08

Medidos nesta árvore, neste commit (`0a082ea`), não copiados de documento
anterior. **Nenhuma task pode citar outro número.**

| Alvo | Comando | Medido |
|---|---|---|
| commerce-service | `cd back-end/commerce-service && uv run pytest -q` | **367 passed** |
| api-gateway | `cd back-end/api-gateway && uv run pytest -q` | **36 passed** |
| Flutter | `cd front-end-flutter && flutter test` | **161 passed** |
| Flutter analyze | `cd front-end-flutter && flutter analyze` | **6 avisos `info`, exit 1** |
| web-admin | `cd web-admin && npm run build` | **exit 0**, 3 avisos de budget SCSS |

Os outros cinco serviços (auth-users 72, learning 78, chatbot 37,
notification 36, analytics 34, edu-common 62) **não são tocados por este
plano**. Não os rode task a task; só na verificação final.

**Critério de teste — relativo, nunca absoluto:** nenhum teste que passava
antes de uma task pode falhar depois dela, e a contagem só sobe. Se uma task
precisa emendar um teste existente, isso está escrito explicitamente na task,
com o motivo. Emenda não declarada é falha da task.

---

## Global Constraints

Valem para toda task. Copiadas da spec e do `CLAUDE.md`.

- **TDD sem exceção.** Teste que falha primeiro, mínimo para passar, refatorar.
- **Regra 1:** nada de SQL concatenado. Sempre `select()` com parâmetro bound.
- **Regra 2:** todo endpoint tem `Depends(get_current_user)` ou
  `Depends(requer_papel(...))`. Nenhuma rota nova sem controle de acesso.
- **Regra 3:** read→write em recurso compartilhado é atômico. `with_for_update()`
  ou expressão SQL atômica. Vale para estoque, carrinho e ocorrência.
- **Regra 4:** todo campo de texto tem `max_length` no model **e** no schema
  Pydantic; toda listagem é paginada, inclusive as de administração.
- **Regra 6:** schemas com campos explícitos. Nenhum endpoint devolve objeto
  ORM cru.
- **Regra 9:** comparação de segredo com `hmac.compare_digest`. (Não incide
  nesta spec, mas nenhuma task pode introduzir `==` em segredo.)
- **Sem `if parceiro == "leroy"`.** A string `leroy` só pode aparecer em dado
  de seed. Nunca em caminho de decisão. Isso é testado (task 11).
- **Lint:** `uv run ruff check .` e `uv run ruff format .` no diretório do
  serviço. `line-length = 100`. Regras `E,F,I,N,UP,B,A,C4,SIM,RUF,ASYNC,S`,
  `ignore = ["S101"]`. Exceção precisa de sufixo `Error` (N818).
- **`loguru.logger`, nunca `print()`.**
- **Idioma dos identificadores:** o agregado que tem cliente é escrito em
  inglês (`products`, `orders`); o que não tem fica em português
  (`fornecedores`, `estoque`, `ocorrencias`). Esta spec dá cliente a
  `fornecedores` (o app e o painel), mas **renomear a tabela é proibido** —
  o rename custaria uma revision destrutiva a mais e a spec não pede. O nome
  da tabela fica; a rota é `/partners`. Isso é decisão registrada, não
  esquecimento.
- **Commits:** Conventional Commits, um por unidade lógica, em inglês,
  imperativo, minúsculas. Rodar `git diff --staged` antes de cada commit.
  Terminar cada mensagem com:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`

### Ambiente local — proibições absolutas

O usuário mantém um stack Docker vivo construído deste checkout, com o mesmo
`COMPOSE_PROJECT_NAME`.

- **Nunca** `docker compose up/down/restart/build/exec`, `make stack-*`,
  `make services-migrate`, `make services-seed`, `make services-seed-demo`.
- **Nunca** `make services-test` nem `make services-lint` — reescrevem
  `uv.lock`. Rode `uv run pytest` / `uv run ruff` dentro de cada serviço.
- **Nunca** `alembic upgrade head` contra `commerce_db` (porta 5433) nem
  contra qualquer banco de desenvolvimento.
- **Permitido:** `docker compose -f back-end/docker-compose.yml config --quiet`,
  `make help`, `make -n <alvo>`, e leitura
  (`docker exec -i edu-postgres psql -U edu -d commerce_db -c "..."`).
- **Permitido e usado pela task 1:** aplicar alembic contra
  `postgresql+asyncpg://edu:edu@localhost:5433/commerce_test`. Esse é o banco
  de scratch da própria suíte — `tests/conftest.py::test_engine` faz
  `Base.metadata.drop_all` + `create_all` nele a cada sessão de pytest. Não é
  banco de desenvolvimento. Decisão do usuário de 2026-09-08.

---

## Decisões tomadas antes de escrever as tasks

Cada uma resolve um ponto onde a spec estava incompleta ou onde a árvore
contradizia a spec. As quatro primeiras foram decididas pelo usuário em
2026-09-08; as demais são medição.

### D1 — CRUD admin de produtos entra no escopo

O `commerce-service` só tem `GET` de produto (medido:
`grep -n "@router" app/routers/produtos.py` devolve cinco rotas, todas GET,
mais um POST de review). O `product-form-modal` do `web-admin` cria e edita
produto com `sku`, `minimumStock`, `initialQuantity`, `active` — nenhum desses
campos existe no `Product` Python. O critério de pronto 2 da spec diz
literalmente "`web-admin` opera produtos, estoque, transportadoras e
ocorrências pelo gateway".

**Decisão:** entram `POST /products` e `PUT /products/{id}`, restritos a
admin, e as colunas que faltam: `products.sku` (único, 60), `products.active`,
`estoque.estoque_minimo`. O modal Angular sobrevive inteiro.

### D2 — O PIX sai por uma rota nova do aluno

O fluxo da spec cita `POST /orders/{id}/confirm-payment`, que não existe. O
que existe é `PATCH /admin/orders/{pedido_id}/confirm-payment`
(`app/routers/admin.py:37`), que é do admin e faz transição de status
(`CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO`) — outra coisa, com outro dono.

**Decisão:** `POST /orders/{order_id}/confirm-payment` no router de pedidos,
dono = o aluno do pedido, devolve `{"payment_code": "..."}`. Não muda status;
não colide com a rota do admin (prefixo diferente, método diferente).
`OrderOut` fica intacto.

### D3 — O boleto sai do cliente junto com o PIX

`checkout_screen.dart:448` e `:458` geram **dois** códigos no app:
`_generatePixCode` e `_generateBoletoCode`. A spec só nomeia o PIX. Mover
metade deixaria o mock que a spec quer remover parcialmente vivo.

**Decisão:** `app/services/codigos_pagamento.py` emite os dois. O app deixa de
gerar qualquer código de pagamento.

### D4 — A migration é provada aplicando em `commerce_test`

A suíte monta o schema com `Base.metadata.create_all` e **nunca** invoca
alembic (`tests/conftest.py::test_engine`). Nenhuma revision deste serviço é
exercitada por teste nenhum — está escrito em
`tests/test_migration_guard.py`, primeiro parágrafo. Uma revision nova entraria
no repositório sem prova de que aplica.

**Decisão:** a task 1 aplica a cadeia inteira contra `commerce_test` e depois
restaura o banco com `create_all`. Ver a task para o procedimento exato.

### D5 — Uma revision só, aditiva, no topo da cadeia

Head medido: `c90210e9965c`
(`c90210e9965c_pedido_status_historico_order_id_not_null.py`). Cadeia completa
medida: `62926745dd94 → 77290516f1b1 → 1308bb221890 → d3a5f5cd6ea8 →
c28f71cb6e30 → ae70488977ef → 6c409ccb480c → 942f75a9a3f2 → 39d3b55161af →
bd410bba0e85 → 099099b0c1a8 → 73f26f88d679 → c90210e9965c`.

As três revisions destrutivas (`1308bb221890`, `bd410bba0e85`,
`099099b0c1a8`) e a de guard (`73f26f88d679`) estão **todas a montante** e já
aplicadas. Nada nesta spec as toca. Toda mudança de schema da spec B é
aditiva: colunas novas com `server_default`, tabelas novas.

**Decisão:** **uma** revision nova, `down_revision = "c90210e9965c"`, com
`downgrade()` **real e reversível** (`drop_column` / `drop_table`) — ao
contrário das três a montante, esta não precisa levantar exceção, porque não
destrói nada. Todo o schema da spec B nasce nela. Nenhuma task posterior
adiciona coluna.

### D6 — `Fornecedor` é o parceiro; a tabela não é renomeada

`app/models/produto.py:22` já traz `Fornecedor(id, nome, contato, ativo)`. O
filtro por ativo que a spec pede é uma coluna que já existe. Falta a origem.
A tabela continua `fornecedores`; a rota é `/partners`. Ver Global Constraints.

### D7 — Ajuste de estoque: absoluto e delta, um núcleo atômico só

O Java (`InventoryService.adjust`) grava **quantidade absoluta** com motivo, e
`Inventory.adjustTo` registra `previousQuantity`/`newQuantity`. A rota que já
existe aqui (`PATCH /admin/inventory/{estoque_id}/adjust?quantidade=N`,
`admin.py:155`) também é absoluta, já usa `with_for_update()`, e **não deixa
rastro nenhum**. A spec pede `POST /products/{id}/stock-adjustments` com
**delta**.

**Decisão:** um núcleo atômico só, `services/estoque.py::aplicar_ajuste`, que
recebe o delta e grava a linha de auditoria na mesma transação sob
`with_for_update()`. A rota absoluta do admin passa a converter para delta
dentro do lock (`delta = quantidade_alvo - estoque.quantidade`) e chamar o
mesmo núcleo. Duas portas, um caminho de escrita.

A tabela `estoque_ajustes` guarda `quantidade_anterior` e `quantidade_nova`
(paridade com o Java) e **não** guarda `delta` — ele é derivável e o schema
Pydantic o expõe como campo calculado. Guardar os três seria uma terceira
fonte da verdade para o mesmo fato.

### D8 — Paridade do PIX é estrutural, não byte a byte

A spec pede que "o payload emitido pelo backend seja idêntico ao que o cliente
gerava, para o mesmo pedido". Medido: `_generatePixCode`
(`checkout_screen.dart:448`) usa `Random()` para 25 caracteres de `txid` — o
cliente **não** produz o mesmo payload duas vezes para o mesmo pedido, então
"idêntico" não pode ser literal.

**Decisão:** o backend deriva o `txid` do `order_id` (determinístico e
reproduzível), e o teste de paridade trava o que era de fato contrato: o
template EMV, os segmentos fixos, o alfabeto e o comprimento do `txid`, e o
comprimento total. A aleatoriedade era acidente do mock, não contrato.

### D9 — O `web-admin` se adapta ao backend, não o contrário

Medido nos seis serviços Angular: o painel espera envelope de página do Spring
(`{content, page, size, totalElements, totalPages}`), `id` numérico,
`{accessToken, tokenType, user}` no login, e os caminhos `/inventory`,
`/carrier-occurrences`, `/dashboard`. O backend responde envelope
`{items, total, limit, offset}`, `id` UUID em produto e pedido,
`{user, tokens}` no login, e os caminhos `/admin/inventory`, `/occurrences`,
`/analytics/...`.

**Decisão:** o Angular é reescrito (é o que a spec manda: "reescrever os
serviços Angular para os endpoints acima"). O backend não ganha envelope
Spring. Consequência direta: o gateway precisa **só** de `partners` e
`carriers` — `/admin`, `/occurrences`, `/products` e `/analytics` já estão em
`SERVICE_MAP` (`api-gateway/app/routing.py:16-25`).

### D10 — O dashboard usa o que o analytics tem

Medido: `analytics-service/app/routers/analytics.py` expõe
`/analytics/students/{id}`, `/analytics/deliveries`, `/analytics/summary`,
`/analytics/executive-summary` e `/analytics/anomalies`. **Não existe**
`/dashboard`. O `DashboardResponse` do Angular pede quinze campos que não
existem em lugar nenhum (`registeredStudents`, `activeStudents`,
`inactiveRiskStudents`, `activityHistory`, ...).

**Decisão:** o dashboard é reconstruído a partir do que existe de verdade —
`GET /analytics/executive-summary?dias=30` (dá `pedidos_criados`,
`pedidos_por_status`, `ocorrencias_abertas`, `ocorrencias_resolvidas`,
`diagnosticos_por_acao`, `resumo_executivo`) mais os totais de
`/partners`, `/carriers` e `/admin/inventory`. O que sobra é registrado como
pendência na task 14, **nunca inventado no cliente**.

### D11 — O `web-admin` não tem suíte de teste, e esta spec não cria uma

Medido: `find web-admin/src -name '*.spec.ts'` não devolve nada, o
`package.json` não traz runner de teste (nem karma nem jest), e
`web-admin/node_modules/` está ausente do disco e ignorado pelo git
(`.gitignore:33-34`).

**Decisão:** a verificação do `web-admin` é `npm install` + `npm run build`. O
build AOT do Angular faz type-check de template, que é exatamente o que pega
mudança de forma de payload. Montar infraestrutura de teste Angular é escopo
que a spec não pede. Registrado como pendência na task 14.

### D12 — Ocorrência de transportadora precisa de rotas de admin

`POST /occurrences/{id}/resolve` (`ocorrencias.py:233`) é **só do aluno** e faz
lógica de substituição de item. Uma ocorrência de dano ou falha de entrega não
passa por ali. E não há `GET /occurrences` paginado — só
`GET /occurrences/order/{pedido_id}`.

**Decisão:** a task 5 acrescenta `GET /occurrences` (admin, paginado, filtros
por transportadora/tipo/status), `POST /occurrences/carrier` (admin, cria
ocorrência de transportadora sobre um pedido) e
`POST /occurrences/{id}/close` (admin, fecha sem lógica de substituição). O
`resolve` do aluno fica intacto.

### D13 — Tipos de ocorrência: três novos, um reaproveitado

Java: `DELIVERY_DELAY, DAMAGE, DELIVERY_FAILURE, OTHER`. Python já tem
`FALTA_ESTOQUE` e `ATRASO_ENTREGA` (`models/ocorrencia.py:16`).
`ATRASO_ENTREGA` **é** `DELIVERY_DELAY`.

**Decisão:** entram `DANO`, `FALHA_ENTREGA` e `OUTRO`. `ATRASO_ENTREGA` é
reaproveitado. Status continua `ABERTA`/`RESOLVIDA` (medido em cinco lugares
de `app/`), e o Angular traduz para `OPEN`/`RESOLVED` na exibição.

### D14 — A origem do pedido é snapshot, não referência

`order_items.supplier_id` já existe, `nullable=True`, e **nunca é escrito** —
o próprio comentário do model (`pedido.py:145-152`) registra isso. A spec C lê
a origem e "não recalcula, porque o estoque pode mudar depois".

**Decisão:** `orders` ganha `origem_rotulo`, `origem_lat`, `origem_lng`
(snapshot, mesmo espírito dos `ship_*`), e `order_items.supplier_id` passa a
ser preenchido na criação do pedido. A origem é copiada do fornecedor, não
referenciada por FK a ele.

---

## Estrutura de arquivos

### `back-end/commerce-service/` — criar

| Arquivo | Responsabilidade |
|---|---|
| `app/models/transportadora.py` | `Carrier` + `CarrierStatus` |
| `app/models/estoque_ajuste.py` | `EstoqueAjuste` (trilha de auditoria) |
| `app/schemas/parceiro.py` | `ParceiroIn/Out/List` |
| `app/schemas/transportadora.py` | `TransportadoraIn/Out/List/StatusIn` |
| `app/services/parceiros.py` | regra de ativo e de origem |
| `app/services/estoque.py` | ajuste atômico com auditoria |
| `app/services/transportadoras.py` | CRUD e transição de status |
| `app/services/codigos_pagamento.py` | payload PIX e linha digitável |
| `app/routers/parceiros.py` | `/partners` |
| `app/routers/transportadoras.py` | `/carriers` |
| `app/seeds/parceiros.py` | fornecedor Edu + Leroy Merlin + estoque |
| `alembic/versions/<hash>_spec_b_schema.py` | a única revision desta spec |

### `back-end/commerce-service/` — modificar

| Arquivo | O quê |
|---|---|
| `app/models/produto.py` | `Fornecedor` ganha origem; `Product` ganha `sku`/`active`; `Estoque` ganha `estoque_minimo` |
| `app/models/ocorrencia.py` | `transportadora_id` nullable |
| `app/models/pedido.py` | `orders` ganha `origem_*` |
| `app/schemas/produto.py` | `sku`/`active` em `ProductOut`; `ProductIn`/`ProductPatch` |
| `app/schemas/estoque.py` | `estoque_minimo`, `EstoqueAjusteOut` |
| `app/schemas/ocorrencia.py` | `transportadora_id`, filtros |
| `app/schemas/pedido.py` | `PagamentoConfirmadoOut` |
| `app/services/carrinho.py` | regra de origem única |
| `app/services/pedidos.py` | grava origem e `supplier_id` |
| `app/services/produtos.py` | filtro `partner_id`, criar/atualizar |
| `app/routers/produtos.py` | `partner_id`, `POST`, `PUT`, `stock-adjustments` |
| `app/routers/admin.py` | `/admin/inventory` passa pelo núcleo com auditoria |
| `app/routers/ocorrencias.py` | rotas de admin da task 5 |
| `app/routers/pedidos.py` | `POST /{id}/confirm-payment` |
| `app/routers/carrinho.py` | traduz o conflito de origem em 409 |
| `app/exceptions.py` | exceções novas |
| `app/main.py` | inclui os dois routers novos |
| `tests/conftest.py` | importa os models novos |

### Fora do commerce-service

| Arquivo | O quê |
|---|---|
| `back-end/api-gateway/app/routing.py` | `partners` e `carriers` -> `commerce` |
| `front-end-flutter/lib/features/marketplace/domain/partner.dart` | novo |
| `front-end-flutter/lib/features/marketplace/data/partner_service.dart` | novo |
| `front-end-flutter/lib/features/marketplace/presentation/partners_provider.dart` | novo |
| `front-end-flutter/lib/features/marketplace/presentation/widgets/partners_section.dart` | novo |
| `front-end-flutter/lib/features/marketplace/presentation/marketplace_screen.dart` | encaixa a seção |
| `front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart` | remove os dois geradores |
| `front-end-flutter/lib/features/marketplace/data/checkout_service.dart` | chama `confirm-payment` |
| `front-end-flutter/lib/features/cart/data/cart_service.dart` | 409 com mensagem do servidor |
| `web-admin/**` | reescrita (task 13) |
| `docs/back-end/microservices.md`, `docs/smoke-test.md`, `CLAUDE.md` | task 14 |

---

## Ordem e dependências

```
1 (schema)
├─ 2 (parceiros) ─┬─ 7 (catálogo por parceiro) ─ 12 (Flutter)
├─ 3 (estoque)    │
├─ 4 (carriers) ──┼─ 5 (ocorrências)
├─ 6 (produtos)  ─┘
├─ 8 (carrinho) ─ 9 (origem do pedido)
├─ 10 (códigos de pagamento) ─ 12
└─ 11 (seed)
2,3,4,5,6,10 ─ 13 (web-admin) ─ 14 (docs + verificação final)
```

A task 1 é bloqueante para todas. As tasks 2, 3, 4, 6, 8 e 10 são
independentes entre si depois dela.

---

### Task 1: Schema da spec B — models e a única revision

Todo o schema desta spec nasce aqui. Nenhuma task posterior adiciona coluna ou
tabela. Ver D5.

**Files:**
- Modificar: `back-end/commerce-service/app/models/produto.py`
- Modificar: `back-end/commerce-service/app/models/ocorrencia.py`
- Modificar: `back-end/commerce-service/app/models/pedido.py`
- Criar: `back-end/commerce-service/app/models/transportadora.py`
- Criar: `back-end/commerce-service/app/models/estoque_ajuste.py`
- Criar: `back-end/commerce-service/alembic/versions/b1a2c3d4e5f6_spec_b_schema.py`
- Modificar: `back-end/commerce-service/tests/conftest.py:57-63`
- Criar: `back-end/commerce-service/tests/test_spec_b_schema.py`

**Interfaces (o que as tasks seguintes consomem):**

```python
# app/models/produto.py
class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id: int; nome: str; contato: str | None; ativo: bool
    origem_rotulo: str          # "Cajamar, SP" — 120, NOT NULL, default ""
    origem_lat: Decimal | None  # Numeric(9, 6)
    origem_lng: Decimal | None  # Numeric(9, 6)

class Product(Base):
    # ... colunas atuais ...
    sku: str      # String(60), NOT NULL, UNIQUE, default ""
    active: bool  # NOT NULL, default True

class Estoque(Base):
    # ... colunas atuais ...
    estoque_minimo: int  # NOT NULL, default 0

# app/models/estoque_ajuste.py
class EstoqueAjuste(Base):
    __tablename__ = "estoque_ajustes"
    id: int; estoque_id: int; quantidade_anterior: int; quantidade_nova: int
    motivo: str            # String(300), NOT NULL
    autor_id: uuid.UUID    # NOT NULL
    criado_em: datetime

# app/models/transportadora.py
class CarrierStatus(str, Enum):
    ACTIVE = "ACTIVE"; INACTIVE = "INACTIVE"

class Carrier(Base):
    __tablename__ = "carriers"
    id: int; name: str; location: str; email: str
    average_delivery_days: int
    rating: Decimal          # Numeric(2, 1)
    sla_percentage: Decimal  # Numeric(5, 2)
    status: str              # String(20), default "ACTIVE"
    created_at: datetime; updated_at: datetime

# app/models/ocorrencia.py
class Ocorrencia(Base):
    # ... colunas atuais ...
    transportadora_id: int | None  # FK carriers.id, nullable

# app/models/pedido.py
class Order(Base):
    # ... colunas atuais ...
    origem_rotulo: str | None   # String(120)
    origem_lat: Decimal | None  # Numeric(9, 6)
    origem_lng: Decimal | None  # Numeric(9, 6)
```

Tamanhos vindos do Java, medidos em
`mobile_hybrid_app/api/src/main/java/com/edu/api/carrier/entity/Carrier.java`:
`name` 150, `location` 150, `email` 254, `status` 20, `rating`
`precision=2 scale=1`, `slaPercentage` `precision=5 scale=2`. `reason` de
`InventoryAdjustment` é 300. `sku` de `Product` é 60 e único.

- [ ] **Passo 1: escrever o teste que falha**

Criar `tests/test_spec_b_schema.py`. Este teste trava a FORMA do schema —
é o que as onze tasks seguintes assumem, e é barato de quebrar em silêncio.

```python
"""Trava a forma do schema que a spec B introduz.

Não roda alembic (a suíte monta o schema com `Base.metadata.create_all` —
ver `tests/conftest.py::test_engine`). O que este arquivo garante é que os
MODELS declaram o que as tasks 2..13 consomem, com os tamanhos medidos no
Java de origem. A prova de que a REVISION aplica está no passo 6 desta
task, feita à mão contra `commerce_test`, e registrada no relatório.
"""

from decimal import Decimal

from app.models.estoque_ajuste import EstoqueAjuste
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order
from app.models.produto import Estoque, Fornecedor, Product
from app.models.transportadora import Carrier, CarrierStatus


def test_fornecedor_carries_a_shipping_origin():
    cols = Fornecedor.__table__.columns
    assert cols["origem_rotulo"].type.length == 120
    assert cols["origem_rotulo"].nullable is False
    assert cols["origem_lat"].nullable is True
    assert cols["origem_lng"].nullable is True


def test_product_has_sku_and_active():
    cols = Product.__table__.columns
    assert cols["sku"].type.length == 60
    assert cols["sku"].unique is True
    assert cols["active"].nullable is False


def test_estoque_has_a_minimum():
    assert Estoque.__table__.columns["estoque_minimo"].nullable is False


def test_estoque_ajuste_records_both_quantities_and_an_author():
    cols = EstoqueAjuste.__table__.columns
    assert set(cols.keys()) == {
        "id",
        "estoque_id",
        "quantidade_anterior",
        "quantidade_nova",
        "motivo",
        "autor_id",
        "criado_em",
    }
    assert cols["motivo"].type.length == 300
    assert cols["autor_id"].nullable is False


def test_carrier_matches_the_java_field_widths():
    cols = Carrier.__table__.columns
    assert cols["name"].type.length == 150
    assert cols["location"].type.length == 150
    assert cols["email"].type.length == 254
    assert (cols["rating"].type.precision, cols["rating"].type.scale) == (2, 1)
    assert (cols["sla_percentage"].type.precision, cols["sla_percentage"].type.scale) == (5, 2)


def test_carrier_status_is_an_enum_of_two_values():
    assert [s.value for s in CarrierStatus] == ["ACTIVE", "INACTIVE"]


def test_ocorrencia_points_at_a_carrier_optionally():
    col = Ocorrencia.__table__.columns["transportadora_id"]
    assert col.nullable is True
    assert {fk.target_fullname for fk in col.foreign_keys} == {"carriers.id"}


def test_order_snapshots_the_shipping_origin():
    cols = Order.__table__.columns
    assert cols["origem_rotulo"].type.length == 120
    for name in ("origem_rotulo", "origem_lat", "origem_lng"):
        assert cols[name].nullable is True


async def test_the_new_tables_are_created_by_the_suite_schema(db_session):
    """Se um model novo não for importado por `conftest.py::test_engine`,
    `create_all` não o cria e todo teste das tasks 2..13 morre com
    `UndefinedTableError` — um sintoma que não aponta para a causa."""
    fornecedor = Fornecedor(nome="Edu", origem_rotulo="Aclimação, SP")
    db_session.add(fornecedor)
    await db_session.commit()

    produto = Product(name="P", type="apostila", price=Decimal("1.00"), sku="SKU-1")
    db_session.add(produto)
    await db_session.commit()

    estoque = Estoque(produto_id=produto.id, fornecedor_id=fornecedor.id, quantidade=5)
    db_session.add(estoque)
    await db_session.commit()

    db_session.add(
        EstoqueAjuste(
            estoque_id=estoque.id,
            quantidade_anterior=5,
            quantidade_nova=7,
            motivo="Recebimento de lote",
            autor_id=fornecedor.id and __import__("uuid").UUID(int=1),
        )
    )
    db_session.add(
        Carrier(
            name="Transportadora X",
            location="São Paulo, SP",
            email="x@example.com",
            average_delivery_days=3,
            rating=Decimal("4.5"),
            sla_percentage=Decimal("98.50"),
            status=CarrierStatus.ACTIVE.value,
        )
    )
    await db_session.commit()
```

- [ ] **Passo 2: rodar o teste e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_spec_b_schema.py -q
```

Esperado: FALHA no import —
`ModuleNotFoundError: No module named 'app.models.transportadora'`.

- [ ] **Passo 3: escrever os models**

`app/models/transportadora.py`:

```python
from enum import Enum

from sqlalchemy import Column, DateTime, Integer, Numeric, String, func, text

from app.database import Base


class CarrierStatus(str, Enum):
    """Enum de TEXTO, não booleano — o Java já distinguia mais de dois
    estados na modelagem (`CarrierStatus` é enum, não flag), e a spec pede
    que a porta preserve isso. Mesmo idioma de `StatusPedido`
    (`app/services/status_pedido.py`): o valor guardado é a string.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Carrier(Base):
    """Porte de `mobile_hybrid_app/api/.../carrier/entity/Carrier.java`.

    Em INGLÊS — tabela e colunas — porque este agregado nasce com dois
    clientes: o painel Angular (`web-admin/src/app/core/models/carrier.model.ts`,
    que já lê `name`/`location`/`averageDeliveryDays`/`slaPercentage`) e a
    rota `/carriers` do gateway. É o mesmo critério que pôs `products` e
    `orders` em inglês (ver docstring de `app/models/produto.py::Product`).

    Larguras copiadas do Java, não escolhidas aqui: `name` 150,
    `location` 150, `email` 254, `status` 20, `rating` Numeric(2,1),
    `sla_percentage` Numeric(5,2).
    """

    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, index=True)
    location = Column(String(150), nullable=False)
    email = Column(String(254), nullable=False)
    average_delivery_days = Column(Integer, nullable=False, default=0, server_default=text("0"))
    rating = Column(Numeric(2, 1), nullable=False, default=0, server_default=text("0"))
    sla_percentage = Column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    # `default=` cobre insert pelo ORM; `server_default` cobre insert que
    # passa por fora dele — mesmo par usado em `Fornecedor.ativo` e
    # `Order.status`.
    status = Column(
        String(20),
        nullable=False,
        default=CarrierStatus.ACTIVE.value,
        server_default=text("'ACTIVE'"),
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

`app/models/estoque_ajuste.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EstoqueAjuste(Base):
    """Porte de `InventoryAdjustment` do Java. Trilha de auditoria de estoque.

    Guarda `quantidade_anterior` e `quantidade_nova` (os dois campos do
    Java), NÃO o delta: o delta é `nova - anterior`, e gravá-lo criaria uma
    terceira fonte da verdade para o mesmo fato, que pode divergir. O schema
    Pydantic o expõe como campo calculado (`app/schemas/estoque.py`).

    Em PORTUGUÊS, ao contrário de `carriers`: este agregado não tem cliente
    próprio — ele é lido através de `/products/{id}/stock-adjustments`, que é
    uma sub-rota de produto. Mesmo critério de `estoque` e `ocorrencias`.

    Sem `ondelete` no FK, de propósito: uma linha de estoque apagada não pode
    levar sua auditoria junto. Um ajuste que não deixa rastro é
    indistinguível de uma perda de dado, e é exatamente isso que esta tabela
    existe para impedir.
    """

    __tablename__ = "estoque_ajustes"

    id = Column(Integer, primary_key=True)
    estoque_id = Column(Integer, ForeignKey("estoque.id"), nullable=False, index=True)
    quantidade_anterior = Column(Integer, nullable=False)
    quantidade_nova = Column(Integer, nullable=False)
    motivo = Column(String(300), nullable=False)
    # Quem fez o ajuste. UUID do `sub` do JWT; sem FK porque o dono do
    # usuário é o auth-users-service, com banco próprio.
    autor_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

Em `app/models/produto.py`, dentro de `class Fornecedor`, depois de `ativo`:

```python
    # Origem de expedição. Todo produto tem estoque, todo estoque tem
    # fornecedor, todo fornecedor tem origem — é isso que evita um caminho
    # especial de código para "produto sem parceiro". Os produtos próprios do
    # Edu pertencem a um fornecedor "Edu" criado pelo seed como qualquer
    # outro (ver `app/seeds/parceiros.py`).
    #
    # `origem_rotulo` é NOT NULL com default "" porque as linhas de
    # `fornecedores` que já existem no banco do usuário não têm origem, e uma
    # coluna NOT NULL sem default falharia o ALTER TABLE nelas.
    #
    # Numeric(9, 6), não Float: 6 casas decimais dão ~11 cm de resolução, e a
    # spec C lê estas colunas para montar rota. Float acumularia erro de
    # arredondamento numa coordenada que atravessa JSON duas vezes.
    origem_rotulo = Column(String(120), nullable=False, default="", server_default=text("''"))
    origem_lat = Column(Numeric(9, 6), nullable=True)
    origem_lng = Column(Numeric(9, 6), nullable=True)
```

Em `class Product`, depois de `name`:

```python
    # `sku` e `active` chegam com a task 1 da spec B para o painel Angular
    # poder cadastrar e desativar produto (`web-admin/src/app/shared/
    # product-form-modal/`, que já os pede). `sku` é único e 60 caracteres,
    # copiado de `Product.java`.
    #
    # `server_default=''` mais unicidade parecem brigar: a segunda linha com
    # sku vazio violaria o índice. Por isso o índice é ÚNICO PARCIAL, criado
    # na revision com `postgresql_where=(sku != '')` — o mesmo idioma do
    # `ix_payment_methods_one_default_per_user` (`app/models/pagamento.py`).
    # Sem isso, a migration falharia no banco do usuário, que já tem seis
    # produtos semeados sem sku.
    sku = Column(String(60), nullable=False, default="", server_default=text("''"))
    active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
```

e no `__table_args__` de `Product` (a classe hoje não tem um — criar):

```python
    __table_args__ = (
        Index("uq_products_sku", "sku", unique=True, postgresql_where=text("sku <> ''")),
    )
```

> **Atenção do implementador:** o teste do passo 1 assere
> `cols["sku"].unique is True`. Com índice parcial em `__table_args__`, a
> coluna NÃO tem `unique=True` — `Column.unique` fica `None`. Trocar aquela
> asserção por:
> ```python
> from sqlalchemy import text as sa_text
> idx = {i.name: i for i in Product.__table__.indexes}["uq_products_sku"]
> assert idx.unique is True
> assert "sku <> ''" in str(idx.dialect_options["postgresql"]["where"])
> ```
> Esta é a única asserção do passo 1 que muda, e ela muda porque a medição
> (índice parcial obrigatório por causa das seis linhas já semeadas) só ficou
> clara ao escrever a revision. Ajustar o teste **antes** de rodar o passo 4,
> e registrar o motivo no relatório da task.

Em `class Estoque`, depois de `quantidade`:

```python
    # Piso de reposição. Alimenta o filtro `lowStock` e o rótulo
    # NORMAL/LOW_STOCK/OUT_OF_STOCK do painel — no Java isso morava em
    # `Product.minimumStock`, mas aqui o estoque é por (produto, fornecedor)
    # e um mesmo produto pode ter piso diferente em fornecedores diferentes.
    # O piso pertence à linha que ele governa.
    estoque_minimo = Column(Integer, nullable=False, default=0, server_default=text("0"))
```

Em `app/models/ocorrencia.py`, depois de `status`:

```python
    # A ocorrência continua sendo SEMPRE de um pedido (`pedido_id` é NOT
    # NULL). A transportadora é uma DIMENSÃO dela, não um segundo dono — é
    # por isso que o `CarrierOccurrence` do Java não virou tabela separada.
    # O painel de transportadoras lê ocorrências agrupando por esta coluna.
    transportadora_id = Column(
        Integer, ForeignKey("carriers.id"), nullable=True, index=True
    )
```

e o comentário da coluna `tipo` passa a listar os cinco valores:

```python
    # FALTA_ESTOQUE | ATRASO_ENTREGA | DANO | FALHA_ENTREGA | OUTRO
    # Os três últimos são a porta de `OccurrenceType` do Java; o
    # `DELIVERY_DELAY` de lá é o `ATRASO_ENTREGA` que já existia aqui, e por
    # isso não virou um sexto valor.
    tipo = Column(String(30), nullable=False)
```

Em `app/models/pedido.py`, dentro de `class Order`, depois do bloco `ship_*`:

```python
    # Origem de expedição, RESOLVIDA na criação do pedido a partir do
    # fornecedor dos itens e congelada aqui. A spec C lê estas colunas para
    # simular a rota e NÃO recalcula a origem — o estoque pode mudar de
    # fornecedor depois que o pedido saiu. Mesmo espírito do snapshot
    # `ship_*` logo acima: um pedido é registro histórico.
    #
    # Nullable: pedidos criados antes desta spec não têm origem, e o carrinho
    # de um catálogo sem fornecedor cadastrado também não teria.
    origem_rotulo = Column(String(120), nullable=True)
    origem_lat = Column(Numeric(9, 6), nullable=True)
    origem_lng = Column(Numeric(9, 6), nullable=True)
```

Ajustar os imports no topo de cada arquivo (`Boolean`, `Index`, `Numeric`,
`ForeignKey` conforme o que faltar) — `uv run ruff check .` acusa o que sobrar.

Em `tests/conftest.py`, dentro de `test_engine`, junto dos seis imports
existentes (linhas 57-63), em ordem alfabética:

```python
    from app.models import estoque_ajuste as estoque_ajuste_models  # noqa: F401
    from app.models import transportadora as transportadora_models  # noqa: F401
```

- [ ] **Passo 4: rodar o teste e confirmar que passa**

```bash
cd back-end/commerce-service && uv run pytest tests/test_spec_b_schema.py -q
```

Esperado: 9 passed.

- [ ] **Passo 5: escrever a revision alembic**

`alembic/versions/b1a2c3d4e5f6_spec_b_schema.py`:

```python
"""spec B: partner origin, stock audit, carriers, order origin

Revision ID: b1a2c3d4e5f6
Revises: c90210e9965c
Create Date: 2026-09-08

ADITIVA POR CONSTRUÇÃO, e é isso que a distingue de três vizinhas desta
cadeia. `1308bb221890`, `bd410bba0e85` e `099099b0c1a8` são reconstruções:
elas apagam dado de propósito, e por isso o `downgrade()` das três levanta
`RuntimeError` incondicional. Esta não apaga nada — só acrescenta colunas com
`server_default` e cria duas tabelas —, então o `downgrade()` abaixo é REAL e
reversível. Não copie o padrão de `raise` das vizinhas para cá: aqui ele
seria mentira.

O índice de `sku` é ÚNICO PARCIAL (`WHERE sku <> ''`). Medido: o
`commerce_db` do usuário já tem seis produtos semeados
(`app/seeds/products.py::SEED_PRODUCTS`), e a coluna nasce com
`server_default=''` para o ALTER TABLE poder ser NOT NULL. Um índice único
TOTAL falharia no segundo produto existente. O idioma é o mesmo de
`ix_payment_methods_one_default_per_user` (`942f75a9a3f2`).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1a2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c90210e9965c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Fornecedor vira parceiro: origem de expedição ────────────────────
    op.add_column(
        "fornecedores",
        sa.Column(
            "origem_rotulo", sa.String(length=120), nullable=False, server_default=sa.text("''")
        ),
    )
    op.add_column("fornecedores", sa.Column("origem_lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("fornecedores", sa.Column("origem_lng", sa.Numeric(9, 6), nullable=True))

    # ── Produto ganha sku e active ───────────────────────────────────────
    op.add_column(
        "products",
        sa.Column("sku", sa.String(length=60), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "products",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index(
        "uq_products_sku",
        "products",
        ["sku"],
        unique=True,
        postgresql_where=sa.text("sku <> ''"),
    )

    # ── Estoque ganha piso de reposição ──────────────────────────────────
    op.add_column(
        "estoque",
        sa.Column("estoque_minimo", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # ── Trilha de auditoria de estoque ───────────────────────────────────
    op.create_table(
        "estoque_ajustes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("estoque_id", sa.Integer(), sa.ForeignKey("estoque.id"), nullable=False),
        sa.Column("quantidade_anterior", sa.Integer(), nullable=False),
        sa.Column("quantidade_nova", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(length=300), nullable=False),
        sa.Column("autor_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_estoque_ajustes_estoque_id", "estoque_ajustes", ["estoque_id"])
    op.create_index("ix_estoque_ajustes_autor_id", "estoque_ajustes", ["autor_id"])

    # ── Transportadora ───────────────────────────────────────────────────
    op.create_table(
        "carriers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("location", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column(
            "average_delivery_days", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False, server_default=sa.text("0")),
        sa.Column("sla_percentage", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_carriers_name", "carriers", ["name"])
    op.create_index("ix_carriers_status", "carriers", ["status"])

    # ── Ocorrência ganha a dimensão de transportadora ────────────────────
    op.add_column("ocorrencias", sa.Column("transportadora_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ocorrencias_transportadora_id",
        "ocorrencias",
        "carriers",
        ["transportadora_id"],
        ["id"],
    )
    op.create_index("ix_ocorrencias_transportadora_id", "ocorrencias", ["transportadora_id"])

    # ── Pedido carrega a origem congelada ────────────────────────────────
    op.add_column("orders", sa.Column("origem_rotulo", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("origem_lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("orders", sa.Column("origem_lng", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "origem_lng")
    op.drop_column("orders", "origem_lat")
    op.drop_column("orders", "origem_rotulo")

    op.drop_index("ix_ocorrencias_transportadora_id", table_name="ocorrencias")
    op.drop_constraint("fk_ocorrencias_transportadora_id", "ocorrencias", type_="foreignkey")
    op.drop_column("ocorrencias", "transportadora_id")

    op.drop_index("ix_carriers_status", table_name="carriers")
    op.drop_index("ix_carriers_name", table_name="carriers")
    op.drop_table("carriers")

    op.drop_index("ix_estoque_ajustes_autor_id", table_name="estoque_ajustes")
    op.drop_index("ix_estoque_ajustes_estoque_id", table_name="estoque_ajustes")
    op.drop_table("estoque_ajustes")

    op.drop_column("estoque", "estoque_minimo")

    op.drop_index("uq_products_sku", table_name="products")
    op.drop_column("products", "active")
    op.drop_column("products", "sku")

    op.drop_column("fornecedores", "origem_lng")
    op.drop_column("fornecedores", "origem_lat")
    op.drop_column("fornecedores", "origem_rotulo")
```

- [ ] **Passo 6: provar que a revision aplica — contra `commerce_test`**

Ver D4. `commerce_test` é o banco de scratch da suíte, não de desenvolvimento.

```bash
cd back-end/commerce-service

# 1. Zerar o banco de scratch. Este é exatamente o que
#    tests/conftest.py::test_engine faz no começo de cada sessão.
docker exec -i edu-postgres psql -U edu -d postgres \
  -c "DROP DATABASE IF EXISTS commerce_test;" -c "CREATE DATABASE commerce_test OWNER edu;"

# 2. Aplicar a cadeia INTEIRA, do zero ao head novo.
DATABASE_URL='postgresql+asyncpg://edu:edu@localhost:5433/commerce_test' \
  uv run alembic upgrade head

# 3. Conferir que o head é a revision nova e que as colunas existem.
DATABASE_URL='postgresql+asyncpg://edu:edu@localhost:5433/commerce_test' \
  uv run alembic current
docker exec -i edu-postgres psql -U edu -d commerce_test -c "\d fornecedores" \
  -c "\d products" -c "\d estoque" -c "\d estoque_ajustes" -c "\d carriers" \
  -c "\d ocorrencias" -c "\d orders"

# 4. Provar que o downgrade é REAL (as três vizinhas destrutivas levantam;
#    esta não pode levantar).
DATABASE_URL='postgresql+asyncpg://edu:edu@localhost:5433/commerce_test' \
  uv run alembic downgrade -1
DATABASE_URL='postgresql+asyncpg://edu:edu@localhost:5433/commerce_test' \
  uv run alembic upgrade head
```

Esperado no passo 3: `alembic current` mostra `b1a2c3d4e5f6 (head)`;
`\d fornecedores` mostra `origem_rotulo | character varying(120) | not null`;
`\d products` mostra `sku`, `active` e o índice
`"uq_products_sku" UNIQUE, btree (sku) WHERE sku::text <> ''::text`;
`\d carriers` e `\d estoque_ajustes` existem.
Esperado no passo 4: os dois comandos saem 0, sem `RuntimeError`.

**Colar a saída real dos passos 3 e 4 no relatório da task.** Sem ela, esta
task não está provada — é a única prova de migration desta cadeia inteira.

Depois, restaurar o banco para o que a suíte espera:

```bash
cd back-end/commerce-service && uv run pytest -q
```

(`test_engine` faz `drop_all` + `create_all` e devolve `commerce_test` ao
estado normal; não é preciso mais nada.)

- [ ] **Passo 7: rodar a suíte inteira e o lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: **376 passed** (367 + 9). Se algum dos 367 falhar, a task está
errada — nenhuma coluna adicionada com `server_default` deveria quebrar teste
existente.

- [ ] **Passo 8: commit**

```bash
cd /home/elias/programming/fiap/estuda_app
git add back-end/commerce-service/app/models back-end/commerce-service/alembic/versions \
        back-end/commerce-service/tests/conftest.py \
        back-end/commerce-service/tests/test_spec_b_schema.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): add the spec B schema

Partner shipping origin on fornecedores, sku/active on products, a minimum
on estoque, the estoque_ajustes audit trail, the carriers table ported from
the Java Carrier entity, a carrier dimension on ocorrencias, and the frozen
shipping origin on orders. One additive revision on top of c90210e9965c,
with a real reversible downgrade — unlike the three reconstruction revisions
upstream, this one destroys nothing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: Parceiros — serviço, rotas `/partners` e roteamento no gateway

O CRUD de admin mais a leitura pública de parceiros ativos. O gateway entra
nesta task porque sem ele o painel recebe 404 e o erro parece do Angular
(a spec diz isso em texto).

**Files:**
- Criar: `back-end/commerce-service/app/schemas/parceiro.py`
- Criar: `back-end/commerce-service/app/services/parceiros.py`
- Criar: `back-end/commerce-service/app/routers/parceiros.py`
- Modificar: `back-end/commerce-service/app/main.py`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Modificar: `back-end/api-gateway/app/routing.py:16-25`
- Criar: `back-end/commerce-service/tests/test_partners_routes.py`
- Modificar: `back-end/api-gateway/tests/test_routing.py` (nome exato: ver passo 1)

**Interfaces:**
- Consome da task 1: `Fornecedor.origem_rotulo/origem_lat/origem_lng`.
- Produz para as tasks 7, 8, 9, 11, 12 e 13:

```python
# app/services/parceiros.py
async def listar_parceiros(
    db: AsyncSession, *, apenas_ativos: bool = False, limit: int, offset: int
) -> tuple[list[Fornecedor], int]: ...
async def obter_parceiro(db: AsyncSession, parceiro_id: int) -> Fornecedor: ...  # raise ParceiroNotFoundError
async def criar_parceiro(db: AsyncSession, data: ParceiroIn) -> Fornecedor: ...
async def atualizar_parceiro(db: AsyncSession, parceiro_id: int, data: ParceiroIn) -> Fornecedor: ...

# app/exceptions.py
class ParceiroNotFoundError(Exception): ...
```

Rotas: `GET /partners` (qualquer papel autenticado, `active=true|false`,
paginado), `GET /partners/{id}` (autenticado), `POST /partners` (admin),
`PUT /partners/{id}` (admin).

- [ ] **Passo 1: medir o nome real do arquivo de teste do gateway**

```bash
cd back-end/api-gateway && ls tests/ && grep -rn "SERVICE_MAP\|resolve_destination" tests/ | head
```

Usar o arquivo que essa saída mostrar. **Não** presumir `test_routing.py`.

- [ ] **Passo 2: escrever os testes que falham**

`back-end/commerce-service/tests/test_partners_routes.py`:

```python
"""Cobertura de `/partners` — o CRUD de parceiro da spec B.

`Fornecedor` é o parceiro; a tabela continua `fornecedores` e a rota é
`/partners` (ver Global Constraints do plano da spec B). Não há entidade
nova.
"""

from decimal import Decimal

import pytest
from edu_common.security import create_access_token

from app.config import settings
from app.models.produto import Fornecedor


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _seed_parceiro(db_session, *, nome: str, ativo: bool = True) -> Fornecedor:
    parceiro = Fornecedor(
        nome=nome,
        contato="contato@example.com",
        ativo=ativo,
        origem_rotulo="Cajamar, SP",
        origem_lat=Decimal("-23.355800"),
        origem_lng=Decimal("-46.876400"),
    )
    db_session.add(parceiro)
    await db_session.commit()
    await db_session.refresh(parceiro)
    return parceiro


async def test_listing_requires_authentication(client):
    assert (await client.get("/partners")).status_code == 401


async def test_listing_is_open_to_any_authenticated_role(client, db_session):
    await _seed_parceiro(db_session, nome="Leroy Merlin")
    response = await client.get("/partners", headers=headers_for("student"))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_listing_is_paginated_and_capped(client):
    assert (await client.get("/partners?limit=5000", headers=headers_for("admin"))).status_code == 422


async def test_active_filter_hides_the_disabled_partner(client, db_session):
    await _seed_parceiro(db_session, nome="Leroy Merlin", ativo=True)
    await _seed_parceiro(db_session, nome="Desativada", ativo=False)

    todos = await client.get("/partners", headers=headers_for("student"))
    ativos = await client.get("/partners?active=true", headers=headers_for("student"))

    assert todos.json()["total"] == 2
    assert ativos.json()["total"] == 1
    assert [p["nome"] for p in ativos.json()["items"]] == ["Leroy Merlin"]


async def test_response_exposes_only_declared_fields(client, db_session):
    await _seed_parceiro(db_session, nome="Leroy Merlin")
    row = (await client.get("/partners", headers=headers_for("admin"))).json()["items"][0]
    assert set(row) == {
        "id", "nome", "contato", "ativo", "origem_rotulo", "origem_lat", "origem_lng",
    }


async def test_creating_a_partner_requires_admin(client):
    payload = {"nome": "X", "origem_rotulo": "São Paulo, SP"}
    for papel in ("student", "separador", "entregador"):
        response = await client.post("/partners", json=payload, headers=headers_for(papel))
        assert response.status_code == 403, papel


async def test_admin_creates_a_partner_with_an_origin(client):
    response = await client.post(
        "/partners",
        json={
            "nome": "Leroy Merlin",
            "contato": "parceria@leroymerlin.com.br",
            "ativo": True,
            "origem_rotulo": "Cajamar, SP",
            "origem_lat": "-23.3558",
            "origem_lng": "-46.8764",
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["origem_rotulo"] == "Cajamar, SP"
    assert body["origem_lat"] == "-23.355800"


async def test_creating_rejects_a_name_over_the_column_width(client):
    response = await client.post(
        "/partners",
        json={"nome": "x" * 151, "origem_rotulo": "São Paulo, SP"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_updating_a_partner_flips_the_active_flag(client, db_session):
    parceiro = await _seed_parceiro(db_session, nome="Leroy Merlin")
    response = await client.put(
        f"/partners/{parceiro.id}",
        json={"nome": "Leroy Merlin", "ativo": False, "origem_rotulo": "Cajamar, SP"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 200
    assert response.json()["ativo"] is False


async def test_updating_an_unknown_partner_is_404(client):
    response = await client.put(
        "/partners/999999",
        json={"nome": "X", "origem_rotulo": "São Paulo, SP"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 404


async def test_detail_of_an_unknown_partner_is_404(client):
    assert (await client.get("/partners/999999", headers=headers_for("admin"))).status_code == 404


@pytest.mark.parametrize("campo", ["origem_lat", "origem_lng"])
async def test_origin_coordinates_are_optional(client, campo):
    payload = {"nome": f"Sem {campo}", "origem_rotulo": "São Paulo, SP"}
    response = await client.post("/partners", json=payload, headers=headers_for("admin"))
    assert response.status_code == 201
    assert response.json()[campo] is None
```

No arquivo de teste do gateway que o passo 1 apontou, acrescentar:

```python
def test_partners_and_carriers_route_to_commerce():
    """Sem estas duas entradas o painel Angular recebe 404 do gateway e o
    erro parece vir do próprio Angular. `products`, `orders`, `cart`,
    `occurrences` e `admin` já estavam mapeados."""
    from app.routing import SERVICE_MAP

    assert SERVICE_MAP["partners"] == "commerce"
    assert SERVICE_MAP["carriers"] == "commerce"
```

- [ ] **Passo 3: rodar os testes e confirmar que falham**

```bash
cd back-end/commerce-service && uv run pytest tests/test_partners_routes.py -q
cd ../api-gateway && uv run pytest -q -k partners_and_carriers
```

Esperado: no commerce, 13 falhas com 404 (`/partners` não existe); no gateway,
`KeyError: 'partners'`.

- [ ] **Passo 4: escrever o schema**

`app/schemas/parceiro.py`:

```python
"""Schema público de parceiro.

Campos um a um (regra 6): `Fornecedor` pode ganhar coluna interna (margem
negociada, contrato) que não pode vazar para o app só por existir no banco.

As coordenadas saem como STRING, não float — mesmo critério de
`ProductOut.price` (`app/schemas/produto.py`): o cliente nunca herda erro de
arredondamento de float num valor que atravessa JSON. O `Numeric(9, 6)` do
model vira "-23.355800", com as seis casas preservadas.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ParceiroIn(BaseModel):
    nome: str = Field(max_length=150)
    contato: str | None = Field(default=None, max_length=150)
    ativo: bool = True
    origem_rotulo: str = Field(max_length=120)
    origem_lat: Decimal | None = Field(default=None, ge=-90, le=90)
    origem_lng: Decimal | None = Field(default=None, ge=-180, le=180)


class ParceiroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    contato: str | None = None
    ativo: bool
    origem_rotulo: str = ""
    origem_lat: Decimal | None = None
    origem_lng: Decimal | None = None

    @field_serializer("origem_lat", "origem_lng")
    def _coord_as_string(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.6f}"


class ParceiroList(BaseModel):
    """Envelope igual ao de `ProductList` — `{items, total, limit, offset}`.
    A frota inteira usa esse formato; o painel Angular é reescrito para ele
    (decisão D9 do plano), não o contrário."""

    items: list[ParceiroOut]
    total: int
    limit: int
    offset: int
```

- [ ] **Passo 5: escrever o serviço**

`app/services/parceiros.py`:

```python
"""Regra de parceiro. O filtro por ativo é uma REGRA, não um `if` por nome.

A spec proíbe `if parceiro == "leroy"` em qualquer caminho de decisão: quem
decide se uma seção aparece é a coluna `ativo`, e desativar o parceiro no
painel esvazia a seção sem tocar em código. A string "leroy" só existe em
dado de seed (`app/seeds/parceiros.py`) — o teste
`test_no_partner_name_in_a_decision_path` (task 11) trava isso.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ParceiroNotFoundError
from app.models.produto import Fornecedor
from app.schemas.parceiro import ParceiroIn


async def listar_parceiros(
    db: AsyncSession, *, apenas_ativos: bool = False, limit: int, offset: int
) -> tuple[list[Fornecedor], int]:
    stmt = select(Fornecedor)
    count_stmt = select(func.count()).select_from(Fornecedor)
    if apenas_ativos:
        stmt = stmt.where(Fornecedor.ativo.is_(True))
        count_stmt = count_stmt.where(Fornecedor.ativo.is_(True))

    stmt = stmt.order_by(Fornecedor.nome).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def obter_parceiro(db: AsyncSession, parceiro_id: int) -> Fornecedor:
    parceiro = await db.get(Fornecedor, parceiro_id)
    if parceiro is None:
        raise ParceiroNotFoundError()
    return parceiro


async def criar_parceiro(db: AsyncSession, data: ParceiroIn) -> Fornecedor:
    parceiro = Fornecedor(**data.model_dump())
    db.add(parceiro)
    await db.commit()
    await db.refresh(parceiro)
    return parceiro


async def atualizar_parceiro(
    db: AsyncSession, parceiro_id: int, data: ParceiroIn
) -> Fornecedor:
    parceiro = await obter_parceiro(db, parceiro_id)
    for campo, valor in data.model_dump().items():
        setattr(parceiro, campo, valor)
    await db.commit()
    await db.refresh(parceiro)
    return parceiro
```

Em `app/exceptions.py`, no fim:

```python
class ParceiroNotFoundError(Exception):
    """Nenhum parceiro (`Fornecedor`) com o id dado. O router traduz em 404
    "Partner not found".

    Sufixo `Error` por N818, como todas as outras deste módulo.
    """
```

- [ ] **Passo 6: escrever o router**

`app/routers/parceiros.py`:

```python
"""CRUD de parceiro. A tabela é `fornecedores`; a rota é `/partners`.

O rename da tabela seria uma revision a mais e a spec não o pede — a decisão
está registrada nas Global Constraints do plano da spec B.

`GET` é aberto a QUALQUER papel autenticado, não só a admin: o app do aluno
precisa saber quais seções de parceiro mostrar (`GET /partners?active=true`,
fluxo de dados da spec). Escrita é só admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, requer_papel
from app.exceptions import ParceiroNotFoundError
from app.schemas.parceiro import ParceiroIn, ParceiroList, ParceiroOut
from app.services import parceiros as services

router = APIRouter(prefix="/partners", tags=["partners"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")


@router.get("", response_model=ParceiroList)
async def listar_parceiros(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    active: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ParceiroList:
    items, total = await services.listar_parceiros(
        db, apenas_ativos=active, limit=limit, offset=offset
    )
    return ParceiroList(
        items=[ParceiroOut.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{parceiro_id}", response_model=ParceiroOut)
async def detalhe_parceiro(
    parceiro_id: int,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParceiroOut:
    try:
        return ParceiroOut.model_validate(await services.obter_parceiro(db, parceiro_id))
    except ParceiroNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.post("", response_model=ParceiroOut, status_code=status.HTTP_201_CREATED)
async def criar_parceiro(
    payload: ParceiroIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> ParceiroOut:
    return ParceiroOut.model_validate(await services.criar_parceiro(db, payload))


@router.put("/{parceiro_id}", response_model=ParceiroOut)
async def atualizar_parceiro(
    parceiro_id: int,
    payload: ParceiroIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> ParceiroOut:
    try:
        return ParceiroOut.model_validate(
            await services.atualizar_parceiro(db, parceiro_id, payload)
        )
    except ParceiroNotFoundError as exc:
        raise _NOT_FOUND from exc
```

Em `app/main.py`, acrescentar `parceiros` ao import de `app.routers` (em ordem
alfabética: depois de `pagamento`) e `app.include_router(parceiros.router)`
depois de `app.include_router(admin.router)`.

Em `back-end/api-gateway/app/routing.py`, dentro de `SERVICE_MAP`, junto do
bloco do commerce (depois de `"admin": "commerce",`):

```python
    "partners": "commerce",
    "carriers": "commerce",
```

`carriers` entra aqui, junto com `partners`, e não na task 4: as duas linhas
são a mesma mudança de uma linha no mesmo dicionário, e separá-las produziria
dois commits que se tocam no mesmo lugar sem nenhum ganho de revisão.

- [ ] **Passo 7: rodar os testes e confirmar que passam**

```bash
cd back-end/commerce-service && uv run pytest tests/test_partners_routes.py -q
cd ../api-gateway && uv run pytest -q
```

Esperado: 13 passed no commerce; **37 passed** no gateway (36 + 1).

- [ ] **Passo 8: suíte inteira e lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd ../api-gateway && uv run ruff check . && uv run ruff format --check .
```

Esperado: **389 passed** no commerce (376 + 13).

- [ ] **Passo 9: commit**

```bash
cd /home/elias/programming/fiap/estuda_app
git add back-end/commerce-service/app back-end/commerce-service/tests/test_partners_routes.py \
        back-end/api-gateway
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): add the partners CRUD and route it through the gateway

Fornecedor is the partner: /partners lists, reads, creates and updates it,
paginated, with writes restricted to admin and reads open to any
authenticated role so the student app can ask which sections to show. The
active flag is the rule that empties a section — no partner name appears in
any decision path. partners and carriers join SERVICE_MAP; without them the
Angular panel gets a 404 that looks like its own bug.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Estoque com auditoria — um núcleo atômico, duas portas

Porte do `InventoryAdjustment`. Ver D7: a rota absoluta do admin que já existe
e a rota de delta que a spec pede passam pelo **mesmo** caminho de escrita.

**Files:**
- Criar: `back-end/commerce-service/app/services/estoque.py`
- Modificar: `back-end/commerce-service/app/schemas/estoque.py`
- Modificar: `back-end/commerce-service/app/routers/produtos.py`
- Modificar: `back-end/commerce-service/app/routers/admin.py:155-186`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Modificar: `back-end/commerce-service/tests/test_admin_routes.py:106-111`
- Criar: `back-end/commerce-service/tests/test_stock_adjustments.py`

**Interfaces:**
- Consome da task 1: `EstoqueAjuste`, `Estoque.estoque_minimo`.
- Produz para as tasks 6, 11 e 13:

```python
# app/services/estoque.py
async def aplicar_ajuste(
    db: AsyncSession, *, estoque_id: int, delta: int, motivo: str, autor_id: uuid.UUID
) -> tuple[Estoque, EstoqueAjuste]: ...
async def definir_quantidade(
    db: AsyncSession, *, estoque_id: int, quantidade: int, motivo: str, autor_id: uuid.UUID
) -> tuple[Estoque, EstoqueAjuste]: ...
async def listar_ajustes(
    db: AsyncSession, *, produto_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[EstoqueAjuste], int]: ...
async def obter_estoque_do_produto(db: AsyncSession, produto_id: uuid.UUID) -> Estoque: ...

# app/exceptions.py
class EstoqueNotFoundError(Exception): ...
class EstoqueNegativoError(Exception): ...
```

Rotas novas: `POST /products/{product_id}/stock-adjustments` (admin, delta) e
`GET /products/{product_id}/stock-adjustments` (admin, paginado).
Rota reescrita: `PATCH /admin/inventory/{estoque_id}/adjust` passa a exigir
`motivo` e a gravar auditoria.

**Emenda declarada a teste existente:**
`tests/test_admin_routes.py:106-111`
(`test_inventory_response_exposes_only_declared_fields`) assere o conjunto
exato `{"id","produto_id","fornecedor_id","quantidade","atualizado_em"}`.
`EstoqueOut` ganha `estoque_minimo`, então o conjunto vira seis chaves. Isso é
a mesma mudança de comportamento, não escopo novo — igual à decisão 1 do
registro da spec A.

`test_inventory_adjust_rejects_a_negative_quantity` e
`test_inventory_adjust_accepts_zero` (`tests/test_admin_routes.py:248-267`)
passam a mandar `motivo` na query string. Também emenda declarada: a rota
passa a exigir motivo porque um ajuste sem motivo não é auditoria.

- [ ] **Passo 1: escrever os testes que falham**

`tests/test_stock_adjustments.py`:

```python
"""Ajuste de estoque com trilha de auditoria — porte de `InventoryAdjustment`.

O ajuste e o registro acontecem na MESMA transação, sob `with_for_update()`
na linha de estoque (regra 3 do CLAUDE.md). Um ajuste que não deixa rastro é
indistinguível de uma perda de dado.
"""

import asyncio
import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import func, select

from app.config import settings
from app.models.estoque_ajuste import EstoqueAjuste
from app.models.produto import Estoque, Fornecedor, Product

_ADMIN_SUB = "00000000-0000-0000-0000-0000000000aa"


def headers_for(role: str, sub: str = _ADMIN_SUB) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed(db_session, *, quantidade: int = 10) -> tuple[Product, Estoque]:
    fornecedor = Fornecedor(nome="Edu", origem_rotulo="Aclimação, SP")
    db_session.add(fornecedor)
    await db_session.commit()
    await db_session.refresh(fornecedor)

    produto = Product(name="Mesa", type="mobiliario", price=Decimal("399.90"), sku="MESA-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    estoque = Estoque(
        produto_id=produto.id,
        fornecedor_id=fornecedor.id,
        quantidade=quantidade,
        estoque_minimo=2,
    )
    db_session.add(estoque)
    await db_session.commit()
    await db_session.refresh(estoque)
    return produto, estoque


async def test_adjustment_requires_admin(client, db_session):
    produto, _ = await _seed(db_session)
    for papel in ("student", "separador", "entregador"):
        response = await client.post(
            f"/products/{produto.id}/stock-adjustments",
            json={"delta": 5, "motivo": "Recebimento de lote"},
            headers=headers_for(papel),
        )
        assert response.status_code == 403, papel


async def test_a_positive_delta_moves_the_quantity_and_writes_the_trail(
    client, db_session
):
    produto, estoque = await _seed(db_session, quantidade=10)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 5, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantidade_anterior"] == 10
    assert body["quantidade_nova"] == 15
    assert body["delta"] == 5
    assert body["motivo"] == "Recebimento de lote"
    assert body["autor_id"] == _ADMIN_SUB

    await db_session.refresh(estoque)
    assert estoque.quantidade == 15

    trilha = (await db_session.execute(select(EstoqueAjuste))).scalars().all()
    assert len(trilha) == 1
    assert trilha[0].estoque_id == estoque.id


async def test_a_negative_delta_is_accepted_down_to_zero(client, db_session):
    produto, estoque = await _seed(db_session, quantidade=3)
    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": -3, "motivo": "Perda"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 201
    assert response.json()["quantidade_nova"] == 0


async def test_an_adjustment_that_would_go_negative_is_422_and_writes_nothing(
    client, db_session
):
    """422 DENTRO da transação, sem gravar — nem o estoque nem a trilha.
    Gravar a linha de auditoria de um ajuste recusado seria pior que não
    auditar: a trilha passaria a mentir."""
    produto, estoque = await _seed(db_session, quantidade=3)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": -4, "motivo": "Perda"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 422
    await db_session.refresh(estoque)
    assert estoque.quantidade == 3
    total = (await db_session.execute(select(func.count()).select_from(EstoqueAjuste))).scalar_one()
    assert total == 0


async def test_a_reason_is_mandatory_and_capped_at_the_column_width(client, db_session):
    produto, _ = await _seed(db_session)
    sem_motivo = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1},
        headers=headers_for("admin"),
    )
    assert sem_motivo.status_code == 422

    motivo_gigante = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "x" * 301},
        headers=headers_for("admin"),
    )
    assert motivo_gigante.status_code == 422


async def test_adjusting_an_unstocked_product_is_404(client, db_session):
    produto = Product(name="Sem estoque", type="apostila", price=Decimal("1.00"), sku="X-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 404


async def test_concurrent_deltas_do_not_lose_an_adjustment(client, db_session):
    """Duas adições simultâneas de +5 sobre 10 têm que dar 20, não 15.

    Sem `with_for_update()` as duas leem 10, as duas gravam 15, e um lote
    inteiro some do sistema sem nenhum erro aparecer. Este é o teste que
    prova a regra 3 do CLAUDE.md nesta rota; ele NÃO é opinião sobre estilo.
    """
    produto, estoque = await _seed(db_session, quantidade=10)

    async def _ajustar():
        return await client.post(
            f"/products/{produto.id}/stock-adjustments",
            json={"delta": 5, "motivo": "Recebimento de lote"},
            headers=headers_for("admin"),
        )

    respostas = await asyncio.gather(_ajustar(), _ajustar())
    assert {r.status_code for r in respostas} == {201}

    await db_session.refresh(estoque)
    assert estoque.quantidade == 20
    total = (await db_session.execute(select(func.count()).select_from(EstoqueAjuste))).scalar_one()
    assert total == 2


async def test_listing_the_trail_is_admin_only_and_paginated(client, db_session):
    produto, _ = await _seed(db_session)
    await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )

    negado = await client.get(
        f"/products/{produto.id}/stock-adjustments", headers=headers_for("student")
    )
    assert negado.status_code == 403

    capado = await client.get(
        f"/products/{produto.id}/stock-adjustments?limit=5000", headers=headers_for("admin")
    )
    assert capado.status_code == 422

    ok = await client.get(
        f"/products/{produto.id}/stock-adjustments", headers=headers_for("admin")
    )
    assert ok.status_code == 200
    assert ok.json()["total"] == 1


async def test_the_admin_absolute_route_also_writes_the_trail(client, db_session):
    """`PATCH /admin/inventory/{id}/adjust` é a porta ABSOLUTA e a rota nova
    é a porta de DELTA — as duas passam pelo mesmo núcleo, então as duas
    deixam rastro. Antes desta task a rota do admin não deixava nenhum."""
    _, estoque = await _seed(db_session, quantidade=10)

    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=4&motivo=Invent%C3%A1rio",
        headers=headers_for("admin"),
    )

    assert response.status_code == 200
    assert response.json()["quantidade"] == 4

    trilha = (await db_session.execute(select(EstoqueAjuste))).scalars().all()
    assert len(trilha) == 1
    assert (trilha[0].quantidade_anterior, trilha[0].quantidade_nova) == (10, 4)
    assert trilha[0].motivo == "Inventário"
```

Emendar `tests/test_admin_routes.py`:

```python
# linha 110-111, dentro de test_inventory_response_exposes_only_declared_fields
    assert set(row) == {
        "id",
        "produto_id",
        "fornecedor_id",
        "quantidade",
        "estoque_minimo",
        "atualizado_em",
    }
```

e nas duas rotas de ajuste do mesmo arquivo, acrescentar `&motivo=Teste` à
query string (linhas 252-255 e 264-267).

- [ ] **Passo 2: rodar os testes e confirmar que falham**

```bash
cd back-end/commerce-service && uv run pytest tests/test_stock_adjustments.py -q
```

Esperado: 9 falhas — 404 nas rotas novas, e a última com
`ModuleNotFoundError` ou 422 por `motivo` desconhecido.

- [ ] **Passo 3: escrever as exceções e o schema**

Em `app/exceptions.py`:

```python
class EstoqueNotFoundError(Exception):
    """Não há linha de estoque para o produto (ou id de estoque) pedido. O
    router traduz em 404 "Stock record not found".

    Sufixo `Error` por N818.
    """


class EstoqueNegativoError(Exception):
    """O ajuste levaria a quantidade abaixo de zero. O router traduz em 422.

    Levantada DENTRO da transação, antes de qualquer escrita — nem o estoque
    nem a linha de auditoria são gravados. Auditar um ajuste recusado faria a
    trilha mentir. Mesma regra do Java (`Inventory.adjustTo` levanta
    `BusinessException` antes de construir o `InventoryAdjustment`).

    Sufixo `Error` por N818.
    """
```

Em `app/schemas/estoque.py`, acrescentar `estoque_minimo` a `EstoqueOut` e
criar:

```python
class AjusteEstoqueIn(BaseModel):
    """`delta`, não quantidade absoluta: a rota é `POST .../stock-adjustments`,
    e o que se posta é o ajuste, não o novo saldo. A porta absoluta é
    `PATCH /admin/inventory/{id}/adjust`, que converte para delta dentro do
    lock e chama o mesmo núcleo (ver app/services/estoque.py)."""

    delta: int = Field(ne=0)
    motivo: str = Field(min_length=1, max_length=300)


class EstoqueAjusteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estoque_id: int
    quantidade_anterior: int
    quantidade_nova: int
    motivo: str
    autor_id: uuid.UUID
    criado_em: datetime

    @computed_field
    @property
    def delta(self) -> int:
        """Derivado, não guardado. Gravar `delta` além das duas quantidades
        criaria uma terceira fonte da verdade para o mesmo fato, capaz de
        divergir das outras duas."""
        return self.quantidade_nova - self.quantidade_anterior


class EstoqueAjusteList(BaseModel):
    items: list[EstoqueAjusteOut]
    total: int
    limit: int
    offset: int
```

Imports novos no topo do arquivo: `from pydantic import Field, computed_field`.

> `Field(ne=0)` não existe no Pydantic. Usar um `field_validator`:
> ```python
>     @field_validator("delta")
>     @classmethod
>     def _delta_nao_pode_ser_zero(cls, v: int) -> int:
>         if v == 0:
>             raise ValueError("delta não pode ser zero")
>         return v
> ```
> Corrigido aqui em vez de deixar o implementador descobrir em runtime.

- [ ] **Passo 4: escrever o serviço**

`app/services/estoque.py`:

```python
"""Ajuste de estoque com trilha de auditoria. Porte de `InventoryAdjustment`.

UM núcleo de escrita, DUAS portas. `aplicar_ajuste` recebe delta;
`definir_quantidade` recebe o valor absoluto, converte para delta DENTRO do
mesmo lock e delega. As duas portas existem porque o painel Angular manda
valor absoluto (`PATCH /inventory/{productId}` com `{quantity, reason}`,
igual ao `InventoryService.adjust` do Java) e a spec pede uma rota de delta.
Duplicar o caminho de escrita para atender as duas seria duplicar o lock e a
regra de saldo negativo.

`with_for_update()` aqui não é ornamento, ao contrário do que era na rota
absoluta original (`admin.py`, cujo comentário registra que, gravando valor
ABSOLUTO, o último commit vence com ou sem lock). Com delta, o read→write é
real: sem o lock, dois +5 concorrentes sobre 10 produzem 15, e um lote some.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EstoqueNegativoError, EstoqueNotFoundError
from app.models.estoque_ajuste import EstoqueAjuste
from app.models.produto import Estoque


async def obter_estoque_do_produto(db: AsyncSession, produto_id: uuid.UUID) -> Estoque:
    estoque = (
        await db.execute(select(Estoque).where(Estoque.produto_id == produto_id))
    ).scalar_one_or_none()
    if estoque is None:
        raise EstoqueNotFoundError()
    return estoque


async def aplicar_ajuste(
    db: AsyncSession, *, estoque_id: int, delta: int, motivo: str, autor_id: uuid.UUID
) -> tuple[Estoque, EstoqueAjuste]:
    estoque = (
        await db.execute(select(Estoque).where(Estoque.id == estoque_id).with_for_update())
    ).scalar_one_or_none()
    if estoque is None:
        raise EstoqueNotFoundError()

    anterior = estoque.quantidade
    nova = anterior + delta
    if nova < 0:
        # Antes de qualquer escrita. A sessão é descartada pelo router sem
        # commit, então nem o estoque nem a trilha mudam.
        raise EstoqueNegativoError()

    estoque.quantidade = nova
    ajuste = EstoqueAjuste(
        estoque_id=estoque.id,
        quantidade_anterior=anterior,
        quantidade_nova=nova,
        motivo=motivo,
        autor_id=autor_id,
    )
    db.add(ajuste)
    # Uma transação só: o UPDATE do estoque e o INSERT da auditoria sobem
    # juntos ou não sobem.
    await db.commit()
    await db.refresh(estoque)
    await db.refresh(ajuste)
    return estoque, ajuste


async def definir_quantidade(
    db: AsyncSession, *, estoque_id: int, quantidade: int, motivo: str, autor_id: uuid.UUID
) -> tuple[Estoque, EstoqueAjuste]:
    """Porta absoluta. O delta é calculado sob o MESMO lock de linha que
    `aplicar_ajuste` toma — por isso a leitura aqui também é
    `with_for_update()`: sem ela, o valor lido para calcular o delta poderia
    ser obsoleto no instante em que o lock fosse adquirido lá dentro.

    O lock é reentrante na mesma transação (Postgres: um segundo
    `SELECT ... FOR UPDATE` na mesma linha, na mesma transação, não bloqueia),
    então as duas tomadas não se travam mutuamente.
    """
    estoque = (
        await db.execute(select(Estoque).where(Estoque.id == estoque_id).with_for_update())
    ).scalar_one_or_none()
    if estoque is None:
        raise EstoqueNotFoundError()
    return await aplicar_ajuste(
        db,
        estoque_id=estoque_id,
        delta=quantidade - estoque.quantidade,
        motivo=motivo,
        autor_id=autor_id,
    )


async def listar_ajustes(
    db: AsyncSession, *, produto_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[EstoqueAjuste], int]:
    estoque = await obter_estoque_do_produto(db, produto_id)
    stmt = (
        select(EstoqueAjuste)
        .where(EstoqueAjuste.estoque_id == estoque.id)
        .order_by(EstoqueAjuste.criado_em.desc(), EstoqueAjuste.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count())
            .select_from(EstoqueAjuste)
            .where(EstoqueAjuste.estoque_id == estoque.id)
        )
    ).scalar_one()
    return items, total
```

> **Cuidado do implementador com `definir_quantidade`:** se `quantidade ==
> estoque.quantidade`, o delta é 0 e `AjusteEstoqueIn` proíbe delta zero — mas
> aqui o schema não incide (a chamada é interna). `aplicar_ajuste` aceita
> delta 0 e grava uma linha de auditoria com anterior == nova. Isso é
> **correto e desejado**: "conferi o inventário e o número está certo" é um
> fato auditável. Não acrescentar guarda contra isso.

- [ ] **Passo 5: escrever as rotas**

Em `app/routers/produtos.py`, **depois** de `@router.get("/categories")` e
**antes** de `@router.get("/{product_id}")` — a ordem importa: FastAPI casa na
primeira rota que bate, e `/{product_id}` engoliria qualquer sufixo:

```python
@router.post(
    "/{product_id}/stock-adjustments",
    response_model=EstoqueAjusteOut,
    status_code=status.HTTP_201_CREATED,
)
async def ajustar_estoque(
    product_id: uuid.UUID,
    payload: AjusteEstoqueIn,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> EstoqueAjusteOut:
    """Ajuste por DELTA, com auditoria, atômico. Ver app/services/estoque.py."""
    try:
        estoque = await estoque_services.obter_estoque_do_produto(db, product_id)
        _, ajuste = await estoque_services.aplicar_ajuste(
            db,
            estoque_id=estoque.id,
            delta=payload.delta,
            motivo=payload.motivo,
            autor_id=uuid.UUID(user["sub"]),
        )
    except EstoqueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock record not found"
        ) from exc
    except EstoqueNegativoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O ajuste deixaria o estoque negativo",
        ) from exc
    return EstoqueAjusteOut.model_validate(ajuste)


@router.get("/{product_id}/stock-adjustments", response_model=EstoqueAjusteList)
async def listar_ajustes_estoque(
    product_id: uuid.UUID,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EstoqueAjusteList:
    try:
        items, total = await estoque_services.listar_ajustes(
            db, produto_id=product_id, limit=limit, offset=offset
        )
    except EstoqueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock record not found"
        ) from exc
    return EstoqueAjusteList(
        items=[EstoqueAjusteOut.model_validate(a) for a in items],
        total=total,
        limit=limit,
        offset=offset,
    )
```

Imports novos em `produtos.py`: `requer_papel` de `app.dependencies`,
`EstoqueNegativoError`/`EstoqueNotFoundError` de `app.exceptions`,
`AjusteEstoqueIn`/`EstoqueAjusteList`/`EstoqueAjusteOut` de
`app.schemas.estoque`, e `from app.services import estoque as estoque_services`.

Em `app/routers/admin.py`, substituir o corpo de `ajustar_estoque` (linhas
155-186) inteiro:

```python
@router.patch("/inventory/{estoque_id}/adjust", response_model=EstoqueOut)
async def ajustar_estoque(
    estoque_id: int,
    # `ge=0`: sem piso, um admin gravava estoque negativo e a separação
    # passava a trabalhar contra um número que não existe no mundo físico.
    quantidade: int = Query(ge=0),
    # Obrigatório desde a spec B: um ajuste sem motivo não é auditoria. O
    # painel Angular já mandava um (`stock-adjust-modal` compõe
    # "<preset>: <observação>") — só não havia onde gravar.
    motivo: str = Query(min_length=1, max_length=300),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Porta ABSOLUTA do ajuste de estoque. A porta de delta é
    `POST /products/{id}/stock-adjustments`. As duas passam pelo mesmo núcleo
    (`app/services/estoque.py`), então as duas deixam rastro em
    `estoque_ajustes` — antes da spec B esta rota não deixava nenhum.
    """
    try:
        estoque, _ = await estoque_services.definir_quantidade(
            db,
            estoque_id=estoque_id,
            quantidade=quantidade,
            motivo=motivo,
            autor_id=uuid.UUID(user["sub"]),
        )
    except EstoqueNotFoundError as exc:
        raise HTTPException(404, "Registro de estoque não encontrado") from exc
    return estoque
```

Imports novos em `admin.py`: `EstoqueNotFoundError` de `app.exceptions` e
`from app.services import estoque as estoque_services`. O import de `select`
continua sendo usado pelas outras rotas do arquivo; conferir com ruff.

- [ ] **Passo 6: rodar os testes e confirmar que passam**

```bash
cd back-end/commerce-service && uv run pytest tests/test_stock_adjustments.py tests/test_admin_routes.py -q
```

Esperado: 9 passed + 16 passed.

- [ ] **Passo 7: suíte inteira e lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: **398 passed** (389 + 9).

- [ ] **Passo 8: commit**

```bash
cd /home/elias/programming/fiap/estuda_app
git add back-end/commerce-service
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): port InventoryAdjustment as an audited stock adjustment

One atomic write path, two doors: POST /products/{id}/stock-adjustments
takes a delta, PATCH /admin/inventory/{id}/adjust keeps taking an absolute
quantity and converts it under the same row lock. Both now write to
estoque_ajustes in the same transaction as the quantity change; the admin
route left no trail at all before. An adjustment that would go negative is
422 before any write, so the trail never records a refused change.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Transportadora — serviço e rotas `/carriers`

Porte do `CarrierController` do Java. O roteamento no gateway já entrou na
task 2 (as duas linhas do `SERVICE_MAP` são a mesma mudança).

**Files:**
- Criar: `back-end/commerce-service/app/schemas/transportadora.py`
- Criar: `back-end/commerce-service/app/services/transportadoras.py`
- Criar: `back-end/commerce-service/app/routers/transportadoras.py`
- Modificar: `back-end/commerce-service/app/main.py`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Criar: `back-end/commerce-service/tests/test_carriers_routes.py`

**Interfaces:**
- Consome da task 1: `Carrier`, `CarrierStatus`.
- Produz para as tasks 5 e 13:

```python
# app/services/transportadoras.py
async def listar_transportadoras(
    db: AsyncSession, *, busca: str | None = None, status: str | None = None,
    limit: int, offset: int,
) -> tuple[list[Carrier], int]: ...
async def obter_transportadora(db: AsyncSession, carrier_id: int) -> Carrier: ...
async def criar_transportadora(db: AsyncSession, data: TransportadoraIn) -> Carrier: ...
async def atualizar_transportadora(db: AsyncSession, carrier_id: int, data: TransportadoraIn) -> Carrier: ...
async def definir_status(db: AsyncSession, carrier_id: int, status: CarrierStatus) -> Carrier: ...

# app/exceptions.py
class TransportadoraNotFoundError(Exception): ...
```

Rotas (espelhando o `CarrierController`): `GET /carriers` (admin, `search`,
`status`, paginado), `GET /carriers/{id}` (admin), `POST /carriers` (admin),
`PUT /carriers/{id}` (admin), `PATCH /carriers/{id}/status` (admin).

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_carriers_routes.py`:

```python
"""Cobertura de `/carriers` — porte do `CarrierController` do Java.

Rotas espelhadas de
`mobile_hybrid_app/api/src/main/java/com/edu/api/carrier/controller/
CarrierController.java`: listagem com `search`/`status`, detalhe, POST, PUT e
`PATCH /{id}/status`. O que NÃO é espelhado é o envelope de página do Spring
(`{content, totalElements, ...}`) — a frota inteira usa
`{items, total, limit, offset}` e o painel Angular é reescrito para ele
(decisão D9 do plano da spec B).
"""

from edu_common.security import create_access_token

from app.config import settings
from app.models.transportadora import Carrier, CarrierStatus


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


_PAYLOAD = {
    "name": "Rápido Cajamar",
    "location": "Cajamar, SP",
    "email": "ops@rapidocajamar.com.br",
    "average_delivery_days": 3,
    "rating": "4.5",
    "sla_percentage": "98.50",
    "status": "ACTIVE",
}


async def _seed(db_session, *, name: str, status: str = "ACTIVE") -> Carrier:
    carrier = Carrier(
        name=name,
        location="São Paulo, SP",
        email="ops@example.com",
        average_delivery_days=2,
        rating=4,
        sla_percentage=95,
        status=status,
    )
    db_session.add(carrier)
    await db_session.commit()
    await db_session.refresh(carrier)
    return carrier


async def test_every_carrier_route_is_admin_only(client, db_session):
    carrier = await _seed(db_session, name="X")
    chamadas = [
        ("get", "/carriers", None),
        ("get", f"/carriers/{carrier.id}", None),
        ("post", "/carriers", _PAYLOAD),
        ("put", f"/carriers/{carrier.id}", _PAYLOAD),
        ("patch", f"/carriers/{carrier.id}/status", {"status": "INACTIVE"}),
    ]
    for metodo, url, corpo in chamadas:
        for papel in ("student", "separador", "entregador"):
            kwargs = {"headers": headers_for(papel)}
            if corpo is not None:
                kwargs["json"] = corpo
            response = await getattr(client, metodo)(url, **kwargs)
            assert response.status_code == 403, f"{metodo} {url} {papel}"


async def test_listing_is_paginated_and_capped(client):
    assert (await client.get("/carriers?limit=5000", headers=headers_for("admin"))).status_code == 422


async def test_response_exposes_only_declared_fields(client, db_session):
    await _seed(db_session, name="X")
    row = (await client.get("/carriers", headers=headers_for("admin"))).json()["items"][0]
    assert set(row) == {
        "id", "name", "location", "email", "average_delivery_days",
        "rating", "sla_percentage", "status", "created_at", "updated_at",
    }


async def test_creating_a_carrier_returns_201_with_the_java_field_shape(client):
    response = await client.post("/carriers", json=_PAYLOAD, headers=headers_for("admin"))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Rápido Cajamar"
    assert body["average_delivery_days"] == 3
    assert body["rating"] == "4.5"
    assert body["sla_percentage"] == "98.50"
    assert body["status"] == "ACTIVE"


async def test_creating_rejects_a_status_outside_the_enum(client):
    response = await client.post(
        "/carriers", json={**_PAYLOAD, "status": "SUSPENSA"}, headers=headers_for("admin")
    )
    assert response.status_code == 422


async def test_creating_rejects_fields_over_the_java_column_widths(client):
    for campo, valor in (("name", "x" * 151), ("location", "x" * 151)):
        response = await client.post(
            "/carriers", json={**_PAYLOAD, campo: valor}, headers=headers_for("admin")
        )
        assert response.status_code == 422, campo


async def test_rating_and_sla_are_bounded(client):
    fora = [("rating", "6.0"), ("rating", "-1.0"), ("sla_percentage", "101.00")]
    for campo, valor in fora:
        response = await client.post(
            "/carriers", json={**_PAYLOAD, campo: valor}, headers=headers_for("admin")
        )
        assert response.status_code == 422, f"{campo}={valor}"


async def test_search_filters_by_name_and_status_filters_by_state(client, db_session):
    await _seed(db_session, name="Rápido Cajamar", status="ACTIVE")
    await _seed(db_session, name="Lenta Osasco", status="INACTIVE")

    busca = await client.get("/carriers?search=cajamar", headers=headers_for("admin"))
    assert [c["name"] for c in busca.json()["items"]] == ["Rápido Cajamar"]

    inativas = await client.get("/carriers?status=INACTIVE", headers=headers_for("admin"))
    assert [c["name"] for c in inativas.json()["items"]] == ["Lenta Osasco"]


async def test_updating_replaces_every_field(client, db_session):
    carrier = await _seed(db_session, name="Antiga")
    response = await client.put(
        f"/carriers/{carrier.id}",
        json={**_PAYLOAD, "name": "Nova"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nova"


async def test_status_transition_flips_the_state_and_touches_updated_at(client, db_session):
    carrier = await _seed(db_session, name="X", status="ACTIVE")
    antes = (await client.get(f"/carriers/{carrier.id}", headers=headers_for("admin"))).json()

    response = await client.patch(
        f"/carriers/{carrier.id}/status",
        json={"status": "INACTIVE"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    assert response.json()["updated_at"] >= antes["updated_at"]


async def test_status_transition_rejects_a_value_outside_the_enum(client, db_session):
    carrier = await _seed(db_session, name="X")
    response = await client.patch(
        f"/carriers/{carrier.id}/status",
        json={"status": "SUSPENSA"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_unknown_carrier_is_404_on_every_route(client):
    assert (await client.get("/carriers/999999", headers=headers_for("admin"))).status_code == 404
    assert (
        await client.put("/carriers/999999", json=_PAYLOAD, headers=headers_for("admin"))
    ).status_code == 404
    assert (
        await client.patch(
            "/carriers/999999", json={"status": "INACTIVE"}, headers=headers_for("admin")
        )
    ).status_code in (404, 405)
```

> A última asserção aceita 405 porque `PATCH /carriers/{id}` sem `/status` não
> é rota. Se o implementador preferir, trocar a linha por
> `client.patch("/carriers/999999/status", json={"status": "INACTIVE"}, ...)`
> e asserir 404 exato. Escolher **essa** forma — é a que testa o que importa.

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_carriers_routes.py -q
```

Esperado: 12 falhas, todas 404.

- [ ] **Passo 3: escrever o schema**

`app/schemas/transportadora.py`:

```python
"""Schema público de transportadora. Campos do `Carrier` do Java, um a um.

`rating` e `sla_percentage` saem como STRING pelo mesmo motivo de
`ProductOut.price` e `ParceiroOut.origem_lat`: dinheiro e nota não podem
herdar erro de arredondamento de float ao atravessar JSON. O painel Angular
lê os dois como number hoje (`carrier.model.ts`) e é ajustado na task 13.

Os limites de `rating` (0..5) e `sla_percentage` (0..100) não estão no Java —
lá `BigDecimal(2,1)` e `(5,2)` só limitam a LARGURA, e nada impedia um SLA de
999%. A regra 4 do CLAUDE.md pede limite, e um número fora de faixa aqui
mente para o painel inteiro.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.transportadora import CarrierStatus


class TransportadoraIn(BaseModel):
    name: str = Field(max_length=150)
    location: str = Field(max_length=150)
    email: str = Field(max_length=254)
    average_delivery_days: int = Field(ge=0, le=365)
    rating: Decimal = Field(ge=0, le=5)
    sla_percentage: Decimal = Field(ge=0, le=100)
    status: CarrierStatus = CarrierStatus.ACTIVE


class TransportadoraStatusIn(BaseModel):
    status: CarrierStatus


class TransportadoraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    email: str
    average_delivery_days: int
    rating: Decimal
    sla_percentage: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("rating")
    def _rating_as_string(self, value: Decimal) -> str:
        return f"{value:.1f}"

    @field_serializer("sla_percentage")
    def _sla_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class TransportadoraList(BaseModel):
    items: list[TransportadoraOut]
    total: int
    limit: int
    offset: int
```

- [ ] **Passo 4: escrever o serviço e o router**

`app/services/transportadoras.py`:

```python
"""CRUD de transportadora. Porte do `CarrierService` do Java.

Sem lock: nenhuma operação aqui é read→write sobre valor compartilhado
(`definir_status` grava um valor absoluto vindo do cliente, não um
incremento). A regra 3 do CLAUDE.md não incide — e isso está escrito porque
a ausência de lock precisa ser uma decisão medida, não um esquecimento.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import TransportadoraNotFoundError
from app.models.transportadora import Carrier, CarrierStatus
from app.schemas.transportadora import TransportadoraIn


async def listar_transportadoras(
    db: AsyncSession,
    *,
    busca: str | None = None,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Carrier], int]:
    stmt = select(Carrier)
    count_stmt = select(func.count()).select_from(Carrier)

    if busca:
        # `ilike` com parâmetro bound — o pattern vai como VALOR, nunca
        # concatenado na string SQL (regra 1 do CLAUDE.md).
        pattern = f"%{busca}%"
        stmt = stmt.where(Carrier.name.ilike(pattern))
        count_stmt = count_stmt.where(Carrier.name.ilike(pattern))
    if status:
        stmt = stmt.where(Carrier.status == status)
        count_stmt = count_stmt.where(Carrier.status == status)

    stmt = stmt.order_by(Carrier.name).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def obter_transportadora(db: AsyncSession, carrier_id: int) -> Carrier:
    carrier = await db.get(Carrier, carrier_id)
    if carrier is None:
        raise TransportadoraNotFoundError()
    return carrier


async def criar_transportadora(db: AsyncSession, data: TransportadoraIn) -> Carrier:
    payload = data.model_dump()
    payload["status"] = payload["status"].value
    carrier = Carrier(**payload)
    db.add(carrier)
    await db.commit()
    await db.refresh(carrier)
    return carrier


async def atualizar_transportadora(
    db: AsyncSession, carrier_id: int, data: TransportadoraIn
) -> Carrier:
    carrier = await obter_transportadora(db, carrier_id)
    payload = data.model_dump()
    payload["status"] = payload["status"].value
    for campo, valor in payload.items():
        setattr(carrier, campo, valor)
    await db.commit()
    await db.refresh(carrier)
    return carrier


async def definir_status(db: AsyncSession, carrier_id: int, status: CarrierStatus) -> Carrier:
    carrier = await obter_transportadora(db, carrier_id)
    carrier.status = status.value
    await db.commit()
    await db.refresh(carrier)
    return carrier
```

Em `app/exceptions.py`:

```python
class TransportadoraNotFoundError(Exception):
    """Nenhuma transportadora com o id dado. O router traduz em 404
    "Carrier not found". Sufixo `Error` por N818."""
```

`app/routers/transportadoras.py` segue exatamente o molde de
`app/routers/parceiros.py` (task 2): `requer_papel("admin")` em **todas** as
cinco rotas, `_NOT_FOUND` de módulo, `try/except TransportadoraNotFoundError`
em detalhe/PUT/PATCH, `limit: int = Query(default=20, ge=1, le=100)` e
`offset: int = Query(default=0, ge=0)` na listagem, mais
`search: str | None = Query(default=None, max_length=150)` e
`status: CarrierStatus | None = Query(default=None)`.

Em `app/main.py`: importar `transportadoras` e
`app.include_router(transportadoras.router)`.

- [ ] **Passo 5: rodar, confirmar que passa, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_carriers_routes.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 12 passed; **410 passed** no total (398 + 12).

- [ ] **Passo 6: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): port the Java Carrier entity behind /carriers

Full admin CRUD plus the PATCH /{id}/status transition, mirroring
CarrierController. status is a text enum, not a boolean, because the Java
side already modelled it as one. rating and sla_percentage gain the range
bounds the Java column widths never enforced.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Ocorrência de transportadora dentro do `Ocorrencia` existente

Ver D12 e D13. Um modelo, não dois. O `resolve` do aluno fica intacto.

**Files:**
- Modificar: `back-end/commerce-service/app/schemas/ocorrencia.py`
- Modificar: `back-end/commerce-service/app/routers/ocorrencias.py`
- Criar: `back-end/commerce-service/tests/test_carrier_occurrences.py`

**Interfaces:**
- Consome das tasks 1 e 4: `Ocorrencia.transportadora_id`, `Carrier`.
- Produz para a task 13:
  - `GET /occurrences` (admin; `carrier_id`, `tipo`, `status`; paginado)
  - `POST /occurrences/carrier` (admin) — corpo
    `{pedido_id, transportadora_id, tipo, motivo}`
  - `POST /occurrences/{id}/close` (admin) — corpo `{observacao?}`
  - `TIPOS_TRANSPORTADORA = ("ATRASO_ENTREGA", "DANO", "FALHA_ENTREGA", "OUTRO")`

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_carrier_occurrences.py`:

```python
"""Ocorrência de transportadora — reconciliada DENTRO do `Ocorrencia`.

O Java tem `CarrierOccurrence`, ancorada na transportadora; o commerce tem
`Ocorrencia`, ancorada no pedido. Manter os dois criaria duas telas e dois
relatórios que nunca fecham. Aqui a transportadora é uma DIMENSÃO da
ocorrência de pedido, não um segundo dono — `pedido_id` continua NOT NULL.

O que este arquivo mais protege é a fronteira: as ocorrências que já existem
(FALTA_ESTOQUE e ATRASO_ENTREGA abertas por separador/entregador, resolvidas
pelo aluno) não podem mudar de comportamento.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order
from app.models.transportadora import Carrier
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed_pedido(db_session) -> Order:
    pedido = Order(
        user_id=uuid.uuid4(),
        status=StatusPedido.EM_TRANSPORTE.value,
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_carrier(db_session, name: str = "Rápido Cajamar") -> Carrier:
    carrier = Carrier(
        name=name,
        location="Cajamar, SP",
        email="ops@example.com",
        average_delivery_days=3,
        rating=Decimal("4.5"),
        sla_percentage=Decimal("98.50"),
        status="ACTIVE",
    )
    db_session.add(carrier)
    await db_session.commit()
    await db_session.refresh(carrier)
    return carrier


async def test_creating_a_carrier_occurrence_is_admin_only(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    corpo = {
        "pedido_id": str(pedido.id),
        "transportadora_id": carrier.id,
        "tipo": "DANO",
        "motivo": "Caixa amassada na chegada",
    }
    for papel in ("student", "separador", "entregador"):
        response = await client.post("/occurrences/carrier", json=corpo, headers=headers_for(papel))
        assert response.status_code == 403, papel


async def test_admin_creates_a_carrier_occurrence_anchored_on_the_order(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)

    response = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "FALHA_ENTREGA",
            "motivo": "Endereço não localizado",
        },
        headers=headers_for("admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["pedido_id"] == str(pedido.id)
    assert body["transportadora_id"] == carrier.id
    assert body["tipo"] == "FALHA_ENTREGA"
    assert body["status"] == "ABERTA"


async def test_the_four_java_types_are_accepted_and_delivery_delay_is_reused(client, db_session):
    """`DELIVERY_DELAY` do Java É o `ATRASO_ENTREGA` que já existia aqui —
    não virou um sexto valor. Os outros três entram."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    for tipo in ("ATRASO_ENTREGA", "DANO", "FALHA_ENTREGA", "OUTRO"):
        response = await client.post(
            "/occurrences/carrier",
            json={
                "pedido_id": str(pedido.id),
                "transportadora_id": carrier.id,
                "tipo": tipo,
                "motivo": "m",
            },
            headers=headers_for("admin"),
        )
        assert response.status_code == 201, tipo


async def test_a_stock_shortage_is_not_a_carrier_occurrence_type(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    response = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "FALTA_ESTOQUE",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_listing_is_admin_only_paginated_and_filterable(client, db_session):
    pedido = await _seed_pedido(db_session)
    rapida = await _seed_carrier(db_session, "Rápida")
    lenta = await _seed_carrier(db_session, "Lenta")
    for carrier, tipo in ((rapida, "DANO"), (lenta, "FALHA_ENTREGA")):
        await client.post(
            "/occurrences/carrier",
            json={
                "pedido_id": str(pedido.id),
                "transportadora_id": carrier.id,
                "tipo": tipo,
                "motivo": "m",
            },
            headers=headers_for("admin"),
        )

    assert (await client.get("/occurrences", headers=headers_for("student"))).status_code == 403
    assert (
        await client.get("/occurrences?limit=5000", headers=headers_for("admin"))
    ).status_code == 422

    todas = await client.get("/occurrences", headers=headers_for("admin"))
    assert todas.json()["total"] == 2

    por_carrier = await client.get(
        f"/occurrences?carrier_id={rapida.id}", headers=headers_for("admin")
    )
    assert por_carrier.json()["total"] == 1
    assert por_carrier.json()["items"][0]["transportadora_id"] == rapida.id

    por_tipo = await client.get("/occurrences?tipo=DANO", headers=headers_for("admin"))
    assert por_tipo.json()["total"] == 1

    por_status = await client.get("/occurrences?status=RESOLVIDA", headers=headers_for("admin"))
    assert por_status.json()["total"] == 0


async def test_grouping_by_carrier_does_not_hide_the_order_occurrences(client, db_session):
    """A ocorrência de pedido sem transportadora continua na listagem — ela
    não deixou de existir por ter ganhado uma dimensão nova."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    db_session.add(
        Ocorrencia(
            pedido_id=pedido.id,
            tipo="FALTA_ESTOQUE",
            motivo="Sem estoque",
            criado_por=uuid.uuid4(),
        )
    )
    await db_session.commit()
    await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )

    todas = await client.get("/occurrences", headers=headers_for("admin"))
    assert todas.json()["total"] == 2
    sem_carrier = [o for o in todas.json()["items"] if o["transportadora_id"] is None]
    assert len(sem_carrier) == 1


async def test_closing_an_occurrence_is_admin_only_and_idempotent_guarded(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]

    negado = await client.post(
        f"/occurrences/{ocorrencia_id}/close", json={}, headers=headers_for("student")
    )
    assert negado.status_code == 403

    fechada = await client.post(
        f"/occurrences/{ocorrencia_id}/close",
        json={"observacao": "Reembolso emitido"},
        headers=headers_for("admin"),
    )
    assert fechada.status_code == 200
    assert fechada.json()["status"] == "RESOLVIDA"
    assert fechada.json()["resolvido_em"] is not None

    de_novo = await client.post(
        f"/occurrences/{ocorrencia_id}/close", json={}, headers=headers_for("admin")
    )
    assert de_novo.status_code == 400


async def test_close_does_not_touch_the_student_resolve_path(client, db_session):
    """`close` fecha; ele NÃO substitui item, não mexe em `orders.total` e não
    cancela pedido. Essa lógica é do `resolve` do aluno e continua lá."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    total_antes = pedido.total
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    await client.post(
        f"/occurrences/{criada.json()['id']}/close", json={}, headers=headers_for("admin")
    )
    await db_session.refresh(pedido)
    assert pedido.total == total_antes
    assert pedido.status == StatusPedido.EM_TRANSPORTE.value


async def test_creating_against_an_unknown_order_or_carrier_is_404(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)

    sem_pedido = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(uuid.uuid4()),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    assert sem_pedido.status_code == 404

    sem_carrier = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": 999999,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    assert sem_carrier.status_code == 404
```

> **Antes de escrever a implementação, medir o valor real de
> `StatusPedido.EM_TRANSPORTE`:** `grep -n "class StatusPedido" -A 15
> app/services/status_pedido.py`. Se o membro tiver outro nome, trocar nos
> quatro usos deste arquivo. Não presumir.

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_carrier_occurrences.py -q
```

Esperado: 9 falhas, todas 404 ou 405.

- [ ] **Passo 3: escrever os schemas**

Em `app/schemas/ocorrencia.py`:

```python
# Os quatro tipos que uma ocorrência de TRANSPORTADORA pode ter. Porte de
# `OccurrenceType` do Java: `DELIVERY_DELAY` é o `ATRASO_ENTREGA` que já
# existia aqui, e por isso não virou um valor novo. `FALTA_ESTOQUE` fica de
# fora de propósito — falta de estoque é do separador, não da transportadora,
# e tem rota própria (`POST /occurrences/stock-shortage`).
TipoOcorrenciaTransportadora = Literal["ATRASO_ENTREGA", "DANO", "FALHA_ENTREGA", "OUTRO"]


class OcorrenciaTransportadoraIn(BaseModel):
    pedido_id: uuid.UUID
    transportadora_id: int
    tipo: TipoOcorrenciaTransportadora
    motivo: str = Field(min_length=1, max_length=2000)


class FecharOcorrenciaIn(BaseModel):
    observacao: str | None = Field(default=None, max_length=2000)


class OcorrenciaList(BaseModel):
    items: list[OcorrenciaOut]
    total: int
    limit: int
    offset: int
```

e acrescentar `transportadora_id: int | None = None` a `OcorrenciaOut` (logo
depois de `produto_id`). Imports novos: `Field` de `pydantic`.

> **Custo medido dessa linha:** `OcorrenciaOut` é o `response_model` das cinco
> rotas que já existem, então `transportadora_id` passa a aparecer em todas.
> Nenhum teste atual assere o conjunto exato de chaves de `OcorrenciaOut`
> (medido: `grep -n "set(.*json()" tests/test_occurrences_routes.py` não
> devolve nada), então isso não quebra teste. **Reconfirmar com esse grep
> antes de escrever.** O Flutter lê campo a campo
> (`incident_resolution_screen.dart`), então também não quebra.

- [ ] **Passo 4: escrever as rotas**

Em `app/routers/ocorrencias.py`, três rotas novas. `GET ""` precisa vir
**antes** de `GET "/{ocorrencia_id}"`; `POST "/carrier"` precisa vir antes de
qualquer `POST "/{...}"`. Conferir a ordem depois de colar.

```python
@router.get("", response_model=OcorrenciaList)
async def listar_ocorrencias(
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    carrier_id: int | None = Query(default=None),
    tipo: str | None = Query(default=None, max_length=30),
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OcorrenciaList:
    """Listagem de administração. Devolve TODA ocorrência, com ou sem
    transportadora: a de pedido não deixou de existir por a de transportadora
    ter passado a caber no mesmo modelo. O painel agrupa por
    `transportadora_id`."""
    stmt = select(Ocorrencia)
    count_stmt = select(func.count()).select_from(Ocorrencia)
    if carrier_id is not None:
        stmt = stmt.where(Ocorrencia.transportadora_id == carrier_id)
        count_stmt = count_stmt.where(Ocorrencia.transportadora_id == carrier_id)
    if tipo:
        stmt = stmt.where(Ocorrencia.tipo == tipo)
        count_stmt = count_stmt.where(Ocorrencia.tipo == tipo)
    if status:
        stmt = stmt.where(Ocorrencia.status == status)
        count_stmt = count_stmt.where(Ocorrencia.status == status)

    stmt = stmt.order_by(Ocorrencia.criado_em.desc(), Ocorrencia.id.desc()).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return OcorrenciaList(
        items=[OcorrenciaOut.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/carrier", response_model=OcorrenciaOut, status_code=201)
async def abrir_ocorrencia_transportadora(
    payload: OcorrenciaTransportadoraIn,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Ocorrência de transportadora. Continua sendo de um PEDIDO — a
    transportadora é uma dimensão, não um segundo dono, e é por isso que o
    `CarrierOccurrence` do Java não virou tabela separada."""
    pedido = (
        await db.execute(select(Order).where(Order.id == payload.pedido_id))
    ).scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    transportadora = await db.get(Carrier, payload.transportadora_id)
    if not transportadora:
        raise HTTPException(404, "Carrier not found")

    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        transportadora_id=transportadora.id,
        tipo=payload.tipo,
        status="ABERTA",
        motivo=payload.motivo,
        criado_por=uuid.UUID(user["sub"]),
    )
    db.add(ocorrencia)
    await db.commit()
    await db.refresh(ocorrencia)
    return OcorrenciaOut.model_validate(ocorrencia)


@router.post("/{ocorrencia_id}/close", response_model=OcorrenciaOut)
async def fechar_ocorrencia(
    ocorrencia_id: int,
    payload: FecharOcorrenciaIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Fecha uma ocorrência SEM a lógica de substituição.

    `POST /occurrences/{id}/resolve` é do ALUNO e decide o destino do item
    (substituir, remover, cancelar, aceitar nova data). Uma ocorrência de dano
    ou de falha de entrega não tem essa decisão para tomar — ela é fechada
    pela operação. Duas rotas porque são dois atos diferentes com dois donos
    diferentes, não por conveniência.

    `with_for_update()` pelo mesmo motivo do `resolve`: sem ele o
    `status != ABERTA` é um TOCTOU e dois fechamentos concorrentes passam os
    dois.
    """
    ocorrencia = (
        await db.execute(
            select(Ocorrencia).where(Ocorrencia.id == ocorrencia_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not ocorrencia:
        raise HTTPException(404, "Ocorrência não encontrada")
    if ocorrencia.status != "ABERTA":
        raise HTTPException(400, "Esta ocorrência já foi resolvida")

    ocorrencia.status = "RESOLVIDA"
    ocorrencia.resolvido_em = datetime.now(UTC)
    if payload.observacao:
        ocorrencia.motivo = f"{ocorrencia.motivo}\n[fechamento] {payload.observacao}"
    await db.commit()
    await db.refresh(ocorrencia)
    return OcorrenciaOut.model_validate(ocorrencia)
```

Imports novos em `ocorrencias.py`: `func` de `sqlalchemy`, `Query` de
`fastapi`, `Carrier` de `app.models.transportadora`, e
`FecharOcorrenciaIn`/`OcorrenciaList`/`OcorrenciaTransportadoraIn` de
`app.schemas.ocorrencia`. `datetime`/`UTC` já estão importados (linha 2).

- [ ] **Passo 5: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_carrier_occurrences.py tests/test_occurrences_routes.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 9 passed + 24 passed; **419 passed** no total (410 + 9). Se algum dos
24 de `test_occurrences_routes.py` falhar, a task está errada — nenhuma rota
existente foi tocada.

- [ ] **Passo 6: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): reconcile CarrierOccurrence into the existing Ocorrencia

The Java model anchors an occurrence on the carrier; this one anchors it on
the order. Keeping both would produce two occurrence screens and two reports
that never agree, so the carrier becomes a dimension of the order
occurrence: an optional column, three new types, and admin routes to list,
open and close. DELIVERY_DELAY is the ATRASO_ENTREGA that already existed
and did not become a sixth value. The student resolve path is untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: CRUD admin de produto

Ver D1: o critério de pronto 2 da spec exige que o painel *opere* produtos, e
o backend só tinha GET.

**Files:**
- Modificar: `back-end/commerce-service/app/schemas/produto.py`
- Modificar: `back-end/commerce-service/app/services/produtos.py`
- Modificar: `back-end/commerce-service/app/routers/produtos.py`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Criar: `back-end/commerce-service/tests/test_products_admin_routes.py`

**Interfaces produzidas (tasks 7, 11, 13):**

```python
# app/schemas/produto.py — ProductOut ganha `sku: str = ""` e `active: bool = True`
class ProductIn(BaseModel):
    name, type, subtype, description, price, sku, active
    fornecedor_id: int          # de qual parceiro este produto é
    quantidade_inicial: int = 0 # cria a linha de estoque junto
    estoque_minimo: int = 0

class ProductPatch(BaseModel):  # PUT: todos os campos, sem estoque
    name, type, subtype, description, price, sku, active

# app/services/produtos.py
async def criar_produto(db, data: ProductIn) -> Product: ...       # raise SkuDuplicadoError, ParceiroNotFoundError
async def atualizar_produto(db, product_id, data: ProductPatch) -> Product: ...

# app/exceptions.py
class SkuDuplicadoError(Exception): ...
```

Rotas: `POST /products` (admin, 201), `PUT /products/{id}` (admin).

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_products_admin_routes.py`:

```python
"""CRUD de produto para o painel. Ver decisão D1 do plano da spec B.

O `product-form-modal` do web-admin cria produto com `sku`, `minimumStock`,
`initialQuantity` e `active`; o backend só tinha GET. O critério de pronto 2
da spec diz "web-admin opera produtos".

`POST /products` cria o produto E a linha de estoque no mesmo ato — a spec
exige que todo produto tenha estoque e todo estoque tenha fornecedor, porque
é isso que elimina o caminho especial de "produto sem parceiro".
"""

from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Product


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed_parceiro(db_session, nome: str = "Edu") -> Fornecedor:
    parceiro = Fornecedor(nome=nome, origem_rotulo="Aclimação, SP")
    db_session.add(parceiro)
    await db_session.commit()
    await db_session.refresh(parceiro)
    return parceiro


def _payload(fornecedor_id: int, **overrides) -> dict:
    base = {
        "name": "Mesa de estudo",
        "type": "mobiliario",
        "subtype": "Mesa",
        "description": "Tampo de 120 cm",
        "price": "399.90",
        "sku": "LM-MESA-120",
        "active": True,
        "fornecedor_id": fornecedor_id,
        "quantidade_inicial": 12,
        "estoque_minimo": 3,
    }
    base.update(overrides)
    return base


async def test_creating_and_updating_require_admin(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    for papel in ("student", "separador", "entregador"):
        criar = await client.post("/products", json=_payload(parceiro.id), headers=headers_for(papel))
        assert criar.status_code == 403, papel


async def test_admin_creates_a_product_with_its_stock_row(client, db_session):
    parceiro = await _seed_parceiro(db_session)

    response = await client.post(
        "/products", json=_payload(parceiro.id), headers=headers_for("admin")
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "LM-MESA-120"
    assert body["active"] is True
    assert body["price"] == "399.90"

    estoque = (await db_session.execute(select(Estoque))).scalars().all()
    assert len(estoque) == 1
    assert estoque[0].fornecedor_id == parceiro.id
    assert estoque[0].quantidade == 12
    assert estoque[0].estoque_minimo == 3


async def test_creating_against_an_unknown_partner_is_404(client):
    response = await client.post("/products", json=_payload(999999), headers=headers_for("admin"))
    assert response.status_code == 404


async def test_a_duplicate_sku_is_409(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    await client.post("/products", json=_payload(parceiro.id), headers=headers_for("admin"))
    de_novo = await client.post(
        "/products", json=_payload(parceiro.id, name="Outra"), headers=headers_for("admin")
    )
    assert de_novo.status_code == 409


async def test_an_empty_sku_is_rejected_on_create(client, db_session):
    """O índice de unicidade é PARCIAL (`WHERE sku <> ''`) para não quebrar
    nos seis produtos já semeados sem sku. Isso significa que o banco aceita
    N produtos com sku vazio — então o VALIDADOR é quem impede um produto novo
    de nascer sem sku."""
    parceiro = await _seed_parceiro(db_session)
    response = await client.post(
        "/products", json=_payload(parceiro.id, sku=""), headers=headers_for("admin")
    )
    assert response.status_code == 422


async def test_creating_rejects_fields_over_the_column_widths(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    for campo, valor in (("name", "x" * 161), ("sku", "x" * 61), ("type", "x" * 65)):
        response = await client.post(
            "/products", json=_payload(parceiro.id, **{campo: valor}), headers=headers_for("admin")
        )
        assert response.status_code == 422, campo


async def test_updating_replaces_the_catalog_fields_and_can_deactivate(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    criado = await client.post(
        "/products", json=_payload(parceiro.id), headers=headers_for("admin")
    )
    product_id = criado.json()["id"]

    response = await client.put(
        f"/products/{product_id}",
        json={
            "name": "Mesa de estudo compacta",
            "type": "mobiliario",
            "subtype": "Mesa",
            "description": "Tampo de 90 cm",
            "price": "349.90",
            "sku": "LM-MESA-120",
            "active": False,
        },
        headers=headers_for("admin"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Mesa de estudo compacta"
    assert response.json()["active"] is False


async def test_updating_does_not_touch_the_stock_row(client, db_session):
    """Estoque muda por ajuste auditado (`POST .../stock-adjustments`), nunca
    por edição de catálogo. Um PUT de produto que mexesse na quantidade
    contornaria a trilha de auditoria que a task 3 existe para garantir."""
    parceiro = await _seed_parceiro(db_session)
    criado = await client.post(
        "/products", json=_payload(parceiro.id), headers=headers_for("admin")
    )
    await client.put(
        f"/products/{criado.json()['id']}",
        json={
            "name": "N", "type": "mobiliario", "subtype": "", "description": "",
            "price": "1.00", "sku": "LM-MESA-120", "active": True,
        },
        headers=headers_for("admin"),
    )
    estoque = (await db_session.execute(select(Estoque))).scalars().all()
    assert estoque[0].quantidade == 12


async def test_updating_an_unknown_product_is_404(client):
    response = await client.put(
        "/products/00000000-0000-0000-0000-0000000000ff",
        json={
            "name": "N", "type": "t", "subtype": "", "description": "",
            "price": "1.00", "sku": "X-1", "active": True,
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 404


async def test_the_public_listing_exposes_sku_and_active(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    await client.post("/products", json=_payload(parceiro.id), headers=headers_for("admin"))
    row = (await client.get("/products", headers=headers_for("student"))).json()["items"][0]
    assert row["sku"] == "LM-MESA-120"
    assert row["active"] is True
```

**Emenda declarada:** `tests/test_products_parity.py` e
`tests/test_products_routes.py` podem asserir o conjunto exato de chaves de
`ProductOut`. **Medir antes de implementar:**

```bash
cd back-end/commerce-service && grep -n "set(row)\|set(body)\|set(item" tests/test_products_*.py
```

Se houver, acrescentar `"sku"` e `"active"` ao conjunto — mesma classe de
emenda da task 3, com o motivo escrito no relatório.

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_products_admin_routes.py -q
```

Esperado: 10 falhas (405 no POST/PUT, `KeyError: 'sku'` na última).

- [ ] **Passo 3: schemas**

Em `app/schemas/produto.py`, acrescentar a `ProductOut`, depois de `name`:

```python
    sku: str = ""
    active: bool = True
```

e no fim do arquivo:

```python
class ProductIn(BaseModel):
    """Criação de produto pelo painel. Cria o produto E a linha de estoque.

    `fornecedor_id` é obrigatório porque a spec exige um único caminho de
    código para "de onde este pedido sai": todo produto tem estoque, todo
    estoque tem fornecedor, todo fornecedor tem origem. Um produto criado sem
    fornecedor reintroduziria o caso especial que a spec eliminou.

    `sku` tem `min_length=1` mesmo o índice do banco sendo parcial
    (`WHERE sku <> ''`, para não quebrar nos seis produtos já semeados): o
    banco tolera o vazio herdado, o validador impede um vazio novo.
    """

    name: str = Field(max_length=160)
    type: str = Field(max_length=64)
    subtype: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=4000)
    price: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    sku: str = Field(min_length=1, max_length=60)
    active: bool = True
    fornecedor_id: int
    quantidade_inicial: int = Field(default=0, ge=0)
    estoque_minimo: int = Field(default=0, ge=0)


class ProductPatch(BaseModel):
    """Edição de catálogo. NÃO carrega estoque: quantidade só muda por ajuste
    auditado (`POST /products/{id}/stock-adjustments`). Um PUT que mexesse no
    saldo contornaria a trilha que a task 3 existe para garantir."""

    name: str = Field(max_length=160)
    type: str = Field(max_length=64)
    subtype: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=4000)
    price: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    sku: str = Field(min_length=1, max_length=60)
    active: bool = True
```

Import novo: `Field` de `pydantic`.

- [ ] **Passo 4: serviço, exceção e rotas**

Em `app/exceptions.py`:

```python
class SkuDuplicadoError(Exception):
    """Já existe produto com este `sku`. O router traduz em 409.

    A unicidade é do BANCO (índice parcial `uq_products_sku`), e o serviço a
    detecta pelo `IntegrityError` em vez de por um SELECT prévio: um SELECT
    seguido de INSERT é uma corrida, e o índice é a única coisa que resolve
    duas criações simultâneas do mesmo sku. Mesmo idioma de
    `get_or_create_cart` (`app/services/carrinho.py`) e de `criar_metodo`
    (`app/services/pagamento.py`).

    Sufixo `Error` por N818.
    """
```

Em `app/services/produtos.py`:

```python
async def criar_produto(db: AsyncSession, data: ProductIn) -> Product:
    fornecedor = await db.get(Fornecedor, data.fornecedor_id)
    if fornecedor is None:
        raise ParceiroNotFoundError()

    product = Product(
        name=data.name,
        type=data.type,
        subtype=data.subtype,
        description=data.description,
        price=data.price,
        sku=data.sku,
        active=data.active,
    )
    db.add(product)
    try:
        # Flush, não commit: o produto e o estoque sobem na MESMA transação.
        # Um produto sem linha de estoque quebraria a invariante da spec
        # ("todo produto tem estoque") no intervalo entre os dois commits.
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SkuDuplicadoError() from exc

    db.add(
        Estoque(
            produto_id=product.id,
            fornecedor_id=fornecedor.id,
            quantidade=data.quantidade_inicial,
            estoque_minimo=data.estoque_minimo,
        )
    )
    await db.commit()
    await db.refresh(product)
    return product


async def atualizar_produto(db: AsyncSession, product_id: uuid.UUID, data: ProductPatch) -> Product:
    product = await buscar_produto(db, product_id)  # levanta ProductNotFoundError
    for campo, valor in data.model_dump().items():
        setattr(product, campo, valor)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SkuDuplicadoError() from exc
    await db.refresh(product)
    return product
```

Imports novos em `services/produtos.py`: `IntegrityError` de
`sqlalchemy.exc`, `Estoque`/`Fornecedor` de `app.models.produto`,
`ParceiroNotFoundError`/`SkuDuplicadoError` de `app.exceptions`,
`ProductIn`/`ProductPatch` de `app.schemas.produto`.

Em `app/routers/produtos.py`, `POST ""` logo depois de `GET ""`, e
`PUT "/{product_id}"` junto do `GET "/{product_id}"`:

```python
@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def criar_produto(
    payload: ProductIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProductOut:
    try:
        product = await services.criar_produto(db, payload)
    except ParceiroNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found"
        ) from exc
    except SkuDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um produto com este SKU"
        ) from exc
    return await _product_out(product, storage=storage, redis=redis)


@router.put("/{product_id}", response_model=ProductOut)
async def atualizar_produto(
    product_id: uuid.UUID,
    payload: ProductPatch,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProductOut:
    try:
        product = await services.atualizar_produto(db, product_id, payload)
    except ProductNotFoundError as exc:
        raise _NOT_FOUND from exc
    except SkuDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um produto com este SKU"
        ) from exc
    return await _product_out(product, storage=storage, redis=redis)
```

- [ ] **Passo 5: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_products_admin_routes.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 10 passed; **429 passed** no total (419 + 10).

- [ ] **Passo 6: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): add the admin product CRUD behind /products

POST creates the product and its stock row in one transaction, so the spec's
invariant holds with no gap: every product has stock, every stock row has a
supplier, every supplier has an origin. PUT edits the catalog and never
touches the quantity — stock moves only through the audited adjustment. sku
uniqueness is enforced by the partial index and surfaced as 409 from the
IntegrityError, not by a select-then-insert race.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: Catálogo filtrado por parceiro

**Files:**
- Modificar: `back-end/commerce-service/app/services/produtos.py::listar_produtos`
- Modificar: `back-end/commerce-service/app/routers/produtos.py::listar_produtos`
- Criar: `back-end/commerce-service/tests/test_products_partner_filter.py`

**Interfaces:**
- Consome: `Estoque.fornecedor_id` (task 1), `Fornecedor.ativo`.
- Produz para a task 12: `GET /products?partner_id=<int>`.

```python
async def listar_produtos(
    db, *, q: str | None = None, partner_id: int | None = None, limit: int, offset: int
) -> tuple[list[Product], int]: ...
```

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_products_partner_filter.py`:

```python
"""`GET /products?partner_id=` — o catálogo de um parceiro.

Produto pertence ao parceiro ATRAVÉS do estoque (`Estoque.fornecedor_id`),
não por chave direta em `products`. Não há coluna nova em `products`; o
filtro é um join.

Parceiro inativo devolve LISTA VAZIA, não 404: um parceiro desativado
enquanto o aluno navega não pode virar tela de erro.
"""

from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Product


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed(db_session, *, parceiro: str, produto: str, ativo: bool = True) -> Fornecedor:
    fornecedor = (
        await db_session.execute(__import__("sqlalchemy").select(Fornecedor).where(Fornecedor.nome == parceiro))
    ).scalar_one_or_none()
    if fornecedor is None:
        fornecedor = Fornecedor(nome=parceiro, ativo=ativo, origem_rotulo="São Paulo, SP")
        db_session.add(fornecedor)
        await db_session.commit()
        await db_session.refresh(fornecedor)

    p = Product(name=produto, type="mobiliario", price=Decimal("10.00"), sku=produto[:60])
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    db_session.add(Estoque(produto_id=p.id, fornecedor_id=fornecedor.id, quantidade=5))
    await db_session.commit()
    return fornecedor


async def test_without_the_filter_the_catalog_is_whole(client, db_session):
    edu = await _seed(db_session, parceiro="Edu", produto="Apostila")
    await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária")
    response = await client.get("/products", headers=headers_for("student"))
    assert response.json()["total"] == 2
    assert edu.id


async def test_the_filter_returns_only_that_partner_catalog(client, db_session):
    edu = await _seed(db_session, parceiro="Edu", produto="Apostila")
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária")

    do_edu = await client.get(f"/products?partner_id={edu.id}", headers=headers_for("student"))
    do_leroy = await client.get(f"/products?partner_id={leroy.id}", headers=headers_for("student"))

    assert [p["name"] for p in do_edu.json()["items"]] == ["Apostila"]
    assert do_edu.json()["total"] == 1
    assert [p["name"] for p in do_leroy.json()["items"]] == ["Luminária"]


async def test_a_disabled_partner_yields_an_empty_list_not_a_404(client, db_session):
    """Regra explícita da spec: "Parceiro inativo em GET /products?partner_id=:
    lista vazia, não 404". Desativar no painel esvazia a seção sem quebrar a
    navegação de quem já estava com a tela aberta."""
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária", ativo=False)
    response = await client.get(
        f"/products?partner_id={leroy.id}", headers=headers_for("student")
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_an_unknown_partner_also_yields_an_empty_list(client):
    response = await client.get("/products?partner_id=999999", headers=headers_for("student"))
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_the_filter_composes_with_the_search_and_the_pagination(client, db_session):
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária de mesa")
    await _seed(db_session, parceiro="Leroy Merlin", produto="Cadeira ergonômica")

    combinado = await client.get(
        f"/products?partner_id={leroy.id}&q=lumin&limit=1", headers=headers_for("student")
    )
    assert combinado.json()["total"] == 1
    assert combinado.json()["items"][0]["name"] == "Luminária de mesa"


async def test_a_product_with_no_stock_row_never_shows_under_any_partner(client, db_session):
    """Um produto sem estoque não pertence a parceiro nenhum — e é por isso
    que a spec exige que todo produto nasça com estoque (task 6). Este teste
    documenta a consequência de quebrar essa invariante."""
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária")
    orfao = Product(name="Órfão", type="apostila", price=Decimal("1.00"), sku="ORFAO-1")
    db_session.add(orfao)
    await db_session.commit()

    do_leroy = await client.get(
        f"/products?partner_id={leroy.id}", headers=headers_for("student")
    )
    assert [p["name"] for p in do_leroy.json()["items"]] == ["Luminária"]

    todos = await client.get("/products", headers=headers_for("student"))
    assert todos.json()["total"] == 2
```

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_products_partner_filter.py -q
```

Esperado: 4 falhas — `partner_id` é query desconhecida e o FastAPI a ignora,
então os totais vêm errados (2 em vez de 1, etc.).

- [ ] **Passo 3: implementar**

Em `app/services/produtos.py::listar_produtos`, acrescentar o parâmetro e o
join:

```python
async def listar_produtos(
    db: AsyncSession,
    *,
    q: str | None = None,
    partner_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    if partner_id is not None:
        # Produto pertence ao parceiro ATRAVÉS do estoque — não há coluna de
        # fornecedor em `products`, e não deve haver: um produto pode ser
        # estocado por mais de um fornecedor (a unicidade de `estoque` é do
        # PAR produto+fornecedor).
        #
        # O join com `fornecedores` é o que faz do "ativo" uma REGRA em vez de
        # um `if` na tela: parceiro inativo simplesmente não casa, e a
        # listagem sai vazia — sem 404, sem ramo especial, sem nome de
        # parceiro em lugar nenhum do código.
        vinculo = (
            select(Estoque.produto_id)
            .join(Fornecedor, Fornecedor.id == Estoque.fornecedor_id)
            .where(Estoque.fornecedor_id == partner_id, Fornecedor.ativo.is_(True))
        )
        stmt = stmt.where(Product.id.in_(vinculo))
        count_stmt = count_stmt.where(Product.id.in_(vinculo))

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))

    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total
```

Imports: `Estoque`, `Fornecedor` de `app.models.produto` (a task 6 já os
trouxe).

Em `app/routers/produtos.py::listar_produtos`, acrescentar o parâmetro depois
de `q` e repassá-lo:

```python
    partner_id: int | None = Query(default=None, ge=1),
```
```python
    items, total = await services.listar_produtos(
        db, q=q, partner_id=partner_id, limit=limit, offset=offset
    )
```

- [ ] **Passo 4: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_products_partner_filter.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 6 passed; **435 passed** no total (429 + 6). `test_products_parity.py`
(18) e `test_products_routes.py` (11) têm que continuar verdes — o parâmetro é
opcional e o caminho sem ele não mudou.

- [ ] **Passo 5: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): filter the catalog by partner

GET /products takes partner_id and resolves ownership through the stock row,
so no column is added to products and a product can still be stocked by more
than one supplier. The join requires fornecedores.ativo, which is what makes
"only active partners" a rule rather than a branch: disabling a partner
empties its section and no partner name appears in any decision path. An
inactive or unknown partner yields an empty list, never a 404.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 8: Regra de origem única no carrinho

Pedido misto (Edu + Leroy) é **proibido**, não adiado. A regra vive no serviço
de carrinho, não na tela, e roda sob o lock que a adição já toma.

**Files:**
- Modificar: `back-end/commerce-service/app/services/carrinho.py::adicionar_item`
- Modificar: `back-end/commerce-service/app/routers/carrinho.py::adicionar_item`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Criar: `back-end/commerce-service/tests/test_cart_single_origin.py`

**Interfaces:**
```python
# app/exceptions.py
class CarrinhoOrigemMistaError(Exception):
    """Carrega a mensagem pronta para exibir."""
    MENSAGEM = (
        "Seu carrinho já tem itens de outro parceiro. "
        "Finalize ou esvazie o carrinho antes de misturar."
    )
```
`POST /cart/items` passa a poder devolver `409` com `detail` = essa mensagem.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_cart_single_origin.py`:

```python
"""Origem única no carrinho. Pedido misto é PROIBIDO, não adiado.

A regra vive no SERVIÇO, sob o mesmo lock de linha do carrinho que a adição
já toma (`select(Cart.id)...with_for_update()` em
`app/services/carrinho.py::adicionar_item`). Pô-la na tela deixaria duas
adições simultâneas montarem um carrinho misto — regra 3 do CLAUDE.md:
leitura seguida de escrita em recurso compartilhado é atômica ou não é regra.
"""

import asyncio
import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import func, select

from app.config import settings
from app.models.carrinho import CartItem
from app.models.produto import Estoque, Fornecedor, Product

_ALUNO = "00000000-0000-0000-0000-0000000000bb"


def headers_for(sub: str = _ALUNO) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, 'student', settings.jwt_secret)}"}


async def _parceiro(db_session, nome: str) -> Fornecedor:
    f = Fornecedor(nome=nome, origem_rotulo=f"{nome}, SP")
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)
    return f


async def _produto(db_session, *, nome: str, fornecedor: Fornecedor | None) -> Product:
    p = Product(name=nome, type="mobiliario", price=Decimal("10.00"), sku=nome[:60])
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    if fornecedor is not None:
        db_session.add(Estoque(produto_id=p.id, fornecedor_id=fornecedor.id, quantidade=50))
        await db_session.commit()
    return p


async def test_two_items_from_the_same_partner_are_accepted(client, db_session):
    leroy = await _parceiro(db_session, "Leroy Merlin")
    a = await _produto(db_session, nome="Luminária", fornecedor=leroy)
    b = await _produto(db_session, nome="Cadeira", fornecedor=leroy)

    for produto in (a, b):
        response = await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for(),
        )
        assert response.status_code == 201, produto.name

    assert len((await client.get("/cart", headers=headers_for())).json()["items"]) == 2


async def test_an_item_from_another_partner_is_409_with_a_displayable_message(
    client, db_session
):
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    conflito = await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )

    assert conflito.status_code == 409
    detail = conflito.json()["detail"]
    assert "outro parceiro" in detail
    # A mensagem é para exibir sem reescrever: nada de código de erro cru,
    # nada de nome de tabela, nada de id.
    assert "Fornecedor" not in detail and "409" not in detail


async def test_the_rejected_item_never_lands_in_the_cart(client, db_session):
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )

    itens = (await client.get("/cart", headers=headers_for())).json()["items"]
    assert [i["name"] for i in itens] == ["Apostila"]


async def test_emptying_the_cart_releases_the_origin(client, db_session):
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    await client.delete(f"/cart/items/{apostila.id}", headers=headers_for())

    depois = await client.post(
        "/cart/items", json={"product_id": str(luminaria.id), "quantity": 1}, headers=headers_for()
    )
    assert depois.status_code == 201


async def test_concurrent_adds_from_two_partners_never_build_a_mixed_cart(client, db_session):
    """A prova de que a regra está sob o lock, e não na tela.

    Sem `with_for_update()` na linha do carrinho antes da checagem, as duas
    requisições leem um carrinho vazio, as duas concluem "não há origem
    ainda", e as duas gravam — carrinho misto, sem erro nenhum aparecer.
    """
    edu = await _parceiro(db_session, "Edu")
    leroy = await _parceiro(db_session, "Leroy Merlin")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)

    async def _add(produto):
        return await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for(),
        )

    respostas = await asyncio.gather(_add(apostila), _add(luminaria))
    codigos = sorted(r.status_code for r in respostas)
    assert codigos == [201, 409]

    total_itens = (
        await db_session.execute(select(func.count()).select_from(CartItem))
    ).scalar_one()
    assert total_itens == 1


async def test_a_product_without_a_stock_row_is_treated_as_originless_and_allowed(
    client, db_session
):
    """Os seis produtos já semeados no banco do usuário não têm linha de
    estoque (medido: `app/seeds/products.py` nunca toca em `Estoque`). Até a
    task 11 dar-lhes um fornecedor, um produto sem origem não pode travar o
    carrinho de ninguém — ele não CONFLITA com nada porque não tem origem
    para conflitar.

    A task 11 elimina esse caso do banco; este teste garante que o caminho
    existe e é benigno enquanto ele durar, em vez de virar 500 ou 409 falso.
    """
    edu = await _parceiro(db_session, "Edu")
    apostila = await _produto(db_session, nome="Apostila", fornecedor=edu)
    orfao = await _produto(db_session, nome="Órfão", fornecedor=None)

    await client.post(
        "/cart/items", json={"product_id": str(apostila.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post(
        "/cart/items", json={"product_id": str(orfao.id), "quantity": 1}, headers=headers_for()
    )
    assert response.status_code == 201


async def test_adding_more_of_an_item_already_in_the_cart_still_works(client, db_session):
    leroy = await _parceiro(db_session, "Leroy Merlin")
    luminaria = await _produto(db_session, nome="Luminária", fornecedor=leroy)
    for _ in range(2):
        response = await client.post(
            "/cart/items",
            json={"product_id": str(luminaria.id), "quantity": 1},
            headers=headers_for(),
        )
        assert response.status_code == 201
    itens = (await client.get("/cart", headers=headers_for())).json()["items"]
    assert itens[0]["quantity"] == 2
```

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_cart_single_origin.py -q
```

Esperado: 4 falhas — as adições de parceiro diferente devolvem 201.

- [ ] **Passo 3: implementar**

Em `app/exceptions.py`:

```python
class CarrinhoOrigemMistaError(Exception):
    """Tentativa de pôr no carrinho um item de outro parceiro. O router
    traduz em 409 com `MENSAGEM` como `detail`.

    Pedido misto é PROIBIDO por decisão da spec B, não adiado: um pedido sai
    de UMA origem, e a spec C simula a rota a partir dela. Um carrinho misto
    produziria um pedido sem origem definida.

    A mensagem mora aqui, não no router, porque ela é contrato de UI: o app
    a exibe verbatim, sem reescrever (`cart_service.dart`, task 12).

    Sufixo `Error` por N818.
    """

    MENSAGEM = (
        "Seu carrinho já tem itens de outro parceiro. "
        "Finalize ou esvazie o carrinho antes de misturar."
    )
```

Em `app/services/carrinho.py`, uma função nova e três linhas dentro de
`adicionar_item`:

```python
async def _fornecedor_do_produto(db: AsyncSession, product_id: uuid.UUID) -> int | None:
    """De qual parceiro este produto é. `None` quando não há linha de estoque.

    Produto pertence ao parceiro ATRAVÉS do estoque — a mesma travessia que
    `services.produtos.listar_produtos` faz para o filtro `partner_id`.
    """
    return (
        await db.execute(select(Estoque.fornecedor_id).where(Estoque.produto_id == product_id))
    ).scalar_one_or_none()


async def _origem_do_carrinho(db: AsyncSession, cart_id: uuid.UUID) -> int | None:
    """O fornecedor dos itens que já estão no carrinho, ou `None` se o
    carrinho está vazio (ou só tem itens sem origem).

    LIMIT 1 basta: a regra que esta função serve é o que garante que nunca há
    mais de um fornecedor aqui.
    """
    return (
        await db.execute(
            select(Estoque.fornecedor_id)
            .join(CartItem, CartItem.product_id == Estoque.produto_id)
            .where(CartItem.cart_id == cart_id)
            .limit(1)
        )
    ).scalar_one_or_none()
```

e, em `adicionar_item`, **depois** do `select(Cart.id)...with_for_update()` e
**antes** do `select(CartItem)`:

```python
    # A checagem de origem fica DENTRO do lock de linha do carrinho que a
    # linha acima acabou de tomar. Fora dele, duas adições simultâneas leem um
    # carrinho vazio, as duas concluem "não há origem ainda", e as duas
    # gravam — carrinho misto sem nenhum erro aparecer. Regra 3 do CLAUDE.md.
    fornecedor_do_item = await _fornecedor_do_produto(db, data.product_id)
    origem_atual = await _origem_do_carrinho(db, cart.id)
    if (
        fornecedor_do_item is not None
        and origem_atual is not None
        and fornecedor_do_item != origem_atual
    ):
        raise CarrinhoOrigemMistaError()
```

> **Nota de precisão:** as duas guardas `is not None` existem porque um
> produto sem linha de estoque não tem origem para conflitar. Enquanto os seis
> produtos semeados não tiverem fornecedor (até a task 11), remover essas
> guardas travaria o carrinho do catálogo inteiro.

Imports novos em `services/carrinho.py`: `Estoque` de `app.models.produto`,
`CarrinhoOrigemMistaError` de `app.exceptions`.

Em `app/routers/carrinho.py::adicionar_item`, mais um `except`:

```python
    except CarrinhoOrigemMistaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=CarrinhoOrigemMistaError.MENSAGEM
        ) from exc
```

- [ ] **Passo 4: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_cart_single_origin.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 7 passed; **442 passed** no total (435 + 7).
`test_cart_parity.py` (16) e `test_cart_services_parity.py` (8) têm que
continuar verdes: nenhum deles cria linha de estoque, então todo produto que
eles usam tem origem `None` e passa pela guarda. **Se algum falhar, medir por
quê antes de mexer no teste** — pode indicar que a guarda `is not None` foi
esquecida.

- [ ] **Passo 5: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): reject a mixed-origin cart with a displayable 409

Adding an item from a different partner is refused with a message the app
shows verbatim. The check runs inside the cart row lock the add already
takes, so two simultaneous adds cannot build a mixed cart between the read
and the write — a rule enforced only in the UI would not be a rule. Products
with no stock row have no origin to conflict with and stay allowed until the
seed gives them one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 9: O pedido carrega a origem do parceiro

**Files:**
- Modificar: `back-end/commerce-service/app/services/pedidos.py::criar_pedido_do_carrinho`
- Criar: `back-end/commerce-service/tests/test_order_origin.py`

**Interfaces:**
- Consome: `Order.origem_*` (task 1), `_fornecedor_do_produto` (task 8),
  `Fornecedor.origem_*` (task 1), `OrderItem.supplier_id` (já existia, nunca
  escrito).
- Produz para a spec C: `orders.origem_rotulo/origem_lat/origem_lng`
  preenchidos na criação.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_order_origin.py`:

```python
"""A origem de expedição é resolvida na CRIAÇÃO do pedido e congelada nele.

A spec C lê estas colunas para simular a rota e NÃO recalcula a origem — o
estoque pode mudar de fornecedor depois que o pedido saiu. Mesmo espírito do
snapshot `ship_*`: um pedido é registro histórico.

`order_items.supplier_id` existe desde a fase 2 e nunca foi escrito
(`app/models/pedido.py` registra isso em comentário). Aqui ele passa a ser
preenchido.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.pedido import Order, OrderItem
from app.models.produto import Estoque, Fornecedor, Product

_ALUNO = "00000000-0000-0000-0000-0000000000cc"


def headers_for(sub: str = _ALUNO) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, 'student', settings.jwt_secret)}"}


async def _catalogo(db_session, *, parceiro: str, rotulo: str, lat, lng, produto: str):
    f = Fornecedor(nome=parceiro, origem_rotulo=rotulo, origem_lat=lat, origem_lng=lng)
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)

    p = Product(name=produto, type="mobiliario", price=Decimal("10.00"), sku=produto[:60])
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    db_session.add(Estoque(produto_id=p.id, fornecedor_id=f.id, quantidade=50))
    await db_session.commit()
    return f, p


async def test_the_order_freezes_the_partner_origin(client, db_session):
    f, p = await _catalogo(
        db_session,
        parceiro="Leroy Merlin",
        rotulo="Cajamar, SP",
        lat=Decimal("-23.355800"),
        lng=Decimal("-46.876400"),
        produto="Luminária",
    )
    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 2}, headers=headers_for()
    )

    response = await client.post(
        "/orders", json={"payment_method": "PIX"}, headers=headers_for()
    )
    assert response.status_code == 201

    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo == "Cajamar, SP"
    assert pedido.origem_lat == Decimal("-23.355800")
    assert pedido.origem_lng == Decimal("-46.876400")


async def test_the_items_carry_the_supplier_id(client, db_session):
    f, p = await _catalogo(
        db_session, parceiro="Edu", rotulo="Aclimação, SP", lat=None, lng=None, produto="Apostila"
    )
    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post(
        "/orders", json={"payment_method": "PIX"}, headers=headers_for()
    )

    itens = (
        await db_session.execute(
            select(OrderItem).where(OrderItem.order_id == uuid.UUID(response.json()["id"]))
        )
    ).scalars().all()
    assert [i.supplier_id for i in itens] == [f.id]


async def test_a_partner_without_coordinates_still_freezes_the_label(client, db_session):
    await _catalogo(
        db_session, parceiro="Edu", rotulo="Aclimação, SP", lat=None, lng=None, produto="Apostila"
    )
    produto = (await db_session.execute(select(Product))).scalars().first()
    await client.post(
        "/cart/items", json={"product_id": str(produto.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post(
        "/orders", json={"payment_method": "PIX"}, headers=headers_for()
    )
    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo == "Aclimação, SP"
    assert pedido.origem_lat is None


async def test_a_cart_of_originless_products_yields_an_order_without_origin(
    client, db_session
):
    """Nenhum 500. Um produto sem linha de estoque (os seis semeados, até a
    task 11) produz pedido sem origem — que é exatamente o que a coluna
    nullable significa."""
    p = Product(name="Órfão", type="apostila", price=Decimal("1.00"), sku="ORFAO-9")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post(
        "/orders", json={"payment_method": "PIX"}, headers=headers_for()
    )

    assert response.status_code == 201
    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo is None


async def test_changing_the_stock_supplier_afterwards_does_not_move_the_order(
    client, db_session
):
    """O congelamento é o ponto da coluna. A spec C lê o pedido, não o
    estoque, justamente porque o estoque pode mudar depois."""
    f, p = await _catalogo(
        db_session,
        parceiro="Leroy Merlin",
        rotulo="Cajamar, SP",
        lat=Decimal("-23.355800"),
        lng=Decimal("-46.876400"),
        produto="Luminária",
    )
    await client.post(
        "/cart/items", json={"product_id": str(p.id), "quantity": 1}, headers=headers_for()
    )
    response = await client.post(
        "/orders", json={"payment_method": "PIX"}, headers=headers_for()
    )

    f.origem_rotulo = "Outro Lugar, MG"
    await db_session.commit()

    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    await db_session.refresh(pedido)
    assert pedido.origem_rotulo == "Cajamar, SP"
```

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_order_origin.py -q
```

Esperado: 4 falhas — `origem_rotulo` e `supplier_id` vêm `None`.

- [ ] **Passo 3: implementar**

Em `app/services/pedidos.py::criar_pedido_do_carrinho`, **depois** do `select`
de `products` e **antes** de construir `order`:

```python
    # Origem de expedição: resolvida aqui, uma vez, e CONGELADA no pedido.
    # A spec C lê `orders.origem_*` para simular a rota e não recalcula — o
    # estoque pode mudar de fornecedor depois que o pedido saiu.
    #
    # Um único caminho de código responde "de onde este pedido sai", porque a
    # regra de origem única do carrinho (`services/carrinho.py`) garante que
    # todo item aqui é do mesmo fornecedor. Basta olhar o primeiro que tiver
    # um.
    vinculos = {
        row.produto_id: row.fornecedor_id
        for row in (
            await db.execute(
                select(Estoque.produto_id, Estoque.fornecedor_id).where(
                    Estoque.produto_id.in_([i.product_id for i in cart_items])
                )
            )
        ).all()
    }
    fornecedor_id = next((f for f in vinculos.values() if f is not None), None)
    fornecedor = await db.get(Fornecedor, fornecedor_id) if fornecedor_id else None
```

no construtor de `Order`, três argumentos a mais:

```python
        origem_rotulo=fornecedor.origem_rotulo if fornecedor else None,
        origem_lat=fornecedor.origem_lat if fornecedor else None,
        origem_lng=fornecedor.origem_lng if fornecedor else None,
```

e no `OrderItem(...)` do laço, mais um:

```python
                # `supplier_id` existia desde a fase 2 e nunca era escrito —
                # o comentário do model registrava a omissão. Aqui ele passa a
                # ser preenchido: a separação precisa saber de qual fornecedor
                # o item veio, item a item, mesmo com a regra de origem única
                # em vigor (um pedido antigo pode ser misto).
                supplier_id=vinculos.get(product.id),
```

Imports novos em `services/pedidos.py`: `Estoque`, `Fornecedor` de
`app.models.produto`.

- [ ] **Passo 4: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_order_origin.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 5 passed; **447 passed** no total (442 + 5). `test_orders_routes.py`
(18), `test_orders_parity.py` e `test_orders_services_parity.py` continuam
verdes — sem linha de estoque, `fornecedor` é `None` e as três colunas ficam
nulas, exatamente como antes.

- [ ] **Passo 5: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): freeze the shipping origin on the order

The origin is resolved once, at creation, from the supplier of the cart
items, and copied into the order the way the address snapshot already is.
Spec C reads the order, not the stock, because the stock can change supplier
after the order ships. order_items.supplier_id, declared in phase 2 and
never written, is now filled.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 10: Códigos de pagamento emitidos pelo backend

Ver D2 e D3 e D8. O mock sai do cliente inteiro — PIX e boleto.

**Files:**
- Criar: `back-end/commerce-service/app/services/codigos_pagamento.py`
- Modificar: `back-end/commerce-service/app/schemas/pedido.py`
- Modificar: `back-end/commerce-service/app/routers/pedidos.py`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Criar: `back-end/commerce-service/tests/test_payment_codes.py`

**Interfaces produzidas (task 12):**

```python
# app/services/codigos_pagamento.py
PIX_PREFIXO = "00020126360014BR.GOV.BCB.PIX0114+55119999999995204000053039865802BR5909EDU STORE6009SAO PAULO62290525"
PIX_SUFIXO = "6304ABCD"
TXID_ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def gerar_codigo_pix(order_id: uuid.UUID) -> str: ...
def gerar_linha_digitavel(order_id: uuid.UUID) -> str: ...
def gerar_codigo_pagamento(order_id: uuid.UUID, payment_method: str) -> str | None: ...

# app/exceptions.py
class CodigoPagamentoError(Exception): ...
```

Rota: `POST /orders/{order_id}/confirm-payment` (aluno dono), devolve
`{"payment_method": "...", "payment_code": "..."}`.

- [ ] **Passo 1: medir o mock do cliente, byte a byte**

```bash
cd /home/elias/programming/fiap/estuda_app
sed -n '440,470p' front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart
```

Medido em 2026-09-08 — **conferir que ainda bate antes de escrever o teste**:

```dart
String _generatePixCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  final rng = Random();
  final txid = List.generate(25, (_) => chars[rng.nextInt(chars.length)]).join();
  return '00020126360014BR.GOV.BCB.PIX0114+55119999999995204000053039865802BR5909EDU STORE6009SAO PAULO62290525${txid}6304ABCD';
}

String _generateBoletoCode() {
  final rng = Random();
  final d = List.generate(47, (_) => rng.nextInt(10).toString()).join();
  return '${d.substring(0, 5)}.${d.substring(5, 10)} '
      '${d.substring(10, 15)}.${d.substring(15, 21)} '
      '${d.substring(21, 26)}.${d.substring(26, 32)} '
      '${d.substring(32, 33)} '
      '${d.substring(33, 47)}';
}
```

- [ ] **Passo 2: escrever o teste que falha**

`tests/test_payment_codes.py`:

```python
"""Paridade dos códigos de pagamento com o mock do cliente que eles substituem.

NÃO É INTEGRAÇÃO COM PROVEDOR. É o mesmo algoritmo que rodava no app,
movido para onde o dado nasce. Isso está dito aqui, no docstring do serviço,
e no relatório final da entrega, para ninguém ler como pagamento real.

Paridade ESTRUTURAL, não byte a byte, e o motivo é medido: o cliente
(`checkout_screen.dart::_generatePixCode`) sorteia o `txid` com `Random()` e
NÃO produz o mesmo payload duas vezes para o mesmo pedido. "Idêntico" não
pode ser literal. O que era contrato de verdade — template EMV, segmentos
fixos, alfabeto e comprimento do txid, comprimento total — é o que este
arquivo trava. A aleatoriedade era acidente do mock.

O backend deriva o txid do `order_id`, então o mesmo pedido devolve sempre o
mesmo código: o aluno pode reabrir a tela sem receber um código diferente do
que já copiou.
"""

import re
import uuid

from edu_common.security import create_access_token

from app.config import settings
from app.services.codigos_pagamento import (
    PIX_PREFIXO,
    PIX_SUFIXO,
    TXID_ALFABETO,
    gerar_codigo_pagamento,
    gerar_codigo_pix,
    gerar_linha_digitavel,
)

_PEDIDO = uuid.UUID("0198f3a1-0000-7000-8000-000000000001")


def test_the_pix_payload_keeps_the_client_template():
    codigo = gerar_codigo_pix(_PEDIDO)
    assert codigo.startswith(PIX_PREFIXO)
    assert codigo.endswith(PIX_SUFIXO)
    assert len(codigo) == len(PIX_PREFIXO) + 25 + len(PIX_SUFIXO)


def test_the_txid_uses_the_client_alphabet_and_length():
    txid = gerar_codigo_pix(_PEDIDO)[len(PIX_PREFIXO) : -len(PIX_SUFIXO)]
    assert len(txid) == 25
    assert set(txid) <= set(TXID_ALFABETO)


def test_the_pix_payload_is_deterministic_per_order():
    assert gerar_codigo_pix(_PEDIDO) == gerar_codigo_pix(_PEDIDO)


def test_two_orders_get_two_payloads():
    outro = uuid.UUID("0198f3a1-0000-7000-8000-000000000002")
    assert gerar_codigo_pix(_PEDIDO) != gerar_codigo_pix(outro)


def test_the_boleto_line_keeps_the_client_grouping():
    linha = gerar_linha_digitavel(_PEDIDO)
    assert re.fullmatch(r"\d{5}\.\d{5} \d{5}\.\d{6} \d{5}\.\d{6} \d \d{14}", linha)
    assert len(linha.replace(".", "").replace(" ", "")) == 47


def test_the_boleto_line_is_deterministic_per_order():
    assert gerar_linha_digitavel(_PEDIDO) == gerar_linha_digitavel(_PEDIDO)


def test_the_dispatcher_picks_by_payment_method_label():
    """O rótulo vem do app ("PIX", "Boleto", "Visa ••••1234") — é o que
    `orders.payment_method` guarda. Cartão não tem código para copiar."""
    assert gerar_codigo_pagamento(_PEDIDO, "PIX").startswith(PIX_PREFIXO)
    assert gerar_codigo_pagamento(_PEDIDO, "pix").startswith(PIX_PREFIXO)
    assert " " in gerar_codigo_pagamento(_PEDIDO, "Boleto")
    assert gerar_codigo_pagamento(_PEDIDO, "Visa ••••1234") is None
    assert gerar_codigo_pagamento(_PEDIDO, "") is None
```

e, no mesmo arquivo, a rota:

```python
def headers_for(sub: str, role: str = "student") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _pedido_do_aluno(client, aluno: str, db_session, metodo: str = "PIX") -> str:
    from decimal import Decimal

    from app.models.produto import Product

    produto = Product(name="Apostila", type="apostila", price=Decimal("10.00"), sku="AP-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    await client.post(
        "/cart/items",
        json={"product_id": str(produto.id), "quantity": 1},
        headers=headers_for(aluno),
    )
    criado = await client.post(
        "/orders", json={"payment_method": metodo}, headers=headers_for(aluno)
    )
    return criado.json()["id"]


async def test_confirm_payment_returns_the_code_to_the_owner(client, db_session):
    aluno = "00000000-0000-0000-0000-0000000000dd"
    order_id = await _pedido_do_aluno(client, aluno, db_session)

    response = await client.post(
        f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["payment_method"] == "PIX"
    assert body["payment_code"].startswith(PIX_PREFIXO)


async def test_confirm_payment_is_idempotent(client, db_session):
    aluno = "00000000-0000-0000-0000-0000000000de"
    order_id = await _pedido_do_aluno(client, aluno, db_session)
    primeira = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))
    segunda = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))
    assert primeira.json() == segunda.json()


async def test_confirm_payment_does_not_move_the_order_status(client, db_session):
    """Esta rota NÃO é a do admin. `PATCH /admin/orders/{id}/confirm-payment`
    faz CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO; esta só emite o código.
    Duas rotas com nome parecido e donos diferentes — a colisão é de nome,
    não de comportamento."""
    from sqlalchemy import select

    from app.models.pedido import Order
    from app.services.status_pedido import StatusPedido

    aluno = "00000000-0000-0000-0000-0000000000df"
    order_id = await _pedido_do_aluno(client, aluno, db_session)
    await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))

    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
    ).scalar_one()
    assert pedido.status == StatusPedido.CRIADO.value


async def test_confirm_payment_of_someone_else_order_is_404(client, db_session):
    dono = "00000000-0000-0000-0000-0000000000e1"
    order_id = await _pedido_do_aluno(client, dono, db_session)
    alheio = "00000000-0000-0000-0000-0000000000e2"

    response = await client.post(
        f"/orders/{order_id}/confirm-payment", headers=headers_for(alheio)
    )
    assert response.status_code == 404


async def test_confirm_payment_of_a_card_order_has_no_code(client, db_session):
    aluno = "00000000-0000-0000-0000-0000000000e3"
    order_id = await _pedido_do_aluno(client, aluno, db_session, metodo="Visa ••••1234")
    response = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))
    assert response.status_code == 200
    assert response.json()["payment_code"] is None


async def test_confirm_payment_requires_authentication(client):
    response = await client.post("/orders/00000000-0000-0000-0000-0000000000ff/confirm-payment")
    assert response.status_code == 401
```

- [ ] **Passo 3: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_payment_codes.py -q
```

Esperado: erro de import —
`ModuleNotFoundError: No module named 'app.services.codigos_pagamento'`.

- [ ] **Passo 4: escrever o serviço**

`app/services/codigos_pagamento.py`:

```python
"""Emissão dos códigos copia-e-cola de PIX e boleto.

NÃO É INTEGRAÇÃO COM PROVEDOR DE PAGAMENTO. Nenhum banco, nenhuma API, nenhum
dinheiro. É exatamente o mesmo algoritmo que rodava dentro do app Flutter
(`checkout_screen.dart::_generatePixCode` e `::_generateBoletoCode`), movido
para onde o dado nasce. O payload tem a FORMA de um EMV de PIX e a linha tem
a FORMA de uma linha digitável, e nenhum dos dois é pagável em lugar nenhum.
Isto está dito aqui, e no relatório final da entrega, de propósito.

O que MUDA em relação ao mock do cliente: o identificador é DERIVADO do
`order_id` em vez de sorteado. O cliente usava `Random()`, então o mesmo
pedido produzia um código diferente a cada vez — o aluno que fechasse a
caixa de diálogo e a reabrisse recebia outro código do que já tinha copiado.
Derivar do pedido conserta isso e torna o teste de paridade possível.

A derivação é `sha256` do id do pedido. Não é segredo, não é assinatura, não
protege nada — é só uma função determinística e bem distribuída de UUID para
alfabeto. Por isso NÃO usa `hmac` nem chave: não há nada a autenticar aqui, e
fingir que há seria pior que não ter.
"""

import hashlib
import uuid

# Template EMV do mock do cliente, byte a byte. O `6304ABCD` do fim é um CRC
# fixo e FALSO — no EMV real ele é calculado sobre o payload. Preservado como
# estava: mudá-lo não tornaria o código pagável, só esconderia que é mock.
PIX_PREFIXO = (
    "00020126360014BR.GOV.BCB.PIX0114+5511999999999"
    "5204000053039865802BR5909EDU STORE6009SAO PAULO62290525"
)
PIX_SUFIXO = "6304ABCD"
TXID_ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
TXID_TAMANHO = 25
LINHA_DIGITOS = 47


def _bytes_do_pedido(order_id: uuid.UUID, dominio: str) -> bytes:
    """`dominio` separa os dois códigos: sem ele, PIX e boleto do mesmo
    pedido derivariam da mesma sequência de bytes."""
    return hashlib.sha256(f"{dominio}:{order_id}".encode()).digest()


def gerar_codigo_pix(order_id: uuid.UUID) -> str:
    fonte = _bytes_do_pedido(order_id, "pix")
    txid = "".join(
        TXID_ALFABETO[fonte[i % len(fonte)] % len(TXID_ALFABETO)] for i in range(TXID_TAMANHO)
    )
    return f"{PIX_PREFIXO}{txid}{PIX_SUFIXO}"


def gerar_linha_digitavel(order_id: uuid.UUID) -> str:
    fonte = _bytes_do_pedido(order_id, "boleto")
    d = "".join(str(fonte[i % len(fonte)] % 10) for i in range(LINHA_DIGITOS))
    # Agrupamento idêntico ao do cliente: 5.5 5.6 5.6 1 14.
    return f"{d[0:5]}.{d[5:10]} {d[10:15]}.{d[15:21]} {d[21:26]}.{d[26:32]} {d[32:33]} {d[33:47]}"


def gerar_codigo_pagamento(order_id: uuid.UUID, payment_method: str) -> str | None:
    """Despacha pelo RÓTULO que o app escolheu e que `orders.payment_method`
    guarda ("PIX", "Boleto", "Visa ••••1234").

    Cartão devolve `None`: não há nada para copiar, e o app já mostra
    "Pedido finalizado com sucesso!" nesse caminho. Devolver string vazia em
    vez de `None` faria a tela abrir uma caixa de diálogo vazia.
    """
    rotulo = (payment_method or "").strip().lower()
    if rotulo == "pix":
        return gerar_codigo_pix(order_id)
    if rotulo == "boleto":
        return gerar_linha_digitavel(order_id)
    return None
```

> `hashlib.sha256` sem `usedforsecurity=False` pode acionar a regra `S324` do
> ruff em algumas versões. Se `uv run ruff check .` reclamar, **não** trocar o
> algoritmo: acrescentar `# noqa: S324` com o motivo na mesma linha, porque a
> docstring já explica que não há segurança envolvida.

- [ ] **Passo 5: schema e rota**

Em `app/schemas/pedido.py`:

```python
class PagamentoConfirmadoOut(BaseModel):
    """Resposta de `POST /orders/{id}/confirm-payment`.

    `payment_code` é `None` para cartão — não há nada para copiar. O app
    trata `None` como "não abrir caixa de diálogo de código".
    """

    order_id: UUID
    payment_method: str
    payment_code: str | None = None
```

Em `app/routers/pedidos.py`:

```python
@router.post("/{order_id}/confirm-payment", response_model=PagamentoConfirmadoOut)
async def confirmar_pagamento(
    order_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PagamentoConfirmadoOut:
    """Devolve ao ALUNO o código copia-e-cola do pedido dele.

    NÃO confunda com `PATCH /admin/orders/{pedido_id}/confirm-payment`
    (`app/routers/admin.py`), que é do ADMIN e faz
    `CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO`. A colisão é de nome, não
    de comportamento: esta rota não toca em status nenhum.

    Idempotente por construção — o código é derivado do `order_id`, então
    chamar duas vezes devolve a mesma coisa e nada é gravado.

    O filtro por `user_id` é o veículo de ownership (regra 2 do CLAUDE.md):
    pedido de outro aluno cai no mesmo 404 que pedido inexistente, sem
    revelar qual dos dois é.
    """
    pedido = (
        await db.execute(
            select(Order).where(Order.id == order_id, Order.user_id == uuid.UUID(user_id))
        )
    ).scalar_one_or_none()
    if pedido is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")

    try:
        codigo = gerar_codigo_pagamento(pedido.id, pedido.payment_method)
    except Exception as exc:  # noqa: BLE001 — traduzido em 502 genérico abaixo
        # 502 com mensagem GENÉRICA: o detalhe interno não vaza. E o cliente
        # NUNCA monta o payload como recurso alternativo — seria reintroduzir
        # o mock que esta spec remove.
        logger.exception("falha ao montar o código de pagamento do pedido {}", pedido.id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Não foi possível emitir o código de pagamento"
        ) from exc

    return PagamentoConfirmadoOut(
        order_id=pedido.id, payment_method=pedido.payment_method, payment_code=codigo
    )
```

Imports novos em `routers/pedidos.py`: `logger` de `loguru`,
`gerar_codigo_pagamento` de `app.services.codigos_pagamento`,
`PagamentoConfirmadoOut` de `app.schemas.pedido`, `select` de `sqlalchemy` e
`Order` de `app.models.pedido` (conferir quais já estão lá).

> **Ordem das rotas:** `POST "/{order_id}/confirm-payment"` não colide com
> nenhuma rota existente de `pedidos.py` (as outras são `GET ""`, `POST ""`,
> `GET "/{order_id}"`, `GET "/{order_id}/status-history"`,
> `GET "/{order_id}/delivery-estimate"`, `POST "/{order_id}/rebuy"`).
> Colocá-la junto de `rebuy`.

- [ ] **Passo 6: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_payment_codes.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 13 passed; **460 passed** no total (447 + 13).

- [ ] **Passo 7: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): emit the pix and boleto codes from the backend

Same algorithm the Flutter checkout screen ran, moved to where the data is
born, with the identifier derived from the order id instead of drawn at
random — the client handed the student a different code every time the
dialog reopened. Not a payment provider integration, and the module says so.
POST /orders/{id}/confirm-payment is the student's route and touches no
status; the admin route of the same name is a different act with a different
owner.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 11: Seed do fornecedor Edu e do catálogo Leroy Merlin

Idempotente em duas passadas. Mesmo caminho de seed dos produtos próprios,
sem rota especial.

**Files:**
- Criar: `back-end/commerce-service/app/seeds/parceiros.py`
- Modificar: `back-end/commerce-service/app/seeds/products.py`
- Modificar: `Makefile:112-113`
- Criar: `back-end/commerce-service/tests/test_partners_seed.py`

**Interfaces:**
```python
# app/seeds/parceiros.py
FORNECEDOR_EDU = {"nome": "Edu", "origem_rotulo": "Aclimação, SP", ...}
FORNECEDOR_LEROY = {"nome": "Leroy Merlin", "origem_rotulo": "Cajamar, SP", ...}
SEED_PARCEIROS: list[dict]
SEED_PRODUTOS_LEROY: list[dict]

async def seed_parceiros(session, *, storage=None, fetch_image=_fetch_image) -> dict[str, int]:
    """Devolve {"parceiros": n, "produtos": n, "estoques": n} inseridos."""
```

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_partners_seed.py`:

```python
"""Seed de parceiro. Idempotente em DUAS passadas, como o seed de produto.

Este seed também repara o catálogo existente: os seis produtos de
`SEED_PRODUCTS` (`app/seeds/products.py`) nunca tiveram linha de estoque —
medido, `grep -n "Estoque" app/seeds/products.py` não devolvia nada antes
desta task. Sem fornecedor, eles não aparecem sob parceiro nenhum e o pedido
que os contém sai sem origem. Aqui eles passam a pertencer ao fornecedor
"Edu", com origem Aclimação/SP.
"""

from sqlalchemy import func, select

from app.models.produto import Estoque, Fornecedor, Product
from app.seeds.parceiros import FORNECEDOR_EDU, FORNECEDOR_LEROY, seed_parceiros
from app.seeds.products import SEED_PRODUCTS, seed_products


async def test_the_seed_creates_both_suppliers_with_their_origins(db_session):
    await seed_parceiros(db_session)

    fornecedores = {
        f.nome: f for f in (await db_session.execute(select(Fornecedor))).scalars().all()
    }
    assert set(fornecedores) == {FORNECEDOR_EDU["nome"], FORNECEDOR_LEROY["nome"]}
    assert fornecedores["Edu"].origem_rotulo == "Aclimação, SP"
    assert fornecedores["Leroy Merlin"].origem_rotulo == "Cajamar, SP"
    assert fornecedores["Leroy Merlin"].origem_lat is not None
    assert fornecedores["Leroy Merlin"].origem_lng is not None
    assert fornecedores["Leroy Merlin"].ativo is True


async def test_the_seed_is_idempotent_over_two_full_passes(db_session):
    primeira = await seed_parceiros(db_session)
    segunda = await seed_parceiros(db_session)

    assert primeira["parceiros"] == 2
    assert segunda == {"parceiros": 0, "produtos": 0, "estoques": 0}

    total_fornecedores = (
        await db_session.execute(select(func.count()).select_from(Fornecedor))
    ).scalar_one()
    assert total_fornecedores == 2


async def test_the_leroy_catalog_lands_with_stock_under_leroy(db_session):
    await seed_parceiros(db_session)

    leroy = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Leroy Merlin"))
    ).scalar_one()
    linhas = (
        await db_session.execute(select(Estoque).where(Estoque.fornecedor_id == leroy.id))
    ).scalars().all()

    assert len(linhas) >= 4
    assert all(linha.quantidade > 0 for linha in linhas)
    assert all(linha.estoque_minimo >= 0 for linha in linhas)


async def test_every_seeded_leroy_product_has_a_unique_sku(db_session):
    await seed_parceiros(db_session)
    leroy = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Leroy Merlin"))
    ).scalar_one()
    produtos = (
        await db_session.execute(
            select(Product).join(Estoque, Estoque.produto_id == Product.id).where(
                Estoque.fornecedor_id == leroy.id
            )
        )
    ).scalars().all()
    skus = [p.sku for p in produtos]
    assert all(skus)
    assert len(set(skus)) == len(skus)


async def test_the_seed_adopts_the_pre_existing_edu_catalog(db_session):
    """Rodar o seed de produto ANTES: os seis produtos próprios existem sem
    estoque. `seed_parceiros` tem que adotá-los sob "Edu", senão eles somem
    de toda seção de parceiro e todo pedido que os contém sai sem origem."""
    await seed_products(db_session)
    await seed_parceiros(db_session)

    edu = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Edu"))
    ).scalar_one()
    adotados = (
        await db_session.execute(
            select(func.count()).select_from(Estoque).where(Estoque.fornecedor_id == edu.id)
        )
    ).scalar_one()
    assert adotados == len(SEED_PRODUCTS)


async def test_running_in_the_other_order_gives_the_same_result(db_session):
    """`seed_parceiros` antes de `seed_products` também tem que fechar. O
    Makefile roda os dois, e a ordem entre eles não pode ser um detalhe que
    só quem escreveu conhece."""
    await seed_parceiros(db_session)
    await seed_products(db_session)
    await seed_parceiros(db_session)

    edu = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Edu"))
    ).scalar_one()
    adotados = (
        await db_session.execute(
            select(func.count()).select_from(Estoque).where(Estoque.fornecedor_id == edu.id)
        )
    ).scalar_one()
    assert adotados == len(SEED_PRODUCTS)


def test_no_partner_name_appears_in_a_decision_path():
    """A regra da spec: "Filtro de parceiro ativo é regra de verdade, sem
    `if parceiro == "leroy"` em lugar nenhum". A string só pode existir em
    DADO de seed.

    Este é um teste de costura — nenhuma task individual o possuiria, e é
    exatamente a classe de achado que a revisão por task não vê (lição 3 do
    registro da spec A).
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1] / "app"
    permitidos = {raiz / "seeds" / "parceiros.py"}
    ofensores = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if arquivo in permitidos:
            continue
        texto = arquivo.read_text(encoding="utf-8").lower()
        if "leroy" in texto:
            ofensores.append(str(arquivo.relative_to(raiz.parent)))
    assert ofensores == []
```

- [ ] **Passo 2: rodar e confirmar que falha**

```bash
cd back-end/commerce-service && uv run pytest tests/test_partners_seed.py -q
```

Esperado: erro de import de `app.seeds.parceiros`.

- [ ] **Passo 3: escrever o seed**

`app/seeds/parceiros.py`:

```python
"""Seed idempotente de parceiro, do catálogo da Leroy Merlin, e de estoque.

TRÊS coisas num arquivo só porque as três são a MESMA invariante da spec:
todo produto tem estoque, todo estoque tem fornecedor, todo fornecedor tem
origem. Separá-las produziria três seeds cuja ordem de execução importa e
não está escrita em lugar nenhum.

O catálogo da Leroy é SEED, não integração: não existe API pública da Leroy
Merlin, e o ponto da entrega é o app abrir uma seção de parceiro, não puxar
preço de terceiro.

O nome "Leroy Merlin" aparece aqui e SÓ aqui. Quem decide se a seção do app
aparece é `fornecedores.ativo` (ver `app/services/parceiros.py`); desativar
no painel esvazia a seção sem tocar em código. O teste
`test_no_partner_name_in_a_decision_path` trava isso varrendo `app/`.

Rodar dentro do container do commerce-service (`make services-seed`):

    uv run python -m app.seeds.parceiros
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.produto import Estoque, Fornecedor, Product
from app.seeds.products import _fetch_image  # mesmo downloader do seed de produto

if TYPE_CHECKING:
    from app.storage import ObjectStorage

# Lock consultivo de transação, no mesmo espírito do `_SEED_LOCK_ID` de
# `app/seeds/products.py` (task 1 da spec A): duas execuções simultâneas do
# seed liam "não existe" ao mesmo tempo e inseriam as duas.
_SEED_LOCK_ID = 0x5EED_B_0001

FORNECEDOR_EDU = {
    "nome": "Edu",
    "contato": "logistica@edu.example.com",
    "origem_rotulo": "Aclimação, SP",
    "origem_lat": Decimal("-23.573000"),
    "origem_lng": Decimal("-46.630000"),
}

FORNECEDOR_LEROY = {
    "nome": "Leroy Merlin",
    "contato": "parceria@leroymerlin.com.br",
    "origem_rotulo": "Cajamar, SP",
    "origem_lat": Decimal("-23.355800"),
    "origem_lng": Decimal("-46.876400"),
}

SEED_PARCEIROS: list[dict] = [FORNECEDOR_EDU, FORNECEDOR_LEROY]

# Produtos de ambiente de estudo, como a spec pede: mesa, luminária, cadeira,
# organizadores. Preço e estoque plausíveis; a foto usa o mesmo caminho
# Unsplash do seed de produto.
SEED_PRODUTOS_LEROY: list[dict] = [
    {
        "sku": "LM-MESA-120",
        "name": "Mesa de estudo 120 cm",
        "type": "mobiliario",
        "subtype": "Mesa",
        "description": "Tampo de 120 x 60 cm em MDF, com passa-cabos e pés de aço.",
        "price": "399.90",
        "photo_id": "photo-1518455027359-f3f8164ba6bd",
        "quantidade": 24,
        "estoque_minimo": 4,
    },
    {
        "sku": "LM-LUMI-LED",
        "name": "Luminária de mesa LED",
        "type": "iluminacao",
        "subtype": "Luminária",
        "description": "Três temperaturas de cor e braço articulado, com porta USB.",
        "price": "129.90",
        "photo_id": "photo-1507473885765-e6ed057f782c",
        "quantidade": 40,
        "estoque_minimo": 8,
    },
    {
        "sku": "LM-CADEIRA-ERG",
        "name": "Cadeira ergonômica",
        "type": "mobiliario",
        "subtype": "Cadeira",
        "description": "Encosto em tela, apoio lombar ajustável e braços reguláveis.",
        "price": "749.00",
        "photo_id": "photo-1580480055273-228ff5388ef8",
        "quantidade": 12,
        "estoque_minimo": 3,
    },
    {
        "sku": "LM-ORG-GAV",
        "name": "Organizador de gavetas",
        "type": "organizacao",
        "subtype": "Organizador",
        "description": "Conjunto de quatro divisórias empilháveis para material de estudo.",
        "price": "89.90",
        "photo_id": "photo-1544816155-12df9643f363",
        "quantidade": 60,
        "estoque_minimo": 10,
    },
]


def _unsplash(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?w=800&h=800&fit=crop&q=80&fm=jpg"


async def seed_parceiros(
    session: AsyncSession,
    *,
    storage: "ObjectStorage | None" = None,
    fetch_image=_fetch_image,
) -> dict[str, int]:
    """Cria os dois fornecedores, o catálogo da Leroy e as linhas de estoque.

    Também ADOTA o catálogo próprio: todo produto sem linha de estoque passa
    a pertencer ao fornecedor "Edu". Sem isso os seis produtos de
    `SEED_PRODUCTS` continuariam invisíveis para toda seção de parceiro e
    todo pedido que os contivesse sairia sem origem.

    Idempotente: fornecedor casado por `nome`, produto por `sku`, estoque
    pelo par (produto, fornecedor) — a unicidade que a tabela já declara.
    Devolve quantos de cada foram INSERIDOS.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _SEED_LOCK_ID}
    )

    inseridos = {"parceiros": 0, "produtos": 0, "estoques": 0}

    existentes = {
        f.nome: f for f in (await session.execute(select(Fornecedor))).scalars().all()
    }
    for dados in SEED_PARCEIROS:
        if dados["nome"] in existentes:
            continue
        fornecedor = Fornecedor(**dados, ativo=True)
        session.add(fornecedor)
        existentes[dados["nome"]] = fornecedor
        inseridos["parceiros"] += 1
    await session.flush()

    edu = existentes[FORNECEDOR_EDU["nome"]]
    leroy = existentes[FORNECEDOR_LEROY["nome"]]

    produtos_por_sku = {
        p.sku: p
        for p in (await session.execute(select(Product))).scalars().all()
        if p.sku
    }
    for dados in SEED_PRODUTOS_LEROY:
        produto = produtos_por_sku.get(dados["sku"])
        if produto is None:
            produto = Product(
                name=dados["name"],
                type=dados["type"],
                subtype=dados["subtype"],
                description=dados["description"],
                price=Decimal(dados["price"]),
                sku=dados["sku"],
                active=True,
            )
            session.add(produto)
            produtos_por_sku[dados["sku"]] = produto
            inseridos["produtos"] += 1
        await _aplicar_imagem(produto, dados, storage=storage, fetch_image=fetch_image)
    await session.flush()

    # Estoque: casado pelo par (produto, fornecedor) — a mesma unicidade que
    # `uq_produto_fornecedor` declara na tabela.
    pares = {
        (e.produto_id, e.fornecedor_id)
        for e in (await session.execute(select(Estoque))).scalars().all()
    }
    for dados in SEED_PRODUTOS_LEROY:
        produto = produtos_por_sku[dados["sku"]]
        if (produto.id, leroy.id) in pares:
            continue
        session.add(
            Estoque(
                produto_id=produto.id,
                fornecedor_id=leroy.id,
                quantidade=dados["quantidade"],
                estoque_minimo=dados["estoque_minimo"],
            )
        )
        pares.add((produto.id, leroy.id))
        inseridos["estoques"] += 1

    # Adoção do catálogo próprio.
    com_estoque = {produto_id for produto_id, _ in pares}
    orfaos = [
        p
        for p in (await session.execute(select(Product))).scalars().all()
        if p.id not in com_estoque
    ]
    for produto in orfaos:
        session.add(
            Estoque(
                produto_id=produto.id, fornecedor_id=edu.id, quantidade=25, estoque_minimo=5
            )
        )
        inseridos["estoques"] += 1

    await session.commit()
    logger.info("seed de parceiros: {}", inseridos)
    return inseridos


async def _aplicar_imagem(produto, dados, *, storage, fetch_image) -> None:
    """Mesmo contrato do `_apply_image` do seed de produto: falha de download
    é logada e deixa a imagem atual intacta, nunca apaga uma foto boa."""
    if storage is None:
        return
    chave = f"products/partner-{dados['sku'].lower()}.jpg"
    try:
        corpo = await fetch_image(_unsplash(dados["photo_id"]))
    except Exception as exc:  # rede/HTTP/timeout/tamanho
        logger.warning("seed: falha ao baixar foto de {!r}: {}", dados["sku"], exc)
        return
    await storage.put_object(chave, corpo, "image/jpeg")
    produto.image_url = chave


async def main() -> None:
    from app.storage import ObjectStorage

    async with async_session() as session:
        inseridos = await seed_parceiros(session, storage=ObjectStorage())
        logger.info("inseridos: {}", inseridos)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

Em `Makefile:112-113`, o alvo `services-seed` passa a rodar os dois módulos,
nessa ordem:

```make
services-seed: ## Seed the commerce catalog and partners (idempotent; downloads photos into MinIO)
	cd $(BACK_ROOT) && $(COMPOSE) exec -T commerce-service uv run python -m app.seeds.products
	cd $(BACK_ROOT) && $(COMPOSE) exec -T commerce-service uv run python -m app.seeds.parceiros
```

> **A ordem não importa para a correção** — o teste
> `test_running_in_the_other_order_gives_the_same_result` prova as duas
> ordens. Ela é escolhida assim porque `products` primeiro deixa `parceiros`
> adotar tudo numa passada só.
>
> **Não rodar `make services-seed`.** Ele usa `docker compose exec`, que está
> proibido. A verificação é a suíte.

- [ ] **Passo 4: rodar, suíte e lint**

```bash
cd back-end/commerce-service && uv run pytest tests/test_partners_seed.py -q && \
  uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: 7 passed; **467 passed** no total (460 + 7).
`test_products_seed.py` (13) tem que continuar verde.

- [ ] **Passo 5: conferir que o Makefile continua parseável**

```bash
cd /home/elias/programming/fiap/estuda_app && make -n services-seed
```

Esperado: imprime as duas linhas de `docker compose exec`. **`-n` só imprime;
não executa.**

- [ ] **Passo 6: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add back-end/commerce-service Makefile && git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): seed the Edu and Leroy Merlin partners with their catalogs

One seed for three things because they are one invariant: every product has
stock, every stock row has a supplier, every supplier has an origin. It also
adopts the six own-catalog products, which never had a stock row and so
belonged to no partner and produced orders with no origin. Idempotent across
two full passes in either order relative to the product seed. The partner
name appears only in this file, and a test sweeps app/ to keep it that way.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 12: Flutter — seção de parceiros, 409 legível, e a saída do mock

Três entregas que se tocam na mesma tela e por isso viajam juntas: a seção de
parceiros, a mensagem de origem única, e a remoção dos geradores de código.

**Files:**
- Criar: `front-end-flutter/lib/features/marketplace/domain/partner.dart`
- Criar: `front-end-flutter/lib/features/marketplace/data/partner_service.dart`
- Criar: `front-end-flutter/lib/features/marketplace/presentation/partners_provider.dart`
- Criar: `front-end-flutter/lib/features/marketplace/presentation/widgets/partners_section.dart`
- Modificar: `front-end-flutter/lib/features/marketplace/presentation/marketplace_screen.dart`
- Modificar: `front-end-flutter/lib/features/marketplace/data/product_service.dart`
- Modificar: `front-end-flutter/lib/features/marketplace/data/checkout_service.dart`
- Modificar: `front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart`
- Modificar: `front-end-flutter/lib/features/cart/data/cart_service.dart`
- Criar: `front-end-flutter/test/features/marketplace/partner_service_test.dart`
- Criar: `front-end-flutter/test/features/marketplace/partners_provider_test.dart`
- Criar: `front-end-flutter/test/features/marketplace/partners_section_test.dart`
- Criar: `front-end-flutter/test/features/cart/cart_service_conflict_test.dart`
- Modificar: `front-end-flutter/test/features/marketplace/checkout_service_test.dart`

**Interfaces:**
```dart
class Partner {
  final int id; final String name; final bool active;
  final String originLabel;
  factory Partner.fromJson(Map<String, dynamic> json);
}

class PartnerService {
  Future<List<Partner>> fetchActivePartners();          // GET /partners?active=true
  Future<List<Product>> fetchPartnerProducts(int id);   // GET /products?partner_id=
}

enum PartnersViewState { loading, success, error }
class PartnersProvider extends ChangeNotifier {
  PartnersViewState get state;
  List<Partner> get partners;
  Map<int, List<Product>> get productsByPartner;
  String? get errorMessage;
  Future<void> load();
}

// CheckoutService
Future<String> placeOrder({required String paymentMethod, String? addressId});
Future<String?> confirmPayment(String orderId);  // devolve payment_code ou null
```

- [ ] **Passo 1: escrever os testes que falham**

`test/features/marketplace/partner_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/partner_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

void main() {
  test('fetchActivePartners asks the backend which partners are active',
      () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 2,
              'nome': 'Leroy Merlin',
              'ativo': true,
              'origem_rotulo': 'Cajamar, SP',
            },
          ],
          'total': 1,
          'limit': 20,
          'offset': 0,
        }),
        200,
      );
    });

    final partners = await PartnerService(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchActivePartners();

    expect(partners, hasLength(1));
    expect(partners.first.id, 2);
    expect(partners.first.name, 'Leroy Merlin');
    expect(partners.first.originLabel, 'Cajamar, SP');
    // O app NÃO sabe que a resposta é a Leroy. Ele pergunta quem está ativo.
    expect(captured.url.queryParameters['active'], 'true');
    expect(captured.url.path, endsWith('/partners'));
  });

  test('fetchPartnerProducts filters the catalog by partner id', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {'id': 'a', 'name': 'Luminária', 'type': 'iluminacao', 'price': '129.90'},
          ],
          'total': 1,
          'limit': 50,
          'offset': 0,
        }),
        200,
      );
    });

    final produtos = await PartnerService(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchPartnerProducts(2);

    expect(produtos, hasLength(1));
    expect(produtos.first.name, 'Luminária');
    expect(captured.url.queryParameters['partner_id'], '2');
  });

  test('a non-200 becomes a PartnerException with a readable message',
      () async {
    final client = MockClient((_) async => http.Response('{}', 500));
    expect(
      () => PartnerService(client: client, tokenStore: _FakeTokenStore())
          .fetchActivePartners(),
      throwsA(isA<PartnerException>()),
    );
  });
}
```

`test/features/marketplace/partners_provider_test.dart`:

```dart
import 'package:edu_ia/features/marketplace/data/partner_service.dart';
import 'package:edu_ia/features/marketplace/domain/partner.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/partners_provider.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakePartnerService implements PartnerService {
  _FakePartnerService({this.partners = const [], this.products = const {}, this.error});

  final List<Partner> partners;
  final Map<int, List<Product>> products;
  final String? error;

  @override
  Future<List<Partner>> fetchActivePartners() async {
    if (error != null) throw PartnerException(error!);
    return partners;
  }

  @override
  Future<List<Product>> fetchPartnerProducts(int partnerId) async {
    if (error != null) throw PartnerException(error!);
    return products[partnerId] ?? const [];
  }
}

const _produto = Product(
  id: 'a',
  name: 'Luminária',
  type: 'iluminacao',
  subtype: '',
  description: '',
  price: 129.90,
);

void main() {
  test('an empty active list leaves the section empty, not broken', () async {
    final provider = PartnersProvider(service: _FakePartnerService());
    await provider.load();
    expect(provider.state, PartnersViewState.success);
    expect(provider.partners, isEmpty);
    expect(provider.errorMessage, isNull);
  });

  test('one active partner loads its catalog', () async {
    final provider = PartnersProvider(
      service: _FakePartnerService(
        partners: const [Partner(id: 2, name: 'Leroy Merlin', active: true, originLabel: 'Cajamar, SP')],
        products: const {2: [_produto]},
      ),
    );
    await provider.load();
    expect(provider.state, PartnersViewState.success);
    expect(provider.partners.single.name, 'Leroy Merlin');
    expect(provider.productsByPartner[2], hasLength(1));
  });

  test('a network error lands in the error state with a message', () async {
    final provider = PartnersProvider(
      service: _FakePartnerService(error: 'Não foi possível conectar ao servidor'),
    );
    await provider.load();
    expect(provider.state, PartnersViewState.error);
    expect(provider.errorMessage, 'Não foi possível conectar ao servidor');
  });
}
```

`test/features/marketplace/partners_section_test.dart` — teste de widget com
os três casos que a spec pede (lista vazia, um parceiro, erro de rede):

```dart
import 'package:edu_ia/features/marketplace/domain/partner.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/partners_provider.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/partners_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _produto = Product(
  id: 'a',
  name: 'Luminária de mesa',
  type: 'iluminacao',
  subtype: 'Luminária',
  description: '',
  price: 129.90,
);

Future<void> _montar(WidgetTester tester, Widget child) =>
    tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child))));

void main() {
  testWidgets('with no active partner the section renders nothing', (tester) async {
    await _montar(
      tester,
      const PartnersSection(
        state: PartnersViewState.success,
        partners: [],
        productsByPartner: {},
      ),
    );
    expect(find.text('Parceiros'), findsNothing);
  });

  testWidgets('with one active partner it shows the header and the catalog',
      (tester) async {
    await _montar(
      tester,
      const PartnersSection(
        state: PartnersViewState.success,
        partners: [Partner(id: 2, name: 'Leroy Merlin', active: true, originLabel: 'Cajamar, SP')],
        productsByPartner: {2: [_produto]},
      ),
    );
    expect(find.text('Parceiros'), findsOneWidget);
    expect(find.text('Leroy Merlin'), findsOneWidget);
    expect(find.text('Luminária de mesa'), findsOneWidget);
  });

  testWidgets('on a network error it shows the message and a retry',
      (tester) async {
    var tentativas = 0;
    await _montar(
      tester,
      PartnersSection(
        state: PartnersViewState.error,
        partners: const [],
        productsByPartner: const {},
        errorMessage: 'Não foi possível conectar ao servidor',
        onRetry: () => tentativas++,
      ),
    );
    expect(find.text('Não foi possível conectar ao servidor'), findsOneWidget);
    await tester.tap(find.text('Tentar novamente'));
    expect(tentativas, 1);
  });
}
```

`test/features/cart/cart_service_conflict_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

void main() {
  test('a 409 surfaces the server message verbatim', () async {
    const mensagem =
        'Seu carrinho já tem itens de outro parceiro. '
        'Finalize ou esvazie o carrinho antes de misturar.';
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({'detail': mensagem}),
        409,
        headers: {'content-type': 'application/json; charset=utf-8'},
      ),
    );

    await expectLater(
      CartService(client: client, tokenStore: _FakeTokenStore())
          .addItem('produto', 1),
      throwsA(
        isA<CartException>().having((e) => e.message, 'message', mensagem),
      ),
    );
  });

  test('other failures keep the generic message with the status code',
      () async {
    final client = MockClient((_) async => http.Response('{}', 500));
    await expectLater(
      CartService(client: client, tokenStore: _FakeTokenStore())
          .addItem('produto', 1),
      throwsA(
        isA<CartException>().having(
          (e) => e.message,
          'message',
          contains('500'),
        ),
      ),
    );
  });

  test('a 409 with an unreadable body falls back to the generic message',
      () async {
    final client = MockClient((_) async => http.Response('<html>', 409));
    await expectLater(
      CartService(client: client, tokenStore: _FakeTokenStore())
          .addItem('produto', 1),
      throwsA(
        isA<CartException>().having((e) => e.message, 'message', contains('409')),
      ),
    );
  });
}
```

Em `test/features/marketplace/checkout_service_test.dart`, acrescentar:

```dart
  test('confirmPayment returns the code the backend issued', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'order_id': 'abc',
          'payment_method': 'PIX',
          'payment_code': '000201263600...6304ABCD',
        }),
        200,
      );
    });

    final code = await CheckoutService(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).confirmPayment('abc');

    expect(code, '000201263600...6304ABCD');
    expect(captured.method, 'POST');
    expect(captured.url.path, endsWith('/orders/abc/confirm-payment'));
  });

  test('confirmPayment returns null when there is nothing to copy', () async {
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({
          'order_id': 'abc',
          'payment_method': 'Visa ••••1234',
          'payment_code': null,
        }),
        200,
      ),
    );
    final code = await CheckoutService(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).confirmPayment('abc');
    expect(code, isNull);
  });
```

> Conferir o nome exato do `_FakeTokenStore` já declarado nesse arquivo antes
> de colar: `grep -n "class _Fake" test/features/marketplace/checkout_service_test.dart`.

- [ ] **Passo 2: rodar e confirmar que falham**

```bash
cd front-end-flutter && flutter test test/features/marketplace/ test/features/cart/
```

Esperado: erros de compilação —
`Error: Couldn't resolve the package 'partner_service.dart'` e
`The method 'confirmPayment' isn't defined`.

- [ ] **Passo 3: domínio e serviço**

`lib/features/marketplace/domain/partner.dart`:

```dart
/// Parceiro do marketplace. Espelha `ParceiroOut` do backend: `id` é inteiro
/// (a tabela `fornecedores` nunca migrou para UUID) e as coordenadas chegam
/// como string decimal, quando chegam.
///
/// O app NÃO sabe quais parceiros existem. Ele pergunta
/// `GET /partners?active=true` e desenha o que voltar — desativar um parceiro
/// no painel esvazia a seção sem tocar em nada aqui.
class Partner {
  final int id;
  final String name;
  final bool active;
  final String originLabel;

  const Partner({
    required this.id,
    required this.name,
    required this.active,
    this.originLabel = '',
  });

  factory Partner.fromJson(Map<String, dynamic> json) {
    return Partner(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['nome'] as String?) ?? '',
      active: (json['ativo'] as bool?) ?? false,
      originLabel: (json['origem_rotulo'] as String?) ?? '',
    );
  }
}
```

`lib/features/marketplace/data/partner_service.dart` segue o molde exato de
`product_service.dart` (mesmo `appAuthClient`, mesmo `TokenStore`, mesmo
`_get`/`_headers`, mesma `PartnerException`), com dois métodos:

```dart
  /// Quais parceiros o app deve mostrar. A resposta é dado, não configuração
  /// do app: hoje ela tem um elemento, e o app não sabe disso.
  Future<List<Partner>> fetchActivePartners() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/partners?active=true&limit=50');
    final body = await _get(uri, 'Falha ao carregar parceiros');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items.map((e) => Partner.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Product>> fetchPartnerProducts(int partnerId, {int limit = 50}) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/products?partner_id=$partnerId&limit=$limit',
    );
    final body = await _get(uri, 'Falha ao carregar o catálogo do parceiro');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items.map((e) => Product.fromJson(e as Map<String, dynamic>)).toList();
  }
```

- [ ] **Passo 4: provider, seção e encaixe na tela**

`lib/features/marketplace/presentation/partners_provider.dart` segue o molde
de `products_provider.dart`: `enum PartnersViewState { loading, success, error }`,
campos privados, getters, e `load()` que busca os ativos e, para cada um, o
catálogo — em paralelo com `Future.wait`, porque a lista é curta e uma
chamada por parceiro em série somaria latência visível.

`lib/features/marketplace/presentation/widgets/partners_section.dart` é
**stateless e sem provider**: recebe `state`, `partners`, `productsByPartner`,
`errorMessage` e `onRetry` por parâmetro. É isso que torna o teste de widget
possível sem montar `ChangeNotifierProvider` — mesmo padrão que
`MarketplaceView` já usa ao separar a tela do `MarketplaceScreen`.

Regras de render, exatamente como os três testes pedem:
- `state == success` e `partners` vazia: `SizedBox.shrink()`. Nenhum título.
- `state == success` com parceiro: título `Parceiros`, e por parceiro o nome,
  o `originLabel` em texto secundário, e uma faixa horizontal com os produtos
  (reaproveitar `_ProductCard` de `marketplace_screen.dart` — extraí-lo para
  o arquivo de widgets se ele ainda for privado da tela).
- `state == error`: a `errorMessage` e um `TextButton` "Tentar novamente" que
  chama `onRetry`.
- `state == loading`: `CircularProgressIndicator` pequeno, centralizado.

Em `marketplace_screen.dart`:
- `MarketplaceScreen.build` passa a montar **dois** providers
  (`MultiProvider` com `ProductsProvider()..load()` e
  `PartnersProvider()..load()`).
- Em `_buildBody`, no ramo `success`, um `SliverToBoxAdapter` novo com a
  `PartnersSection` **depois** do grid do catálogo próprio — a spec diz
  "separada do catálogo próprio".

- [ ] **Passo 5: 409 legível no carrinho**

Em `lib/features/cart/data/cart_service.dart::_send`, trocar o bloco de erro:

```dart
    if (res.statusCode != 200 && res.statusCode != 201) {
      // 409 é a regra de origem única do carrinho: o backend manda a
      // mensagem PRONTA para exibir (ver CarrinhoOrigemMistaError.MENSAGEM no
      // commerce-service). Reescrevê-la aqui duplicaria a regra em dois
      // lugares que divergiriam.
      if (res.statusCode == 409) {
        final message = _detailOrNull(res.body);
        if (message != null) throw CartException(message);
      }
      throw CartException('$error (${res.statusCode})');
    }
```

e a função auxiliar, no mesmo arquivo:

```dart
/// Lê `detail` do corpo, ou `null` se o corpo não for um JSON com `detail`
/// legível. Sem isso, uma página de erro HTML de um proxy viraria a mensagem
/// que o aluno lê.
String? _detailOrNull(String body) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) {
      final detail = decoded['detail'];
      if (detail is String && detail.trim().isNotEmpty) return detail;
    }
  } on FormatException {
    return null;
  }
  return null;
}
```

- [ ] **Passo 6: o mock de código sai do app**

Em `checkout_service.dart`:

```dart
  /// Pede ao backend o código copia-e-cola do pedido. `null` quando não há
  /// nada para copiar (cartão).
  ///
  /// O app NÃO gera mais código de pagamento. Os dois geradores que viviam em
  /// `checkout_screen.dart` (`_generatePixCode`, `_generateBoletoCode`) foram
  /// para `commerce-service/app/services/codigos_pagamento.py`, onde o dado
  /// nasce. Se esta chamada falhar, a tela mostra o erro — ela nunca monta o
  /// payload por conta própria, porque isso reintroduziria o mock.
  Future<String?> confirmPayment(String orderId) async {
    final headers = await _headers();
    final res = await _send(
      () => _client.post(
        Uri.parse('${ApiConfig.baseUrl}/orders/$orderId/confirm-payment'),
        headers: {'Content-Type': 'application/json', ...headers},
      ),
      accept: const {200},
      error: 'Falha ao emitir o código de pagamento',
    );
    return (jsonDecode(res.body) as Map<String, dynamic>)['payment_code'] as String?;
  }
```

Em `checkout_screen.dart`:
- **apagar** `_generatePixCode` e `_generateBoletoCode` (linhas 444-466,
  incluindo o comentário de bloco "Geração de códigos (mock)"), e o
  `import 'dart:math';` se ele ficar órfão (`flutter analyze` acusa).
- em `_placeOrder`, guardar o id devolvido por `placeOrder` e trocar o
  `switch` por:

```dart
    final orderId = await CheckoutService().placeOrder(...);
    // ...
    if (method.type == PaymentMethodType.creditCard) {
      _snack('Pedido finalizado com sucesso!');
      Navigator.pop(context);
      return;
    }

    final String? code;
    try {
      code = await CheckoutService().confirmPayment(orderId);
    } on CheckoutException catch (e) {
      if (mounted) _snack(e.message);
      return;
    }
    if (!mounted || code == null) return;

    final ehPix = method.type == PaymentMethodType.pix;
    _showCopyCodeDialog(
      title: ehPix ? 'Pague com PIX' : 'Pague com Boleto',
      description: ehPix
          ? 'Copie o código abaixo e cole no app do seu banco para concluir o pagamento.'
          : 'Copie a linha digitável abaixo e pague no app do seu banco. Compensação em até 2 dias úteis.',
      code: code,
      copiedMessage: ehPix ? 'Código PIX copiado' : 'Linha digitável copiada',
    );
```

> `cart.clear()` continua antes disso, como já está. **Conferir a ordem no
> arquivo real** — se `confirmPayment` falhar depois do `clear()`, o carrinho
> já foi esvaziado no servidor pelo `POST /orders`, então limpar o estado
> local continua correto.

- [ ] **Passo 7: rodar tudo**

```bash
cd front-end-flutter && flutter analyze; flutter test
```

Esperado: `flutter analyze` com **os mesmos 6 avisos `info`** do baseline e
exit 1 — nenhum achado novo. Se aparecer um sétimo, é regressão desta task.
`flutter test`: **175 passed** (161 + 3 + 3 + 3 + 3 + 2). **Medir o número
real e usá-lo**; a soma acima é estimativa do plano, e a regra que vale é
"161 continuam passando e a contagem sobe".

- [ ] **Passo 8: confirmar que o mock sumiu**

```bash
cd /home/elias/programming/fiap/estuda_app
grep -rn "_generatePixCode\|_generateBoletoCode\|BR.GOV.BCB.PIX" front-end-flutter/lib/
```

Esperado: **nenhuma saída**. Este é o critério de pronto 5 da spec.

- [ ] **Passo 9: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add front-end-flutter && git diff --staged
git commit -m "$(cat <<'MSG'
feat(marketplace): add the partners section and drop the client-side codes

The app asks the backend which partners are active and draws what comes
back, so disabling a partner in the panel empties the section with no code
change. A mixed-origin cart surfaces the server's 409 message verbatim
instead of an error code. The PIX and boleto generators are gone from
checkout_screen.dart: the code now comes from confirm-payment, and the
screen never builds a payload of its own.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 13: `web-admin` no gateway

Ver D9, D10 e D11. O painel nunca rodou contra este backend; a diferença de
forma foi medida serviço a serviço.

**Files:**
- Modificar: `web-admin/proxy.conf.json`
- Modificar: `web-admin/src/app/core/services/auth.service.ts`
- Modificar: `web-admin/src/app/core/models/auth.model.ts`
- Modificar: `web-admin/src/app/core/services/product.service.ts` + `models/product.model.ts`
- Modificar: `web-admin/src/app/core/services/inventory.service.ts` + `models/inventory.model.ts`
- Modificar: `web-admin/src/app/core/services/carrier.service.ts` + `models/carrier.model.ts`
- Modificar: `web-admin/src/app/core/services/occurrence.service.ts` + `models/occurrence.model.ts`
- Modificar: `web-admin/src/app/core/services/dashboard.service.ts` + `models/dashboard.model.ts`
- Modificar: as quatro páginas e os quatro modais que consomem esses tipos

**Verificação:** `npm install` + `npm run build`. Não há suíte de teste no
`web-admin` e esta spec não cria uma (D11) — o build AOT do Angular faz
type-check de template, que é o que pega mudança de forma de payload.

- [ ] **Passo 1: medir a diferença, endpoint a endpoint**

Antes de tocar em código, produzir a tabela de correspondência e **colar no
relatório da task**:

```bash
cd /home/elias/programming/fiap/estuda_app
grep -rn "apiUrl}/" web-admin/src/app/core/services/ | sort
cd back-end/commerce-service && uv run python - <<'PY'
from app.main import app
for r in sorted(app.routes, key=lambda r: getattr(r, "path", "")):
    if hasattr(r, "methods"):
        print(sorted(r.methods), r.path)
PY
```

Correspondência medida em 2026-09-08 (**reconfirmar**: as tasks 2 a 10
acrescentaram rotas depois dessa medição):

| Angular chamava | Passa a chamar | Diferença de forma |
|---|---|---|
| `POST /api/v1/auth/login` | `POST /api/auth/login` | resposta é `{user, tokens:{access_token}}`, não `{accessToken, user}` |
| `GET /api/v1/dashboard?days=` | `GET /api/analytics/executive-summary?dias=` | ver D10 |
| `GET /api/v1/inventory?page&size&search&lowStock` | `GET /api/admin/inventory?limit&offset` | envelope `{items,total,limit,offset}`; sem `search`/`lowStock` no backend |
| `PATCH /api/v1/inventory/{productId}` `{quantity,reason}` | `PATCH /api/admin/inventory/{estoque_id}/adjust?quantidade=&motivo=` | id é o do ESTOQUE, não do produto; parâmetros vão na query |
| `GET/POST/PUT /api/v1/products/{id}` | `GET/POST/PUT /api/products/{id}` | `id` é UUID string, não number; envelope `{items,...}` |
| `GET/POST/PUT/PATCH /api/v1/carriers` | `GET/POST/PUT/PATCH /api/carriers` | envelope; `average_delivery_days` em snake_case; `rating`/`sla_percentage` chegam como string |
| `GET/PATCH /api/v1/carrier-occurrences` | `GET /api/occurrences`, `POST /api/occurrences/{id}/close` | `status` é `ABERTA`/`RESOLVIDA`; campos em português |

> **`search` e `lowStock` no estoque:** o backend não os tem. Duas saídas —
> acrescentá-los a `GET /admin/inventory` (mais uma task de backend, fora do
> escopo da spec) ou filtrar no cliente sobre uma página grande. **Escolha do
> plano: filtrar no cliente**, com `limit=100`, e registrar a limitação como
> pendência na task 14. O painel de administração desta entrega opera dezenas
> de linhas, não milhares; um filtro de servidor que não existe não pode ser
> inventado no cliente como se existisse, mas filtrar localmente o que já foi
> baixado é honesto e visível no código.

- [ ] **Passo 2: repontar a base**

`web-admin/proxy.conf.json`:

```json
{
  "/api": {
    "target": "http://localhost:8100",
    "secure": false,
    "changeOrigin": true,
    "logLevel": "debug"
  }
}
```

E em **cada** um dos seis serviços, `private readonly apiUrl = '/api/v1';`
vira `private readonly apiUrl = '/api';`.

> `8100` é a porta do gateway nesta máquina, medida em
> `back-end/docker-compose.yml:140` (`${GATEWAY_PORT_EXTERNAL:-8100}:8000`).
> A `8080` que estava ali era a API Java que a spec A eliminou.

- [ ] **Passo 3: auth**

`models/auth.model.ts`:

```ts
export interface AuthUser {
  id: string;   // UUID, não number — auth-users-service usa UUID
  name: string;
  email: string;
  role: string;
}

/** Formato de `AuthResponseOut` do auth-users-service: `{user, tokens}`. */
export interface LoginResponse {
  user: AuthUser;
  tokens: {
    access_token: string;
    refresh_token: string;
    token_type: string;
  };
}
```

`auth.service.ts`, dentro do `tap`:

```ts
          storage.setItem(this.tokenKey, response.tokens.access_token);
          storage.setItem(this.userKey, JSON.stringify(response.user));
```

> **Não** guardar o `refresh_token`. O painel não implementa refresh, e um
> token de 14 dias em `localStorage` que ninguém usa é superfície de ataque
> sem contrapartida. Registrar "o painel não faz refresh; a sessão expira com
> o access token" como pendência na task 14.

- [ ] **Passo 4: produtos e estoque**

`models/product.model.ts` — `id: string`, `sku: string`, `active: boolean`,
`price: string` (o backend serializa dinheiro como string, de propósito),
sem `minimumStock` (ele vive no estoque agora):

```ts
export interface Product {
  id: string;
  name: string;
  sku: string;
  type: string;
  subtype: string;
  description: string;
  price: string;
  active: boolean;
  image_url: string;
}

export interface CreateProductRequest {
  name: string; type: string; subtype: string; description: string;
  price: string; sku: string; active: boolean;
  fornecedor_id: number; quantidade_inicial: number; estoque_minimo: number;
}

export type UpdateProductRequest = Omit<
  CreateProductRequest,
  'fornecedor_id' | 'quantidade_inicial' | 'estoque_minimo'
>;
```

`models/inventory.model.ts`:

```ts
export type InventoryStatus = 'NORMAL' | 'LOW_STOCK' | 'OUT_OF_STOCK';

/** Espelha `EstoqueOut`. `id` é o do ESTOQUE — é ele que a rota de ajuste
 *  endereça, não o do produto. */
export interface InventoryItem {
  id: number;
  produto_id: string;
  fornecedor_id: number;
  quantidade: number;
  estoque_minimo: number;
  atualizado_em: string | null;
}

export interface InventoryPage {
  items: InventoryItem[];
  total: number;
  limit: number;
  offset: number;
}

/** Derivado no cliente a partir de `quantidade` e `estoque_minimo` — o
 *  backend não devolve rótulo de status, e inventar um campo no cliente que
 *  o servidor não tem seria mentir sobre a origem do dado. Isto é CÁLCULO,
 *  não invenção: as duas parcelas vêm do servidor. */
export function inventoryStatus(item: InventoryItem): InventoryStatus {
  if (item.quantidade <= 0) return 'OUT_OF_STOCK';
  if (item.quantidade <= item.estoque_minimo) return 'LOW_STOCK';
  return 'NORMAL';
}
```

`inventory.service.ts`: `listInventory(limit, offset)` chama
`GET /api/admin/inventory`; `adjustInventory(estoqueId, {quantidade, motivo})`
chama `PATCH /api/admin/inventory/{estoqueId}/adjust` com `HttpParams`. O
`search`/`lowStock` viram filtro no componente sobre `items`. `getSummary()`
deixa de depender do dashboard e conta sobre a página carregada.

A página `products-stock.component.ts` precisa do **nome do produto**, que
`EstoqueOut` não traz. Resolver com um `forkJoin` de `GET /api/products?limit=100`
mais a listagem de estoque, casando por `produto_id`. Documentar em comentário
que isso é uma junção no cliente por falta de rota agregada, e registrar como
pendência na task 14.

- [ ] **Passo 5: transportadoras e ocorrências**

`models/carrier.model.ts` — campos em snake_case, `rating`/`sla_percentage`
como `string`, envelope `{items,total,limit,offset}`.
`carrier.service.ts` — `listCarriers(limit, offset, search, status)` mapeia
`search`/`status` para os parâmetros que o backend já aceita (task 4);
`getSummary()` conta sobre `total` e sobre uma consulta com `status=ACTIVE`,
sem tocar no dashboard.

`models/occurrence.model.ts` — espelha `OcorrenciaOut`:
`{id, pedido_id, transportadora_id, tipo, status, motivo, criado_em, resolvido_em}`.
`OccurrenceStatus` vira `'ABERTA' | 'RESOLVIDA'`; `OccurrenceType` vira
`'FALTA_ESTOQUE' | 'ATRASO_ENTREGA' | 'DANO' | 'FALHA_ENTREGA' | 'OUTRO'`.
`occurrence.service.ts` — `GET /api/occurrences` com `carrier_id`/`tipo`/`status`,
e `updateStatus` vira `close(id, observacao?)` chamando
`POST /api/occurrences/{id}/close`.

Os rótulos de exibição (`typeLabel`, `statusLabel` em
`occurrences.component.ts`) traduzem os valores em português para o que a
tela mostra. **Traduzir na exibição, nunca no serviço** — o serviço fala o
idioma do backend.

- [ ] **Passo 6: dashboard**

`models/dashboard.model.ts` passa a espelhar `ResumoExecutivoOut`:

```ts
export interface DashboardMetrics {
  pedidos_criados: number;
  pedidos_por_status: Record<string, number>;
  ocorrencias_abertas: number;
  ocorrencias_resolvidas: number;
  diagnosticos_por_acao: Record<string, number>;
}

export interface DashboardResponse {
  periodo_dias: number;
  metricas: DashboardMetrics;
  resumo_executivo: string;
}
```

`dashboard.service.ts` chama `GET /api/analytics/executive-summary?dias=30`.

`dashboard.component` mostra: pedidos criados, pedidos por status, ocorrências
abertas e resolvidas, o resumo executivo, e — de `/partners` e `/carriers` —
os totais de parceiros e transportadoras ativos.

**O que NÃO existe e sai da tela:** `registeredStudents`, `activeStudents`,
`newRegistrations`, `inactiveRiskStudents`, `activityHistory`,
`registeredProducts`, `lowStockProducts`, `activeCarriers`, `lowStock[]`,
`carriers[]`, `recentOccurrences[]`. Cada um vai para a lista de pendências
da task 14 — **nenhum é inventado no cliente**, que é a instrução literal da
spec.

- [ ] **Passo 7: build**

```bash
cd web-admin && npm install --no-audit --no-fund && npm run build
```

Esperado: **exit 0**, com os mesmos **três** avisos de budget SCSS do baseline
(`products-stock`, `carriers`, `dashboard`). Um erro de TypeScript aqui é um
payload que não bate; um quarto aviso é regressão.

- [ ] **Passo 8: confirmar que nada aponta mais para a API Java**

```bash
cd /home/elias/programming/fiap/estuda_app
grep -rn "8080\|/api/v1" web-admin/src web-admin/proxy.conf.json
```

Esperado: **nenhuma saída**. Este é o critério de pronto 1 e 2 da spec.

- [ ] **Passo 9: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add web-admin && git diff --staged
git commit -m "$(cat <<'MSG'
feat(web-admin): point the panel at the gateway

The panel spoke to a Java API that spec A deleted: Spring page envelopes,
numeric ids, an accessToken-shaped login and a /dashboard endpoint that
never existed here. Every service is rewritten against the real routes, with
ids as UUIDs where the backend uses them and money and ratings read as the
strings the backend serializes. The dashboard shows what the analytics
service actually has; the fields it does not have are removed and recorded,
not invented in the client.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 14: Documentação, pendências e verificação de costura

Esta task existe por causa da lição 3 do registro da spec A: a revisão por
task não vê as costuras. Nada aqui pertence a uma task anterior.

**Files:**
- Modificar: `CLAUDE.md` (tabela de documentação)
- Modificar: `docs/back-end/microservices.md`
- Modificar: `docs/smoke-test.md`
- Criar: `docs/back-end/partners-inventory-carriers.md`
- Criar: `docs/superpowers/plans/2026-09-08-spec-b-...-execution-record.md`

- [ ] **Passo 1: medir tudo, de novo, do zero**

Nenhum número deste plano é reaproveitado aqui. Medir.

```bash
cd /home/elias/programming/fiap/estuda_app
for s in api-gateway auth-users-service learning-service commerce-service \
         chatbot-service notification-service analytics-service packages/edu-common; do
  printf '%-28s ' "$s"
  (cd "back-end/$s" && uv run pytest -q 2>&1 | tail -1)
done
(cd front-end-flutter && flutter test 2>&1 | tail -1)
(cd front-end-flutter && flutter analyze 2>&1 | tail -3)
(cd web-admin && npm run build 2>&1 | tail -3)
```

Comparar com o baseline da abertura deste plano: gateway 36 → 37,
commerce 367 → o número medido, os outros seis **inalterados**, Flutter
161 → o número medido, `flutter analyze` com os mesmos **6** avisos `info`,
`npm run build` exit 0 com **3** avisos.

**Qualquer serviço não-tocado que mudar de contagem é bug de costura.**
Investigar antes de escrever o registro.

- [ ] **Passo 2: as verificações de costura que nenhuma task possui**

```bash
cd /home/elias/programming/fiap/estuda_app

# 1. Nenhum nome de parceiro em caminho de decisão (backend E frontend).
grep -rni "leroy" back-end/ front-end-flutter/lib/ web-admin/src/ \
  --include='*.py' --include='*.dart' --include='*.ts' \
  | grep -v "back-end/commerce-service/app/seeds/parceiros.py" \
  | grep -v "back-end/commerce-service/tests/" | sort

# 2. Nenhum gerador de código de pagamento no cliente.
grep -rn "_generatePixCode\|_generateBoletoCode\|BR.GOV.BCB.PIX" front-end-flutter/lib/

# 3. Nada mais aponta para a API Java.
grep -rn "8080\|/api/v1" web-admin/src web-admin/proxy.conf.json

# 4. O compose continua válido (NÃO sobe nada).
docker compose -f back-end/docker-compose.yml config --quiet && echo "compose ok"

# 5. Todo model novo está no create_all da suíte.
grep -n "from app.models import" back-end/commerce-service/tests/conftest.py

# 6. As rotas novas estão todas no gateway.
cd back-end/commerce-service && uv run python - <<'PY'
import sys
sys.path.insert(0, "../api-gateway")
from app.main import app
segmentos = {r.path.strip("/").split("/")[0] for r in app.routes if hasattr(r, "methods")}
print(sorted(s for s in segmentos if s and not s.startswith("{")))
PY
cd ../api-gateway && uv run python -c "from app.routing import SERVICE_MAP; print(sorted(SERVICE_MAP))"
```

Toda saída dos itens 1, 2 e 3 tem que ser **vazia**. O item 6 tem que mostrar
que todo primeiro segmento do commerce (`products`, `orders`, `cart`,
`payment-methods`, `picking`, `delivery`, `occurrences`, `admin`, `partners`,
`carriers`, `health`) está no `SERVICE_MAP` — exceto `health`, que é interno.

> **O item 6 roda dois interpretadores diferentes.** Se o `sys.path` acima não
> resolver, medir cada lado num comando separado e comparar as duas listas à
> mão. O que importa é a comparação, não a esperteza do script.

- [ ] **Passo 3: a fronteira do cache de imagem**

Lição literal da spec A: **cada task provou seu trabalho com `pytest` no host,
enquanto o artefato que o usuário opera é uma imagem de container construída.**
O plano da spec B tem a mesma fronteira, e ela é mais afiada aqui porque esta
spec **muda schema**.

Escrever, em `docs/back-end/microservices.md`, um runbook de aplicação da spec
B, na ordem exata, **sem executá-lo**:

```markdown
### Aplicando a spec B a um stack existente

A spec B acrescenta colunas e duas tabelas ao `commerce_db`, e reescreve o
painel Angular. O código no disco não basta: a imagem do `commerce-service`
precisa ser reconstruída, e a migration precisa ser aplicada.

1. `make stack-rebuild` — a imagem carrega o código; sem isto o container
   continua rodando o commerce de antes da spec B, e o `alembic` do passo 3
   não enxerga a revision nova.
2. `make stack-up`
3. `make services-migrate` — aplica `b1a2c3d4e5f6`. É ADITIVA: colunas com
   `server_default` e duas tabelas novas. Nenhum dado é reescrito, e o
   `downgrade` desta revision é real (ao contrário das três reconstruções a
   montante, que levantam por construção).
4. `make services-seed` — cria os fornecedores Edu e Leroy Merlin, o catálogo
   da Leroy, e **adota** os produtos próprios sob "Edu". Idempotente.
   Sem este passo, nenhum produto pertence a parceiro nenhum: a seção de
   parceiros do app fica vazia e todo pedido novo sai sem origem.
5. `cd web-admin && npm install && npm run build`

A ordem 3 antes de 4 é obrigatória: o seed escreve em `fornecedores.origem_*`
e em `estoque.estoque_minimo`, colunas que só existem depois da migration.
```

- [ ] **Passo 4: `docs/back-end/partners-inventory-carriers.md`**

Documento novo, indexado no `CLAUDE.md`, cobrindo: o que `Fornecedor` passou a
ser, como um produto pertence a um parceiro (através do estoque), a regra de
origem única e por que ela vive sob o lock, a trilha de auditoria de estoque e
suas duas portas, a transportadora e sua relação com `Ocorrencia`, os códigos
de pagamento (**e a frase explícita de que não são pagamento real**), e a
tabela de rotas novas.

Acrescentar a linha no `CLAUDE.md`, na tabela de documentação, na seção
**Backend**:

```markdown
| | [docs/back-end/partners-inventory-carriers.md](docs/back-end/partners-inventory-carriers.md) | Spec B: parceiro, origem de expedição, estoque auditado, transportadora, ocorrência de transportadora, códigos de pagamento |
```

- [ ] **Passo 5: `docs/smoke-test.md`**

Acrescentar ao roteiro manual, no perfil de admin e no de aluno:
- admin cria parceiro com origem, cria produto sob ele, ajusta estoque com
  motivo e confere a trilha;
- admin cadastra transportadora e abre/fecha uma ocorrência de dano;
- aluno vê a seção "Parceiros", põe um item da Leroy no carrinho, tenta pôr um
  item do Edu e **lê a mensagem de 409**;
- aluno fecha o pedido com PIX e confere que o código veio do servidor;
- admin desativa a Leroy no painel e confere que a seção do app esvazia
  **sem recompilar nada**.

E, nas lacunas conhecidas que não são bug, as pendências do passo 6.

- [ ] **Passo 6: registrar as pendências, não escondê-las**

Lista para o registro de execução e para o `smoke-test.md`:

1. `web-admin` não tem suíte de teste; a verificação é `npm run build` (D11).
2. `GET /admin/inventory` não tem `search` nem `lowStock`; o painel filtra no
   cliente sobre `limit=100`.
3. A página de estoque junta produto e estoque no cliente por falta de rota
   agregada.
4. O painel não faz refresh de token; a sessão expira com o access token.
5. O dashboard perdeu os quinze campos que o backend não tem (lista em D10).
6. `estoque_ajustes` não tem rota de leitura global — só por produto.
7. Os seis produtos próprios ficam com `sku` vazio até alguém editá-los; o
   índice único é parcial justamente para isso.
8. A suíte continua montando o schema com `create_all` e não roda alembic; a
   revision da spec B é a única com prova de aplicação registrada (task 1).

- [ ] **Passo 7: escrever o registro de execução**

`docs/superpowers/plans/2026-09-08-spec-b-...-execution-record.md`, no molde
do da spec A: o que foi entregue por task com os hashes, a tabela de contagem
antes/depois **medida no passo 1**, cada decisão tomada durante a execução
onde o plano estava errado, e o que ficou como dívida.

- [ ] **Passo 8: commit**

```bash
cd /home/elias/programming/fiap/estuda_app && git add CLAUDE.md docs && git diff --staged
git commit -m "$(cat <<'MSG'
docs: record what spec B delivered and what it left open

The seam checks no single task owned, the runbook for applying an additive
schema change to a running stack, and the pendencies the delivery carries on
purpose — the panel's missing test suite, the client-side filters standing in
for server ones, and the dashboard fields the analytics service does not
have.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Auto-revisão do plano contra a spec

Feita depois de escrever o plano inteiro, relendo a spec com olhos frescos.

### 1. Cobertura da spec

| Item da spec | Task |
|---|---|
| 1. `Fornecedor` como parceiro, CRUD `/partners`, paginado | 1, 2 |
| 2. Estoque com auditoria, `POST /products/{id}/stock-adjustments` | 1, 3 |
| 3. Transportadora, CRUD `/carriers`, status como enum | 1, 4 |
| 4. Catálogo de parceiro no app, `partner_id`, seção "Parceiros" | 7, 12 |
| 5. Seed da Leroy Merlin | 11 |
| 6. Código PIX no backend | 10, 12 |
| 7. `web-admin` no gateway | 2 (roteamento), 13 |
| Origem de expedição em `Fornecedor` | 1 |
| Origem única no carrinho, 409, sob lock | 8 |
| Ocorrências: um modelo, não dois | 1, 5 |
| Origem gravada no pedido | 1, 9 |
| Duas entradas no `SERVICE_MAP` | 2 |
| Mock do PIX eliminado do `checkout_screen.dart` | 12 |
| Testes de erro: 409, 422, lista vazia, 502 | 8, 3, 7, 10 |
| Teste: nenhuma string `leroy` em decisão | 11, 14 |
| Teste: seed idempotente em duas passadas | 11 |
| Teste: widget de parceiros vazio/um/erro | 12 |
| Teste: paridade do PIX | 10 |

**Nenhuma lacuna.** Dois itens da spec ganharam escopo por medição, com
decisão do usuário registrada: o CRUD de produto (D1) e o boleto (D3).

### 2. Critérios de pronto da spec

1. *Nenhum processo Java necessário* — tasks 4, 5, 13 e o grep do passo 8 da 13.
2. *`web-admin` opera produtos, estoque, transportadoras e ocorrências pelo
   gateway* — tasks 6, 3, 4, 5, 13.
3. *Seção de parceiros no app, respondendo ao flag de ativo* — tasks 7, 12.
4. *Pedido com a origem correta* — task 9.
5. *`checkout_screen.dart` não gera mais PIX* — task 12, passo 8.
6. *`make services-test`, `make front-analyze`, `make front-test` verdes* —
   **divergência deliberada**: `make services-test` e `make services-lint` são
   proibidos neste ambiente (reescrevem `uv.lock`). O equivalente é
   `uv run pytest` serviço a serviço, e é isso que a task 14 mede.
   `make front-analyze` sai com código 1 por seis avisos `info`
   pré-existentes — o critério é "os mesmos seis", não "exit 0".

### 3. Consistência de tipos entre tasks

- `Fornecedor.origem_lat` é `Numeric(9, 6)` na task 1, `Decimal` no schema da
  task 2, serializado como string de 6 casas, e lido como `String` no
  `Partner.originLabel`... **não**: `originLabel` é `origem_rotulo`, texto. As
  coordenadas não sobem para o app nesta spec (a spec C as usa pelo pedido).
  Consistente.
- `EstoqueAjuste.autor_id` é `UUID` no model (task 1), `uuid.UUID` no schema
  (task 3), e o router o preenche com `uuid.UUID(user["sub"])`. Consistente.
- `aplicar_ajuste` devolve `tuple[Estoque, EstoqueAjuste]` na task 3 e é
  chamada como tal em `admin.py` (`estoque, _ =`) e em `produtos.py`
  (`_, ajuste =`). Consistente.
- `_fornecedor_do_produto` nasce em `services/carrinho.py` (task 8); a task 9
  **não** a importa — refaz a travessia com um `select` em lote, porque
  precisa do mapa produto→fornecedor para todos os itens, não de um só.
  Deliberado, e escrito.
- `CarrierStatus` é enum de `app.models.transportadora` e é usado no schema da
  task 4 e no serviço. `Carrier.status` guarda `.value` (string). Os três
  pontos de escrita fazem `.value` explicitamente. Consistente.
- `gerar_codigo_pagamento` devolve `str | None`; `PagamentoConfirmadoOut.payment_code`
  é `str | None`; `CheckoutService.confirmPayment` devolve `String?`.
  Consistente ponta a ponta.

### 4. Contradições entre prosa e código

Lição 2 do registro da spec A. Duas encontradas na própria escrita e já
corrigidas no texto acima:

- A task 1 assere `cols["sku"].unique is True` no passo 1, mas o passo 3 usa
  índice único **parcial**, com o qual `Column.unique` fica `None`. A
  asserção corrigida está escrita na task, junto com o motivo.
- A task 3 escrevia `delta: int = Field(ne=0)`, e `ne` não existe no
  Pydantic. O `field_validator` substituto está escrito na task.

Uma terceira, que o executor precisa vigiar: a task 8 promete no texto que a
regra roda "sob o mesmo lock", e o bloco de código a coloca **depois** do
`select(Cart.id)...with_for_update()`. Ler as duas coisas juntas antes de
colar — se o bloco for parar acima daquela linha, a prosa continua verdadeira
e o código deixa de ser.
