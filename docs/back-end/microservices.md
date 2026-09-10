# Microserviços — arquitetura do backend

> **Escopo deste documento:** descreve **o que existe hoje**, depois do corte
> da spec A (2026-09-07), que apagou `back-end/legacy/`. Onde algo ainda não
> existe, está marcado com a fase em que chega. O gateway é o backend que o
> app Flutter consome hoje — veja [start-here.md](start-here.md) para o
> registro histórico do monolito que ele substituiu.

O plano completo da migração está em
`docs/superpowers/specs/2026-08-02-microservices-migration-design.md`.

---

## 1. Topologia

A fase 1 colocou os sete serviços novos **ao lado** do monolito, não no lugar
dele. A spec A (2026-09-07) completou o corte: apagou `back-end/legacy/` e
apontou o app para o gateway. Hoje só a frota nova sobe, no mesmo projeto
Docker Compose (`edu`), compartilhando uma única instância de Postgres, Redis,
RabbitMQ e MinIO.

```
                     Flutter (hoje)
                           │
                           ▼
              ┌────────────────────────┐
              │  api-gateway           │  :8100   ← o app fala com este
              └───────────┬────────────┘
                          │
   ┌──────────┬───────────┼───────────┬──────────┬──────────┐
   ▼          ▼           ▼           ▼          ▼          ▼
 auth-      learning-  commerce-   chatbot-  notification- analytics-
 users       service    service     service    service      service
 :8101       :8102      :8103       :8104      :8105        :8106
   │           │          │                       │            │
   └───────────┴──────────┴───── RabbitMQ ────────┴────────────┘
                              (exchange edu.events)
```

O gateway é **burro de propósito**: ele decide apenas *para onde* mandar a
requisição. Autenticação e autorização ficam 100% no serviço de destino — cada
um valida o JWT sozinho, com o mesmo `JWT_SECRET`
(`back-end/api-gateway/app/routing.py`).

---

## 2. Serviços

| Serviço | Porta host | Banco | Responsabilidade |
|---|---|---|---|
| `api-gateway` | **8100** | — | Proxy reverso por prefixo de path sob `/api`. Sem banco, sem eventos |
| `auth-users-service` | **8101** | `auth_db` | Registro, login, refresh, reset de senha por OTP, perfil e endereços |
| `learning-service` | **8102** | `learning_db` | Matérias, temas, subtemas, diagnóstico adaptativo, SM-2, embeddings, recomendação semântica |
| `commerce-service` | **8103** | `commerce_db` | Catálogo, pedidos, máquina de 10 estados, separação, entrega, ocorrências, admin de estoque, carregamento/posição de entrega, scheduler próprio (`app/scheduler.py`, `AsyncIOScheduler` no `lifespan`, padrão do `learning-service`) |
| `chatbot-service` | **8104** | `chatbot_db` | RAG (FAISS + Groq): perguntas livres e explicação de questão; conversa de suporte (`support`), portada do legacy na fase 2d |
| `notification-service` | **8105** | `notification_db` | Notificações in-app e registro de device token, alimentado por eventos |
| `analytics-service` | **8106** | `analytics_db` | Event log, métricas agregadas, detecção de anomalias, resumo executivo por LLM |

A porta **interna** de todo container é `8000` — só o mapeamento para o host
muda. As URLs que o gateway usa entre containers são
`http://<serviço>:8000`, não as portas 81xx.

### Infra compartilhada

| Componente | Porta host | Porta interna |
|---|---|---|
| PostgreSQL 17.4 | 5433 | 5432 |
| Redis 8.2.1 | 6380 | 6379 |
| RabbitMQ 4.2.3 | 5673 (AMQP), 15673 (painel) | 5672, 15672 |
| MinIO | 9000 (API), 9001 (console) | 9000, 9001 |

Um Postgres, vários bancos: `edu` (órfão — era do legacy, nenhum serviço novo
o usa, mas o Postgres continua criando-o porque `POSTGRES_DB=edu` segue no
`.env`) mais `auth_db`, `learning_db`, `commerce_db`, `chatbot_db`,
`notification_db` e `analytics_db`, cada um com um `*_test` correspondente
para as suítes. **Só o `api-gateway` não tem banco** — o `DATABASE_URL` dele é
explicitamente zerado no compose para que a credencial do banco `edu` não
fique no ambiente de um container que não deveria alcançá-la.

O `chatbot-service` estava nessa mesma frase até a fase 2d e **saiu dela**: o
módulo `support` deu banco a ele, e `back-end/docker-compose.yml:246-247`
preenche `DATABASE_URL` e `DATABASE_URL_TEST` com `chatbot_db` e `chatbot_test`
— não mais com string vazia. A razão do zeramento continua valendo, e continua
escrita no próprio compose (`:241-245`): ela agora vale só para o gateway, que
não fala com banco nenhum.

---

## 3. Mapa de rotas do gateway

Tudo que chega em `/api/<prefixo>/...` é resolvido pelo primeiro segmento do
path contra o `SERVICE_MAP` de `back-end/api-gateway/app/routing.py`. Prefixo
não mapeado devolve 404 com uma mensagem explícita do próprio gateway; prefixo
mapeado é repassado, e aí o 404 (se houver) vem do serviço de destino.

> Todos os módulos foram portados. O monolito foi apagado na spec A
> (2026-09-07); esta tabela deixou de ser um mapa de migração e passou a ser o
> índice de qual serviço atende cada prefixo.

| Prefixo | Serviço | Estado hoje |
|---|---|---|
| `auth` | auth-users-service | OK |
| `users` | auth-users-service | OK |
| `subjects` | learning-service | OK |
| `topics` | learning-service | OK |
| `subtopics` | learning-service | OK |
| `diagnostic` | learning-service | OK |
| `recommendations` | learning-service | OK |
| `reviews` | learning-service | OK |
| `products` | commerce-service | OK — reconciliado com o Flutter na fase 2b |
| `orders` | commerce-service | OK — ciclo completo, reconciliado na fase 2c |
| `cart` | commerce-service | OK — servido por `commerce-service` |
| `payment-methods` | commerce-service | OK — servido por `commerce-service` |
| `picking` | commerce-service | OK |
| `delivery` | commerce-service | OK |
| `occurrences` | commerce-service | OK |
| `partners` | commerce-service | OK — spec B |
| `carriers` | commerce-service | OK — spec B |
| `shipments` | commerce-service | OK — spec C (carregamento: login do entregador por código, `/shipments/{id}/orders`) |
| `admin` | commerce-service | OK |
| `notifications` | notification-service | OK |
| `analytics` | analytics-service | OK |
| `chat` | chatbot-service | OK |
| `support` | chatbot-service | OK — servido por `chatbot-service` |

### O que "404" quer dizer aqui

**Não sobrou nenhum prefixo mapeado sem rota no serviço de destino.** `support`
era o último, e saiu dessa condição na fase 2d:
`chatbot-service/app/routers/suporte.py` declara `APIRouter(prefix="/support")`
e `app/main.py` o inclui. `cart` e `payment-methods` estavam na mesma lista até
a fase 2b — hoje são servidos por `commerce-service/app/routers/carrinho.py` e
`.../pagamento.py` —, e `orders` até a 2c.

Medido serviço a serviço nesta árvore, importando cada app em processo e
imprimindo o **primeiro segmento** de cada path do OpenAPI dele. Use o OpenAPI,
não `app.routes`: no FastAPI 0.141.1 cada `include_router` vira uma única
entrada `_IncludedRouter` com `path=None`, então iterar `app.routes` esconde
exatamente os routers que interessam — `/support` e `/notifications` somem, e a
medição diz "não há rota" sobre um serviço que tem rota.

Saída dos seis comandos, um por serviço, colada como veio:

```
auth-users-service -> ['auth', 'health', 'users']
learning-service -> ['diagnostic', 'health', 'recommendations', 'reviews', 'subjects', 'subtopics', 'topics']
commerce-service -> ['admin', 'carriers', 'cart', 'delivery', 'health', 'occurrences', 'orders', 'partners', 'payment-methods', 'picking', 'products', 'shipments']
chatbot-service -> ['chat', 'health', 'support']
notification-service -> ['health', 'notifications']
analytics-service -> ['analytics', 'health']
```

Os 23 prefixos do `SERVICE_MAP` aparecem nessa lista (eram 20 até a spec B
acrescentar `partners` e `carriers`, e 22 até a spec C acrescentar
`shipments`). O 404 do gateway continua existindo, mas hoje ele é **sempre**
sobre prefixo não mapeado — nunca sobre prefixo mapeado e vazio. `addresses`
é o exemplo vivo disso.

`addresses` **não está na tabela acima porque não está no mapa**. A entrada
existia e foi removida pelo commit `42bc7ce` ("refactor(gateway): drop the dead
addresses entry from SERVICE_MAP"), ancestral do HEAD desta branch:
`grep -c addresses back-end/api-gateway/app/routing.py` devolve `0`. Ninguém
serve `/addresses` — o auth-users-service monta os endereços sob
**`/auth/addresses`** (`APIRouter(prefix="/auth/addresses")`, em
`back-end/auth-users-service/app/routers/addresses.py:12`), que roteia pelo
prefixo `auth`; o legacy fazia o mesmo antes de ser apagado na spec A
(`app/modules/addresses/routes.py:14` do monolito, caminho que não existe mais
nesta árvore). O app Flutter também chama `/auth/addresses`
(`front-end-flutter/lib/features/profile/data/addresses_api.dart:33`).
Um `/api/addresses/...` que chegue hoje cai no 404 do próprio gateway, e é isso
que `api-gateway/tests/test_routing.py:49` trava —
`resolve_destination("addresses/123") is None`, com o caso irmão
`resolve_destination("auth/addresses/123")` provando que o caminho real
continua resolvendo.

### `products` e `orders`: as divergências da fase 1 foram fechadas

Esta seção descrevia um estado que **não existe mais**. Na fase 1, `products` e
`orders` respondiam com a forma errada — o problema era forma, não rota, e por
isso requisições que antes davam 404 limpo passaram a dar 405, 422 ou 200
errado. As fases 2b e 2c reconciliaram os dois campo a campo contra o código do
Flutter.

O que a fase 1 registrava, e o que está no lugar hoje (medido nesta árvore):

| Afirmação da fase 1 | Hoje |
|---|---|
| `GET /products` devolve array puro; o app lê `{"items": [...]}` | Devolve `ProductList`, que tem `items:` — a forma que `product_service.dart` lê |
| `id` inteiro onde o app faz `as String` | `ProductOut.id` é `uuid.UUID`, JSON string |
| `GET /orders` devolve 405; a listagem está em `/orders/mine` | `GET /orders` existe e devolve array puro paginado; `/orders/mine` não existe mais |
| `POST /orders` devolve 422 porque exige outro corpo | Aceita `{payment_method, address_id}` e também corpo vazio (`OrderCreateIn`, com os dois campos opcionais) |
| `GET /products/{id}/reviews` não existe | Existe (`routers/produtos.py`) |
| `GET /orders/{id}/route` não existe | Existe (`routers/rastreio.py::rota_pedido`) |

A reconciliação completa — contagem portada, asserções adaptadas e as
divergências deliberadas que sobraram de propósito — está em
[`commerce-parity.md`](commerce-parity.md), seção 9 para o bloco C.

**Consequência para a fase 4:** o que falta agora não é a reconciliação de
forma, e sim rodar a frota junto — migrations, seed e os consumidores de
evento. A dívida aberta está em [`phase-2-debt.md`](phase-2-debt.md).

---

## 4. Regra de contrato

A regra tem **dois níveis**, e isso é intencional.

**Paths em inglês na frota inteira.** Rotas expostas ficam em inglês
(`/subjects`, `/diagnostic`, `/picking`, `/delivery`, `/occurrences`), mesmo
nos serviços importados, cujos models, services e nomes de função seguem em
português. Os routers carregam uma camada explícita de tradução — é uma
anti-corruption layer deliberada.

**Campos de schema em inglês só onde há cliente.**

| Serviço | Paths | Campos de schema |
|---|---|---|
| `notification-service` | inglês | **inglês** — o Flutter consome hoje (`title`, `body`, `created_at`, `read_at`) |
| `learning-service`, `commerce-service`, `analytics-service` | inglês | **português** — sem cliente (`tema_id`, `dominio_tema`, `produto_id`, `quantidade`) |

Traduzir campo de schema de serviço sem cliente dessincronizaria o consumidor
do seu produtor: o analytics-service lê `tema_id`/`dominio_tema` do evento que
o learning-service publica com esses nomes. Renomear só do lado da resposta
criaria duas grafias para o mesmo dado.

Isso é dívida aberta hoje: o Flutter já fala com o gateway, e todo campo que
ele consumir precisa estar em inglês. O corte acima **empurra** a tradução
para quando existir um cliente que a justifique — não a cancela.

---

## 5. Como subir o stack

Tudo a partir da raiz do repositório.

> **Depois desta fase, reconstrua as imagens antes do primeiro `stack-up`.**
> `stack-up` roda `docker compose up -d`, sem `--build`, e nenhum serviço
> monta o código-fonte por bind mount — a imagem carrega só o que foi
> copiado no `docker build`. Numa máquina cujas imagens são anteriores à
> spec A, cinco serviços mudam de comportamento sem que o rebuild aconteça:
> `auth-users-service` (seed de contas de demo, módulo novo),
> `commerce-service` (lock consultivo no seed do catálogo) e
> `notification-service` (título curto do pedido, dead-letter exchange) por
> código próprio; `learning-service` e `analytics-service` porque redeclaram
> fila com `x-dead-letter-exchange` através do `EventConsumer` do
> `edu-common`. As sete imagens do stack vendorizam `edu-common` (`COPY
> packages/edu-common` no Dockerfile de cada uma), então o rebuild vale para
> todas, não só essas cinco. Sem ele:
>
> - `make services-seed-demo` estoura com `ModuleNotFoundError: No module
>   named 'app.seeds'` — o módulo não está na imagem em cache.
> - `make services-seed` roda o seed **antigo**, sem o lock consultivo — a
>   corrida fica reaberta bem na primeira execução real do alvo.
> - A dead-letter exchange fica inerte: os consumidores continuam
>   declarando fila sem `arguments`.
> - `idCurto` fica inerte: o título do push mantém o UUID de 36 caracteres.
>
> ```bash
> make stack-rebuild     # docker compose build — reconstrói as sete imagens
> ```
>
> Um clone limpo, sem imagem nenhuma ainda, não precisa disso: o primeiro
> `stack-up` já builda a partir do zero.

```bash
make stack-up          # sobe infra + gateway + os 6 serviços
```

Numa base **já existente** (o caso normal em máquina de dev), os bancos por
serviço e as migrations **não são aplicados sozinhos**. O hook `initdb.d` do
Postgres só dispara em volume novo, então rode também:

```bash
make services-dbs      # cria os bancos por serviço no volume existente (idempotente)
make services-migrate  # aplica alembic upgrade head em cada serviço com banco
make services-seed     # popula o catálogo do commerce (baixa as fotos no MinIO)
```

Em um volume totalmente novo, `make stack-up` sozinho já cria os bancos pelo
`initdb.d` — mas rodar os dois primeiros alvos depois não faz mal: ambos são
idempotentes. Isso deixou de ser teoria no portão do bloco D: depois de um
`docker compose down -v` autorizado (com `pg_dumpall` conferido antes), o
volume virgem subiu com `chatbot_db` e `chatbot_test` já criados, **sem ninguém
rodar `make services-dbs`**. É a prova da armadilha de mount que a §11 descreve
— o script novo estava de fato montado.

> **Antes de `make services-migrate`, reconstrua a imagem do serviço que ganhou
> `alembic/` nesta fase.** Veja a §11 — `stack-up` não passa `--build`, e o alvo
> roda o Alembic **dentro do container**, onde uma imagem em cache não tem a
> árvore de migrations.

`make services-seed` é o terceiro alvo desse fluxo e **nunca foi executado** —
foi escrito na fase 2b, e no `commerce_db` de dev a tabela `products` nem
existe ainda (`to_regclass('public.products')` devolve vazio). A idempotência
**sequencial** dele é medida — `seed_products` rodado duas vezes na mesma
sessão insere o catálogo e depois insere zero
(`tests/test_products_seed.py::TestProductsSeed::test_is_idempotent`, verde).
A idempotência **concorrente** — duas execuções simultâneas inserindo o
catálogo em duplicidade, porque `products.name` tem índice sem `unique` — era
a dívida de verdade e foi fechada na spec A: `seed_products` agora abre a
transação com `pg_advisory_xact_lock`
(`back-end/commerce-service/app/seeds/products.py:245-251,271-273`), coberto
por `tests/test_products_seed.py::test_concurrent_seeds_do_not_duplicate`.

Conferindo que subiu:

```bash
curl -s localhost:8100/health   # gateway
curl -s localhost:8101/health   # ... até 8106
```

Outros alvos:

```bash
make stack-down                     # derruba o stack inteiro
make stack-logs SVC=analytics-service   # logs de um serviço (default: api-gateway)
make services-sync                  # uv sync em cada projeto, para o IDE
```

### Runbook de corte desta fase (broker e imagens antigos)

Três passos deste corte são do usuário — apagar as filas antigas do
RabbitMQ, rodar os dois seeds, arquivar o repositório 2 — e a ordem entre os
dois primeiros é **load-bearing**: invertê-la descarta os dois eventos que o
seed de demonstração existe para publicar, sem erro visível, e também derruba
`make services-migrate` um passo antes disso.

Numa máquina cujo broker e imagens são anteriores à spec A, a sequência
completa é:

```bash
make stack-rebuild                                     # 1. reconstrói as sete imagens
make stack-up                                          # 2. sobe infra + gateway + serviços
make services-dbs                                      # 3. cria os bancos que faltarem

# 4. apague as sete filas antigas — veja a lista completa e o comando na
#    §11, "Uma fila declarada antes da DLX não aceita a nova declaração"

docker compose -f back-end/docker-compose.yml restart \
  notification-service learning-service analytics-service   # 5. reinicia os três consumidores

make services-migrate                                  # 6. aplica alembic upgrade head
make services-seed                                     # 7. catálogo do commerce
make services-seed-demo DEMO_ACCOUNTS_PASSWORD='...'   # 8. as quatro contas fixas
```

**Os passos 4 e 5 têm que vir antes do 6 e do 8, nessa ordem.**
`notification-service`, `learning-service` e `analytics-service` sobem com
`start_consumer()` dentro do `lifespan`, sem `except`
(`notification-service/app/main.py:10-13`,
`learning-service/app/main.py:12-19`,
`analytics-service/app/main.py:10-13`): redeclarar uma fila antiga (sem
`arguments`) com `x-dead-letter-exchange` novo é fatal —
`PRECONDITION_FAILED - inequivalent arg 'x-dead-letter-exchange'` — e o
serviço não sobe até a fila ser apagada, entrando em loop de restart
(`restart: unless-stopped`).

Isso morde o passo 6 antes mesmo de chegar no 8. `DB_SERVICES`
(`Makefile:86`) lista `learning-service` em **segundo** lugar, e o loop de
`services-migrate` (`Makefile:107-110`) tem `|| exit 1`: o primeiro `docker
compose exec` que cai num container em restart loop aborta o alvo inteiro, e
`commerce-service`, `notification-service`, `analytics-service` e
`chatbot-service` nunca chegam a ser migrados. O operador vê um erro de
Docker/Alembic nomeando `learning-service`, sem nada que explique o motivo —
a mesma classe de falha de ordem confusa que este runbook existe para
eliminar, só que um passo antes. `auth-users-service` só **publica**, não tem
fila: ele sobe mesmo com os três consumidores fora do ar, e `make
services-seed-demo` **roda** normalmente nesse estado.

Se o passo 8 rodar com o 4/5 pendente, `student.created` e `staff.created`
são publicados e roteiam para as filas antigas (`learning.student_created`,
`analytics.event_log`), que ninguém está consumindo — apagar essas filas
depois, para destravar os três serviços, destrói as mensagens que estavam
nelas. O seed é idempotente (`demo_accounts.py:94-97`): uma segunda passada
devolve 0 contas criadas e **não republica nada**. Recuperar significa apagar
à mão as quatro linhas `@demo.edu` de `auth_db.users` e rodar `make
services-seed-demo` de novo, dessa vez com os passos 4 e 5 já feitos.

Um broker que nunca rodou a versão anterior (stack novo, volume novo) não
tem passo 4/5: as filas já nascem com `x-dead-letter-exchange` e o
`PRECONDITION_FAILED` nunca aparece.

### Aplicando a spec B a um stack existente

A spec B acrescenta colunas e duas tabelas ao `commerce_db`, e reescreve o
painel Angular. **O código no disco não basta**: a imagem do
`commerce-service` precisa ser reconstruída, e a migration precisa ser
aplicada. Esta é a mesma fronteira que a spec A documentou na §11 — cada task
provou o próprio trabalho com `pytest` no host, enquanto o artefato que o
usuário opera é uma imagem de container construída —, e aqui ela é mais
afiada, porque esta spec **muda schema**.

Na ordem exata:

```bash
make stack-rebuild      # 1. a imagem carrega o código
make stack-up           # 2.
make services-migrate   # 3. aplica b1a2c3d4e5f6
make services-seed      # 4. parceiros, catálogo do parceiro e adoção
cd web-admin && npm install && npm run build   # 5.
```

1. **`make stack-rebuild`** — sem isto o container continua rodando o commerce
   de antes da spec B, e o `alembic` do passo 3 não enxerga a revision nova.
2. **`make stack-up`**.
3. **`make services-migrate`** — aplica `b1a2c3d4e5f6`. É **aditiva**: colunas
   com `server_default` e duas tabelas novas (`estoque_ajustes`, `carriers`).
   Nenhum dado é reescrito, e o `downgrade` desta revision é real (ao
   contrário das três reconstruções a montante, que levantam por construção).
4. **`make services-seed`** — cria os dois fornecedores (o próprio e o
   parceiro externo), o catálogo do parceiro, e **adota** os produtos próprios
   sob o fornecedor próprio. Idempotente, inclusive no laço de adoção. Sem
   este passo, **nenhum produto pertence a parceiro nenhum**: a seção de
   parceiros do app fica vazia e todo pedido novo sai sem origem.
5. **`cd web-admin && npm install && npm run build`**.

**A ordem 3 antes de 4 é obrigatória:** o seed escreve em
`fornecedores.origem_*` e em `estoque.estoque_minimo`, colunas que só existem
depois da migration.

O detalhe do que cada peça faz está em
[`partners-inventory-carriers.md`](partners-inventory-carriers.md).

---

## 6. Como rodar os testes

```bash
make services-env      # num clone limpo, primeiro: cria cada .env a partir do .env.example
make services-test     # roda a suíte dos 8 projetos (edu-common + 7 serviços) no host
make services-lint     # ruff check em cada um
```

**`make services-env` é obrigatório num clone limpo.** Rodando no host, cada
serviço lê o `.env` do próprio diretório (dentro do compose é diferente: o
`docker-compose.yml` injeta tudo por `environment`). Como os campos
obrigatórios não têm default, sem esse passo o `pytest` estoura **no import**,
com um `ValidationError` do pydantic — não numa assertion, o que torna o
sintoma confuso para quem clonou o repositório agora. O alvo copia de cada
`.env.example` e **nunca sobrescreve** um `.env` existente, então é seguro
rodar de novo a qualquer momento.

> **O reverso disso morde quem já tinha o repositório clonado.** "Nunca
> sobrescreve" significa que um `.env` antigo, sem as variáveis que a fase 2d
> acrescentou, sobrevive ao alvo — e `make services-test` estoura no import.
> Veja a §11.

Os testes rodam **no host**, não dentro dos containers, e usam os bancos
`*_test` pelas portas publicadas — o stack precisa estar de pé. Cada projeto é
um projeto `uv` independente, com o seu próprio `pyproject.toml`, `alembic/` e
`tests/`.

Estado medido nesta árvore, no fim do bloco D da fase 2, com
`uv run pytest -q --collect-only` em cada projeto (coleta, não execução — não
toca em banco):

| Projeto | Testes |
|---|---|
| `packages/edu-common` | 59 |
| `api-gateway` | 36 |
| `auth-users-service` | 65 |
| `learning-service` | 78 |
| `commerce-service` | 366 |
| `chatbot-service` | 37 |
| `notification-service` | 31 |
| `analytics-service` | 34 |
| **Total** | **706** |

No fechamento da fase 1 esta tabela somava **322**; os blocos B, C e D mais que
dobraram a suíte, e o `commerce-service` sozinho respondeu pela maior parte
disso (69 → 366). A soma de 706 confere com o total que o portão do bloco D
mediu rodando as oito suítes de verdade.

A suíte do legacy foi o critério de aceite da paridade da fase 2. Ela foi
apagada junto com o monolito na spec A (2026-09-07); o resultado da medição
contra ela ficou registrado em [`commerce-parity.md`](commerce-parity.md) e
[`phase-2-debt.md`](phase-2-debt.md).

---

## 7. `edu-common`

Pacote compartilhado em `back-end/packages/edu-common`, consumido pelos
serviços como path dependency editável via `[tool.uv.sources]`. **Não é um uv
workspace**: quando o legacy ainda existia, o `auth-users-service` fixava uma
versão de `bcrypt` incompatível com a dele, e num workspace o lock seria
único. A decisão não foi revisitada depois do corte.

Ele carrega **só o que é sensível a segurança e a contrato de evento**:

| Módulo | O que tem |
|---|---|
| `security.py` | Hash de senha (bcrypt direto, sem passlib) e encode/decode de JWT |
| `deps.py` | Dependências FastAPI de autenticação (`build_auth_deps`) |
| `events.py` | `EventPublisher` e `EventConsumer` do RabbitMQ |

Seis dos sete serviços importam `edu_common`. O `api-gateway` **não** — ele não
valida token nem toca no barramento.

### Por que `config.py` e `database.py` seguem duplicados

Porque compartilhá-los acoplaria os serviços sem ganho real. Cada serviço tem
o seu próprio conjunto de variáveis de ambiente, o seu próprio banco e o seu
próprio ciclo de migrations; a "duplicação" são poucas linhas de boilerplate
que mantêm cada serviço autônomo e removível.

O critério para entrar no `edu-common` é estreito de propósito: **contrato
compartilhado de verdade**. Um JWT emitido por um serviço é validado por
todos os outros, e um evento publicado por um é consumido por outro — divergir
nessas duas coisas é falha de segurança ou de integração. Um `Settings` que
diverge entre serviços não é falha nenhuma.

---

## 8. Eventos

Coreografia via RabbitMQ, no exchange **`edu.events`**. Dez routing keys em
produção hoje:

`student.created`, `staff.created`, `diagnostic.completed`,
`revision.scheduled`, `order.created`, `order.status_changed`,
`order.stock_issue`, `order.delivery_delayed`, `order.occurrence_resolved`,
`shipment.created` (spec C — carrega a senha do carregamento em claro, só o
`notification-service` escuta, e nenhum log a imprime;
[`order-flow.md`](order-flow.md) §2 e §5).

Onze filas, todas ligadas ao `edu.events`:

| Fila | Serviço | Escuta |
|---|---|---|
| `analytics.event_log` | analytics-service | as nove anteriores à spec C — **não** `shipment.created`; o `analytics-service` não foi tocado por esta spec |
| `notification.diagnostic_completed` | notification-service | `diagnostic.completed` |
| `notification.revision_scheduled` | notification-service | `revision.scheduled` |
| `notification.order_status_changed` | notification-service | `order.status_changed` |
| `notification.stock_issue` | notification-service | `order.stock_issue` |
| `notification.delivery_delayed` | notification-service | `order.delivery_delayed` |
| `notification.staff_created` | notification-service | `staff.created` — spec C, alimenta o registro de destinatário por papel (`order-flow.md` §5) |
| `notification.order_created` | notification-service | `order.created` — spec C |
| `notification.occurrence_resolved` | notification-service | `order.occurrence_resolved` — spec C |
| `notification.shipment_created` | notification-service | `shipment.created` — spec C, e-mail à transportadora |
| `learning.student_created` | learning-service | `student.created` |

O `commerce-service` só **publica** — não tem fila.

Para inspecionar ao vivo:

```bash
docker compose -f back-end/docker-compose.yml exec rabbitmq \
  rabbitmqctl list_queues name messages consumers
```

> **Fase 3 — idempotência dos consumidores.** Os handlers inserem
> incondicionalmente ao receber um evento, sem chave de deduplicação. O
> RabbitMQ entrega *pelo menos uma vez*: uma queda entre o commit e o ack
> reentrega a mensagem e duplica a notificação do aluno. A correção não é local
> a nenhum serviço — o `EventPublisher` ainda não carimba id de mensagem, então
> não há nada estável para deduplicar. Fica para a fase 3, junto com o Redis.

---

## 9. Portas — por que estas

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

---

## 10. Variáveis de ambiente e segredos

**Nenhum `.env` vai para o repositório. O `.env.example` é o contrato.**

Existe **um** `.env`, em `back-end/.env`, ao lado do `docker-compose.yml`.
Além dele, cada serviço tem o seu próprio `.env.example` para quem quiser
rodar o serviço direto no host, fora do compose.

```bash
cp back-end/.env.example back-end/.env    # e preencha os valores
```

Regras:

- Todo `.env` é git-ignored. Nenhum foi commitado em nenhum ponto da fase 1.
- O `.env.example` lista **toda** variável obrigatória, com valor de exemplo e
  **nunca** com valor real. Settings com campo obrigatório sem default fazem
  `uv run pytest` estourar no import de um clone limpo — sem o `.env.example`
  ninguém descobre o que falta.
- Segredos que não são texto (a service account do Firebase) ficam em
  `secrets/`, fora do build context, montados read-only. Nunca vão para dentro
  da imagem.

---

## 11. Armadilhas conhecidas

Cinco coisas que mordem e não são óbvias. Duas delas chegaram com a fase
2d e valem para **quem já tinha o repositório ou as imagens**, não para um
clone limpo — por isso passam despercebidas em CI e mordem só na máquina de
quem estava trabalhando aqui antes.

### `make stack-up` num volume existente não cria os bancos

O hook `initdb.d` do Postgres só roda em volume **novo**. Num volume que já
existe — o caso de qualquer máquina que já rodava o legacy — os bancos por
serviço e as migrations não aparecem sozinhos. Rode `make services-dbs` e
`make services-migrate` depois do `stack-up`. Veja a §5.

Detalhe relacionado: o compose monta o `initdb.d` **script a script**, não a
pasta inteira (não dá para montar duas pastas no mesmo destino, e o compose do
legacy que exigia isso não existe mais desde a spec A). Um script novo em
`./postgres/initdb.d/` vira um no-op silencioso aqui até que a linha de mount
dele seja acrescentada.

### `JWT_SECRET` ausente trava até o `down`

O compose usa `${JWT_SECRET:?...}`, que é uma falha **alta e proposital**: sem
o segredo, nenhum serviço sobe achando que está seguro. O canto ruim é que a
interpolação roda em toda subcomando do compose — inclusive `down`. Se o
`JWT_SECRET` sumir do `back-end/.env` com o stack de pé, `docker compose down`
falha e os containers ficam presos.

Saída: restaure a variável no `.env`, ou passe-a inline só para conseguir
derrubar.

```bash
JWT_SECRET=qualquer-coisa docker compose down
```

O trade-off é deliberado — falhar alto vale mais que subir um serviço com
segredo vazio — mas o canto precisa ser conhecido.

### Um `.env` de antes da fase 2d quebra `make services-test`, e `services-env` não conserta

Quem clonou o repositório **depois** desta fase não vê nada disso: o
`.env.example` do chatbot já traz `DATABASE_URL`, e `make services-env` copia o
arquivo inteiro. O problema é de quem já tinha o repositório. O
`chatbot-service/.env` de antes desta fase guardava **uma** variável,
`JWT_SECRET`, e `app/config.py` passou a declarar `database_url: str` **sem
default** de propósito (um default apontando para o banco do legacy seria pior
que estourar). O `Makefile:183-191` só cria o `.env` que **não existe** — para
um que existe ele imprime `mantido chatbot-service/.env` e não faz mais nada.

Resultado: `make services-env` diz que está tudo certo e `make services-test`
estoura no import, antes de qualquer teste. Reproduzido nesta árvore, pondo no
lugar do `.env` atual um arquivo com a única linha
`JWT_SECRET=pre-branch-placeholder` e rodando `uv run pytest -q` em
`back-end/chatbot-service` (saída colada como veio, com **uma** edição: o
prefixo absoluto do caminho do worktree virou `<repo>`):

```
ImportError while loading conftest '<repo>/back-end/chatbot-service/tests/conftest.py'.
tests/conftest.py:28: in <module>
    from app.config import settings
app/config.py:53: in <module>
    settings = Settings()
               ^^^^^^^^^^
.venv/lib/python3.14/site-packages/pydantic_settings/main.py:247: in __init__
    super().__init__(**__pydantic_self__.__class__._settings_build_values(sources, init_kwargs))
E   pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
E   database_url
E     Field required [type=missing, input_value={'jwt_secret': 'pre-branch-placeholder'}, input_type=dict]
E       For further information visit https://errors.pydantic.dev/2.13/v/missing
```

O `.env` real foi restaurado logo em seguida, conferido pelo `md5sum` de antes
e de depois, e a suíte voltou a `37 passed`.

Correção, uma linha, no `.env` do serviço:

```bash
DATABASE_URL=postgresql+asyncpg://edu:edu@localhost:5433/chatbot_db
```

`DATABASE_URL_TEST` não precisa: tem default apontando para `chatbot_test`.
**O caminho do compose não é afetado** — lá o `docker-compose.yml:246-247`
injeta as duas por `environment`, e o `.env` do diretório do serviço nem é
lido. Vale a mesma regra para qualquer fase futura: variável obrigatória nova
significa que todo `.env` que já existe na máquina de alguém está incompleto, e
o alvo de `.env` não vai avisar.

### `make services-migrate` precisa de imagem reconstruída, e `stack-up` não reconstrói

`Makefile:158` (`stack-up`) é `docker compose up -d`, **sem `--build`**. Numa
máquina cujas imagens são anteriores a esta fase, o `stack-up` sobe o container
do chatbot a partir do cache — uma imagem construída antes de a árvore
`alembic/` existir. E `make services-migrate` roda `alembic upgrade head`
**dentro do container** (`$(COMPOSE) exec -T $$s`, `Makefile:169-173`), não no
host: sem a árvore lá dentro, o alvo não tem o que aplicar.

Que a ausência do Alembic reprova o alvo está medido: no commit em que o
chatbot entrou em `DB_SERVICES` mas ainda não tinha `alembic.ini`,
`make services-migrate` saía com **1** na última iteração — o `|| exit 1` de
`Makefile:172` garante isso. E no portão do bloco D a imagem do chatbot **foi**
reconstruída de propósito antes da verificação de volume limpo, com o registro
da época dizendo que sem o rebuild a verificação não teria significado nada.

Regra prática: quando uma fase acrescenta `alembic/`, um router, ou qualquer
arquivo novo a um serviço, reconstrua a imagem dele antes de rodar
`services-migrate`. `stack-up` sozinho não faz isso.

Sintoma vizinho e da mesma família, **anterior a esta fase**: a imagem do
`commerce-service` no ar também é antiga. No portão do bloco D o
`services-migrate` aplicou nela só a baseline `62926745dd94`, enquanto a árvore
de código carrega treze revisões — o mesmo defeito de cache, num serviço em que
o custo é maior. A cadeia pendente está listada em
[`commerce-parity.md`](commerce-parity.md) §7, item 1.

### Uma fila declarada antes da DLX não aceita a nova declaração

As cinco filas do notification, a do analytics e a do learning foram criadas
sem `arguments`. A partir da spec A elas são declaradas com
`x-dead-letter-exchange`, e o RabbitMQ **recusa** uma redeclaração com
argumentos diferentes: `PRECONDITION_FAILED - inequivalent arg
'x-dead-letter-exchange'`, e o serviço não sobe.

Num broker que já rodou a versão anterior, apague as filas antigas **uma
vez**, com a infra (Postgres, Redis, RabbitMQ) já de pé e antes de subir os
três serviços consumidores — veja a ordem completa na §5, "Runbook de corte
desta fase":

```bash
docker compose -f back-end/docker-compose.yml exec rabbitmq \
  rabbitmqctl delete_queue notification.revision_scheduled
# repetir para: notification.diagnostic_completed,
# notification.order_status_changed, notification.stock_issue,
# notification.delivery_delayed, learning.student_created,
# analytics.event_log
```

Só quem tem broker antigo precisa disso. Um broker limpo declara já com os
argumentos certos e nunca vê o erro.

> **Atenção — passo do usuário.** O comando acima age no stack vivo. Quem executa este plano **não** o roda: registra a instrução e avisa o usuário. Ele decide quando aplicar.

A fila morta em si (`edu.events.dead`,
`back-end/packages/edu-common/src/edu_common/events.py:96-101`) não tem
TTL, não tem `max-length`, não tem consumidor e não tem alarme — é um ralo que
ninguém esvazia. Um handler falhando persistentemente enche essa fila sem
limite.

---

## 12. O que ainda não está aqui

| Fase | O que chega |
|---|---|
| **2** | Paridade do commerce: `products` com reviews e imagem, `cart`, `orders`, `payment-methods` e `tracking` portados do legacy; `support` para o chatbot-service; PKs UUID; o estado `CONFIRMADO`; reconciliação de contrato campo a campo |
| **3** | E-mail real e rate limit no reset de senha; push FCM; Celery + Redis com primitivas atômicas; painel SQLAdmin; upload de imagem; idempotência dos consumidores de evento |
| **4** (spec A, 2026-09-07) | Feito: Flutter apontando para o gateway e remoção de `back-end/legacy/`. Em aberto: tradução dos campos de schema que passarem a ter cliente (§4) |
| **4** (spec B, 2026-09-08) | Feito: parceiro com origem de expedição, estoque com trilha de auditoria, transportadora e ocorrência de transportadora, catálogo por parceiro no app, códigos de pagamento emitidos pelo servidor, e o `web-admin` falando com o gateway. Detalhe e pendências em [`partners-inventory-carriers.md`](partners-inventory-carriers.md) |
| **4** (spec C, 2026-09-09) | Feito: pedido de ponta a ponta pelos quatro perfis — carregamento como credencial do entregador (`/shipments`), posição do entregador simulada e registrada por uma porta única, avanço automático desligado por padrão, push endereçado por transição (registro de staff alimentado por evento), e o e-mail da credencial (primeiro envio real desde a spec A). Detalhe, o que é simulado e o que continua fora em [`order-flow.md`](order-flow.md) |

Até a spec A (2026-09-07), `back-end/legacy/` foi **referência viva**: as
suítes dele foram a especificação executável da paridade que o
commerce-service precisou reproduzir. A spec A apagou o diretório; o resultado
da comparação ficou registrado em [`commerce-parity.md`](commerce-parity.md) e
[`phase-2-debt.md`](phase-2-debt.md).
