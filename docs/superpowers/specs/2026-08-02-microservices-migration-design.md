# Migração para microserviços — design

Data: 2026-08-02

## Problema

O backend hoje é um monolito modular com BFF em `back-end/`: uv, Alembic, 59
arquivos de teste, Celery + Redis, painel SQLAdmin, Firebase FCM, e-mail via
Resend e MinIO para imagem de produto. Os módulos (`auth`, `addresses`,
`products`, `cart`, `orders`, `tracking`, `payment_methods`, `notifications`,
`support`) expõem contrato em inglês sob `/api` e são o que o app Flutter
consome hoje.

Existe uma refatoração pronta para microserviços em `/home/elias/Downloads/edu-project (2)`:
sete serviços (`api-gateway`, `auth-users-service`, `learning-service`,
`commerce-service`, `chatbot-service`, `notification-service`,
`analytics-service`) com coreografia via RabbitMQ. Ela traz domínios que o
monolito não tem — diagnóstico adaptativo com SM-2 e embeddings, chatbot RAG,
analytics — mas diverge do padrão do projeto (pip + `requirements.txt`,
`schema.sql` em vez de Alembic, zero testes) e não tem paridade com o que o
Flutter já consome.

O objetivo é trazer a refatoração para o repositório e tornar `back-end/`
obsoleta **sem quebrar o app**.

## Lacunas de paridade

O próprio `api-gateway/app/routing.py` documenta que `products`, `orders`,
`cart`, `payment-methods` e `support` estão mapeados no gateway mas os
endpoints não existem no destino. O commerce-service fala português
(`/produtos`, `/pedidos`, `/pedidos/{id}/rastreio`) com um modelo de domínio
diferente. Sem portar essas lacunas, trocar o backend quebra no Flutter:
marketplace, carrinho, checkout, meios de pagamento, suporte, rastreio com
mapa, reviews e upload de imagem.

Têm paridade real hoje: `auth` (incluindo `/auth/addresses` e o fluxo de reset
de senha) e `notifications` (incluindo `/notifications/devices`).

As telas de **logística e quiz do Flutter são mockadas** — nenhuma delas chama
a API. Elas não entram no cálculo de quebra, e passam a ter backend real com
learning-service e commerce-service.

Capacidades presentes no legacy e ausentes no stack novo: e-mail real e rate
limit no reset de senha (o código OTP hoje vai para `print()`), push FCM
(o `/notifications/devices` só grava o token), Celery + Redis, painel
SQLAdmin, e storage/upload de imagem.

## Decisões

| Decisão | Escolha |
|---|---|
| Estratégia | Portar as lacunas **antes** de desligar o legacy |
| Padrões | Padrão completo: uv + pyproject + ruff + pytest + Alembic nos 7 serviços |
| Domínio do commerce | Modelo novo como base, enxertado com o que só o legacy tem |
| Contrato público | Padronizado em inglês; código interno segue como veio (português) |
| Capacidades do legacy | Todas sobrevivem: e-mail + rate limit, FCM, Celery + Redis, admin + upload |
| Layout | `back-end/` vira guarda-chuva dos serviços; monolito em `back-end/legacy/` |
| Código comum | Pacote `edu-common` só com o crítico: JWT/auth e eventos RabbitMQ |

## Arquitetura alvo

```
back-end/
  packages/edu-common/      # JWT + deps de auth, publisher/consumer RabbitMQ (uv workspace)
  api-gateway/              # :8000  proxy por prefixo de path
  auth-users-service/       # :8001  auth, users, addresses, password reset (e-mail real)
  learning-service/         # :8002  diagnóstico, SM-2, embeddings, ENEM
  commerce-service/         # :8003  catálogo, cart, orders, payment-methods, tracking, logística
  chatbot-service/          # :8004  RAG (FAISS + Groq) + support
  notification-service/     # :8005  in-app + push FCM
  analytics-service/        # :8006  event log, métricas, anomalias
  legacy/                   # monolito atual — referência viva, removido na fase 4
  docker-compose.yml
```

Cada serviço tem `pyproject.toml` (uv), ruff, pytest e Alembic próprio, com um
banco por serviço e um histórico de migration por serviço. Cada `schema.sql`
importado é convertido em migration baseline.

`edu-common` carrega apenas o que é sensível a segurança e a contrato de
evento: validação de JWT com as dependências de autenticação, e o
publisher/consumer do RabbitMQ. `config.py` e `database.py` seguem duplicados
por serviço, mantendo cada um autônomo.

O `docker-compose.yml` alvo é a união dos dois: Postgres 17.4, Redis 8.2.1,
RabbitMQ 4.2.3 e MinIO (do legacy) mais o gateway, os seis serviços e os
workers Celery.

### Regra de contrato

**Contrato público em inglês, código interno como veio.** Rotas e campos de
schema expostos ficam em inglês (`/subjects`, `/diagnostic`, `/picking`,
`/delivery`); models, services e nomes de função dos serviços importados seguem
em português. Os routers ganham uma camada explícita de tradução — é uma
anti-corruption layer deliberada, não acidente.

## Fases

Cada fase vira seu próprio plano de implementação.

### Fase 1 — Fundação

Importar os 7 serviços normalizados ao padrão do projeto, criar o
`edu-common`, unificar o `docker-compose` e subir tudo ao lado do legacy, que
continua servindo o Flutter intacto.

Inclui a cobertura de teste do código importado (learning, chatbot, analytics,
gateway chegam sem nenhum teste) e as correções de segurança listadas abaixo.

Entrega: stack novo de pé, com testes, sem tocar no app.

### Fase 2 — Paridade do commerce

Portar `products`, `cart`, `orders`, `payment-methods` e `tracking` do legacy
para o commerce-service, e `support` para o chatbot-service.

Reconciliação por agregado:

| Agregado | Base | O que é enxertado do legacy |
|---|---|---|
| `Produto` | novo (categoria, estoque, fornecedor) | reviews, `image_url` via MinIO, PK vira UUID |
| `Pedido` | novo (máquina de 7 estados, separador/entregador, histórico) | snapshot estruturado do endereço (hoje é `Text` livre), PK vira UUID |
| `PedidoItem` | novo (produto/fornecedor) | snapshot de nome, preço, imagem e rating no momento da compra |
| `Cart`, `PaymentMethod` | legacy inteiro | não existem no serviço novo |
| Rastreio | novo (`PedidoStatusHistorico`) | rota Google Maps, ETA, `directions.py` |

**PK UUID** nos agregados portados: o Flutter já espera UUID em string para
`id` de produto, review e pedido, o commerce novo usa `Integer`
autoincremental. UUID casa com o Flutter, casa com o legacy e elimina IDs
enumeráveis.

**Status do pedido**: o Flutter tem 5 estados
(`pending → confirmed → separating → out_for_delivery → delivered`), o commerce
novo tem 7 (`CRIADO → AGUARDANDO_SEPARACAO → EM_SEPARACAO → SEPARADO →
AGUARDANDO_COLETA → EM_TRANSITO → ENTREGUE`).

A máquina interna é preservada e ganha um estado: `CONFIRMADO`, entre `CRIADO` e
`AGUARDANDO_SEPARACAO`. Ele não existe no commerce novo porque a máquina de lá
não modela pagamento — mas o legacy modela, e o Flutter mostra esse passo na
timeline do pedido. Ficam 8 estados internos, e o contrato expõe os 5 via
mapeamento:

- `CRIADO` → `pending`
- `CONFIRMADO` → `confirmed`
- `AGUARDANDO_SEPARACAO`, `EM_SEPARACAO`, `SEPARADO` → `separating`
- `AGUARDANDO_COLETA`, `EM_TRANSITO` → `out_for_delivery`
- `ENTREGUE` → `delivered`

O histórico completo dos 8 estados continua visível em
`GET /orders/{id}/tracking`.

### Divergências de contrato medidas na fase 1

O design original dizia "portar products/cart/orders/payment-methods/tracking". A fase 1
mediu, contra o código real do Flutter, **o que exatamente diverge** — e o problema é
maior do que rota faltando: várias rotas existem, respondem, e ainda assim quebram o app.

| O que o Flutter chama | O que ele espera | O que o commerce-service devolve hoje |
|---|---|---|
| `GET /products` | `{"items": [...]}`, `id` string (UUID) | array puro, `id` inteiro, sem `type`/`subtype`/`rating_avg`/`rating_count` |
| `GET /orders` | array de pedidos com `items[]` | **405** — a listagem está em `/orders/mine` |
| `POST /orders` | `{payment_method, address_id}` | **422** — exige `{endereco_entrega, itens[]}` |
| `GET /orders/{id}/tracking` | objeto único | array de histórico de status |
| `GET /products/{id}/reviews` | `{"items": [...]}` | **404** — rota não existe |
| `GET /orders/{id}/route` | objeto de rota | **404** — rota não existe |
| `GET /notifications` → `data.order_id` | UUID em string (legacy) | inteiro — mesma chave, tipo diferente |

Duas consequências para o planejamento da fase 2:

**O envelope de resposta é parte do contrato, não detalhe de formatação.** O Flutter faz
`jsonDecode(body)['items']`; contra um array puro isso levanta um `TypeError` que o
tratamento de erro do app não captura — a tela quebra sem nem virar mensagem de erro. O
mesmo vale para `id`: o app faz `as String` sobre um inteiro. Traduzir o caminho da rota
resolve metade do problema e esconde a outra metade atrás de um 200.

**A fase 1 trocou 404 limpo por quase-acerto.** Ao mover o commerce para o mesmo espaço de
nomes que o app usa, requisições que antes falhavam de forma óbvia passaram a falhar de
forma sutil (405, 422, forma errada). Isso é aceitável enquanto o Flutter aponta para o
legacy, mas significa que a fase 4 precisa de uma passagem de reconciliação de contrato
campo a campo — não basta apontar o app para o gateway e ver se responde.

### Fase 3 — Paridade de plataforma

E-mail real (Resend) e rate limit no reset de senha; push FCM no
notification-service; Celery + Redis com as primitivas atômicas exigidas pelo
CLAUDE.md; painel SQLAdmin; upload e storage de imagem de produto.

**Mais um item, medido na fase 1: idempotência dos consumidores de evento.** Os
cinco handlers do notification-service e o do analytics-service inserem
incondicionalmente ao receber um evento, sem chave de deduplicação. O RabbitMQ
entrega pelo menos uma vez: uma queda entre o commit e o ack reentrega a mensagem
e gera notificação duplicada para o aluno e contagem inflada no painel. É a regra
10 do CLAUDE.md.

A correção não é local a nenhum dos dois serviços — o `EventPublisher` do
`edu-common` não carimba id de mensagem, então não existe nada estável para
deduplicar. O caminho é: o publisher passa a stampar um id único por evento, os
consumidores ganham um registro de mensagens já processadas, e a checagem entra
antes do insert. Fica na fase 3 porque é onde o Redis e as primitivas atômicas
chegam. Deduplicar por chave de negócio agora seria pior que o buraco honesto:
duas notificações de mesmo tipo para o mesmo pedido podem ser legítimas.

Também nesta fase: o `UNIQUE(aluno_id, token)` de `device_tokens` permite o mesmo
token físico registrado sob dois alunos — inofensivo enquanto não há push real,
relevante no instante em que houver.

### Fase 4 — Desligamento

Apontar o Flutter para o gateway `:8000`, rodar a suíte ponta a ponta, remover
`back-end/legacy/`, atualizar Makefile, `docs/back-end/` e README.

### Por que nessa ordem

O legacy fica vivo até a fase 4 porque é a especificação executável da
paridade: seus 59 arquivos de teste são o critério de aceite do que o
commerce-service precisa reproduzir. Desligar antes disso transformaria
"portar" em "reescrever de memória".

## Correções de segurança na importação

Entram junto com o import, na fase 1 — não depois:

- Remover o `.env` commitado em `auth-users-service/` (contém `JWT_SECRET` de sandbox).
- Trocar o `print()` do código OTP do reset de senha por loguru, sem o segredo no log.
- Paginação e `response_model` explícito em `GET /products`, que hoje devolve o objeto ORM cru sem limite (regras 4 e 6 do CLAUDE.md).
- CORS do gateway restrito por variável de ambiente em vez de `allow_origins=["*"]`.
- `datetime.utcnow()` naive → timezone-aware.
- Auditar cada endpoint importado contra a regra 2: autorização explícita e filtro de ownership.

## Testes

Os 59 arquivos de teste do legacy são o critério de aceite da fase 2: um
comportamento portado só é dado como pronto quando o teste equivalente passa
contra o commerce-service.

Para o código importado sem teste (learning, chatbot, analytics, gateway), a
fase 1 escreve teste de caracterização sobre o comportamento atual antes de
qualquer refactor. Código novo segue Red-Green-Refactor.

Cada serviço tem seu `pytest` com `httpx.AsyncClient` e banco real, espelhando
a estrutura do código (`services/foo.py` → `tests/test_foo.py`).

## Riscos

**`sentence-transformers` e FAISS** são dependências pesadas que tornam build e
suíte lentos. Os testes de learning e chatbot usam um fake do encoder; testes
com modelo real ficam atrás de uma marca `slow`.

**Baseline do Alembic** convertida de `schema.sql` pode divergir dos models. A
fase 1 inclui, como prova de sincronia, um check de que
`alembic revision --autogenerate` produz migration vazia.

**Volume da fase 2** — é a maior das quatro e provavelmente precisa ser
quebrada em dois planos (catálogo/carrinho e pedido/rastreio) no momento de
planejar.

## Fora de escopo

- Reescrever as telas mockadas de logística e quiz do Flutter para consumir os serviços novos.
- Trocar JWT HS256 por RS256.
- Rate limiting, circuit breaker e observabilidade no gateway.
- Integração real de transportadora.
