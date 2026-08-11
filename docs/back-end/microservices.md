# Microserviços — arquitetura do backend

> **Escopo deste documento:** descreve **o que existe hoje**, no fim da fase 1
> da migração. Onde algo ainda não existe, está marcado com a fase em que
> chega. O monolito continua sendo o backend que o app Flutter consome — veja
> [start-here.md](start-here.md).

O plano completo da migração está em
`docs/superpowers/specs/2026-08-02-microservices-migration-design.md`.

---

## 1. Topologia

A fase 1 colocou os sete serviços novos **ao lado** do monolito, não no lugar
dele. Os dois stacks sobem juntos, no mesmo projeto Docker Compose (`edu`),
compartilhando uma única instância de Postgres, Redis, RabbitMQ e MinIO.

```
                     Flutter (hoje)
                           │
                           ▼
              ┌────────────────────────┐
              │  legacy (monolito)     │  :8001   ← o app fala com este
              └────────────────────────┘
                           
              ┌────────────────────────┐
              │  api-gateway           │  :8100   ← proxy por prefixo de path
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
| `legacy` (monolito) | **8001** | `edu` | Backend de produção do app: auth, products, cart, orders, tracking, payment-methods, support, notifications, BFF, admin SQLAdmin, Celery |
| `api-gateway` | **8100** | — | Proxy reverso por prefixo de path sob `/api`. Sem banco, sem eventos |
| `auth-users-service` | **8101** | `auth_db` | Registro, login, refresh, reset de senha por OTP, perfil e endereços |
| `learning-service` | **8102** | `learning_db` | Matérias, temas, subtemas, diagnóstico adaptativo, SM-2, embeddings, recomendação semântica |
| `commerce-service` | **8103** | `commerce_db` | Catálogo, pedidos, máquina de 7 estados, separação, entrega, ocorrências, admin de estoque |
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

Um Postgres, vários bancos: `edu` (legacy) mais `auth_db`, `learning_db`,
`commerce_db`, `chatbot_db`, `notification_db` e `analytics_db`, cada um com um
`*_test` correspondente para as suítes. **Só o `api-gateway` não tem banco** — o
`DATABASE_URL` dele é explicitamente zerado no compose para que a credencial do
legacy não fique no ambiente de um container que não deveria alcançá-la.

O `chatbot-service` estava nessa mesma frase até a fase 2d e **saiu dela**: o
módulo `support` deu banco a ele, e `back-end/docker-compose.yml:307-308`
preenche `DATABASE_URL` e `DATABASE_URL_TEST` com `chatbot_db` e `chatbot_test`
— não mais com string vazia. A razão do zeramento continua valendo, e continua
escrita no próprio compose (`:302-306`): ela agora vale só para o gateway, que
não fala com banco nenhum.

---

## 3. Mapa de rotas do gateway

Tudo que chega em `/api/<prefixo>/...` é resolvido pelo primeiro segmento do
path contra o `SERVICE_MAP` de `back-end/api-gateway/app/routing.py`. Prefixo
não mapeado devolve 404 com uma mensagem explícita do próprio gateway; prefixo
mapeado é repassado, e aí o 404 (se houver) vem do serviço de destino.

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
| `cart` | commerce-service | OK — portado na fase 2b |
| `payment-methods` | commerce-service | OK — portado na fase 2b |
| `picking` | commerce-service | OK |
| `delivery` | commerce-service | OK |
| `occurrences` | commerce-service | OK |
| `admin` | commerce-service | OK |
| `notifications` | notification-service | OK |
| `analytics` | analytics-service | OK |
| `chat` | chatbot-service | OK |
| `support` | chatbot-service | OK — portado do legacy na fase 2d |

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
commerce-service -> ['admin', 'cart', 'delivery', 'health', 'occurrences', 'orders', 'payment-methods', 'picking', 'products']
chatbot-service -> ['chat', 'health', 'support']
notification-service -> ['health', 'notifications']
analytics-service -> ['analytics', 'health']
```

Os 20 prefixos do `SERVICE_MAP` aparecem nessa lista. O 404 do gateway continua
existindo, mas hoje ele é **sempre** sobre prefixo não mapeado — nunca sobre
prefixo mapeado e vazio. `addresses` é o exemplo vivo disso.

`addresses` **não está na tabela acima porque não está no mapa**. A entrada
existia e foi removida pelo commit `42bc7ce` ("refactor(gateway): drop the dead
addresses entry from SERVICE_MAP"), ancestral do HEAD desta branch:
`grep -c addresses back-end/api-gateway/app/routing.py` devolve `0`. Ninguém
serve `/addresses` — tanto o legacy quanto o auth-users-service montam os
endereços sob **`/auth/addresses`**
(`APIRouter(prefix="/auth/addresses")`, em
`back-end/auth-users-service/app/routers/addresses.py:12` e
`back-end/legacy/app/modules/addresses/routes.py:14`), que roteia pelo prefixo
`auth`; o app Flutter também chama `/auth/addresses`
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

Isso vira dívida na fase 4: quando o Flutter falar com o gateway, todo campo
que ele consumir precisa estar em inglês. O corte acima **empurra** a tradução
para quando existir um cliente que a justifique — não a cancela.

---

## 5. Como subir o stack

Tudo a partir da raiz do repositório.

```bash
make stack-up          # sobe infra + legacy + gateway + os 6 serviços
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
idempotentes.

`make services-seed` é o terceiro alvo desse fluxo e **nunca foi executado** —
foi escrito na fase 2b, e no `commerce_db` de dev a tabela `products` nem
existe ainda (`to_regclass('public.products')` devolve vazio). A idempotência
**sequencial** dele é medida — `seed_products` rodado duas vezes na mesma
sessão insere o catálogo e depois insere zero
(`tests/test_products_seed.py::TestProductsSeed::test_is_idempotent`, verde).
O que **não** é medido, e é a dívida de verdade, é a idempotência
**concorrente**: o seed lê o que já existe e só então grava, e `products.name`
tem índice sem `unique`, então duas execuções simultâneas inserem o catálogo
duas vezes sem erro. Veja a §2.1 de
[`phase-2-debt.md`](phase-2-debt.md) antes de rodá-lo pela primeira vez.

Conferindo que subiu:

```bash
curl -s localhost:8001/health   # legacy
curl -s localhost:8100/health   # gateway
curl -s localhost:8101/health   # ... até 8106
```

Outros alvos:

```bash
make stack-down                     # derruba o stack inteiro
make stack-logs SVC=analytics-service   # logs de um serviço (default: api-gateway)
make services-sync                  # uv sync em cada projeto, para o IDE
```

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

A suíte do legacy é separada e continua sendo o critério de aceite da paridade
da fase 2 — rode com `make back-test`.

---

## 7. `edu-common`

Pacote compartilhado em `back-end/packages/edu-common`, consumido pelos
serviços como path dependency editável via `[tool.uv.sources]`. **Não é um uv
workspace**: o `auth-users-service` fixa uma versão de `bcrypt` incompatível
com a do legacy, e num workspace o lock é único.

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

Coreografia via RabbitMQ, no exchange **`edu.events`**. Nove routing keys em
produção hoje:

`student.created`, `staff.created`, `diagnostic.completed`,
`revision.scheduled`, `order.created`, `order.status_changed`,
`order.stock_issue`, `order.delivery_delayed`, `order.occurrence_resolved`.

Sete filas, todas ligadas ao `edu.events`:

| Fila | Serviço | Escuta |
|---|---|---|
| `analytics.event_log` | analytics-service | todas as nove |
| `notification.diagnostic_completed` | notification-service | `diagnostic.completed` |
| `notification.revision_scheduled` | notification-service | `revision.scheduled` |
| `notification.order_status_changed` | notification-service | `order.status_changed` |
| `notification.stock_issue` | notification-service | `order.stock_issue` |
| `notification.delivery_delayed` | notification-service | `order.delivery_delayed` |
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

**O legacy fica onde o `.env` já manda.** A porta host dele é
`API_PORT_EXTERNAL` do `back-end/.env` (**8001** nesta máquina). O app Flutter
aponta para essa porta, e a fase 1 inteira foi feita sem tocar nessa variável:
qualquer mudança ali quebra o app em uso.

**O stack novo vive na faixa 81xx.** Gateway em `GATEWAY_PORT_EXTERNAL`
(**8100**) e os seis serviços fixos em **8101-8106**. A faixa 80xx não estava
disponível: a 8001 é do legacy e a 8000 pode estar ocupada por outro projeto na
mesma máquina. Publicar um serviço novo em 80xx arriscaria colidir — e a
colisão apareceria como *resultado errado*, não como erro, porque o container
sobe normalmente e outra aplicação atende.

**O que muda na fase 4.** No desligamento, o Flutter passa a falar com o
gateway, o `back-end/legacy/` é removido e a porta que o app usa deixa de
apontar para o monolito. As portas 8101-8106 podem então deixar de ser
publicadas: só o gateway precisa ser alcançável de fora, e os serviços passam a
ser acessíveis apenas pela rede interna do compose, que já é como o gateway
fala com eles hoje (`http://<serviço>:8000`).

---

## 10. Variáveis de ambiente e segredos

**Nenhum `.env` vai para o repositório. O `.env.example` é o contrato.**

Existe **um** `.env` para os dois stacks, em `back-end/.env`, ao lado do
`docker-compose.yml` unificado. Além dele, cada serviço tem o seu próprio
`.env.example` para quem quiser rodar o serviço direto no host, fora do
compose.

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

Três coisas que mordem e não são óbvias.

### `make back-down` derruba a infra debaixo dos serviços novos

`back-down` roda o compose do legacy, que declara o **mesmo projeto** (`edu`) e
os mesmos `container_name` da infra compartilhada. Ele para `postgres`, `redis`,
`rabbitmq`, `minio`, `api`, `worker` e `migrate` — mas **não** para os sete
containers novos, porque eles não estão declarados naquele arquivo. Resultado:
gateway e serviços continuam de pé sem banco, sem broker e sem cache.

Isso é inerente ao desenho de infra única e não é bug. Com o stack unificado no
ar, use **`make stack-down`**. Se derrubou sem querer, `make stack-up` traz
tudo de volta.

### `make stack-up` num volume existente não cria os bancos

O hook `initdb.d` do Postgres só roda em volume **novo**. Num volume que já
existe — o caso de qualquer máquina que já rodava o legacy — os bancos por
serviço e as migrations não aparecem sozinhos. Rode `make services-dbs` e
`make services-migrate` depois do `stack-up`. Veja a §5.

Detalhe relacionado: o compose unificado monta o `initdb.d` **script a script**,
não a pasta inteira (não dá para montar duas pastas no mesmo destino). Um script
novo em qualquer um dos dois `initdb.d` vira um no-op silencioso aqui, ainda que
funcione no compose do legacy. Ao acrescentar um script, acrescente também a
linha de mount.

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

---

## 12. O que ainda não está aqui

| Fase | O que chega |
|---|---|
| **2** | Paridade do commerce: `products` com reviews e imagem, `cart`, `orders`, `payment-methods` e `tracking` portados do legacy; `support` para o chatbot-service; PKs UUID; o estado `CONFIRMADO`; reconciliação de contrato campo a campo |
| **3** | E-mail real e rate limit no reset de senha; push FCM; Celery + Redis com primitivas atômicas; painel SQLAdmin; upload de imagem; idempotência dos consumidores de evento |
| **4** | Flutter apontando para o gateway; remoção de `back-end/legacy/`; tradução dos campos de schema que passarem a ter cliente |

Até a fase 4, `back-end/legacy/` é **referência viva**: as suítes dele são a
especificação executável da paridade que o commerce-service precisa reproduzir.
