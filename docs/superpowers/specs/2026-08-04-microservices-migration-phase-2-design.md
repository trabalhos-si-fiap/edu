# Fase 2 — paridade do commerce — design

Data: 2026-08-04
Estado: aprovado, pronto para virar planos de implementação

Antecedentes:
[design das 4 fases](2026-08-02-microservices-migration-design.md) ·
[backlog da fase 1](2026-08-04-migration-backlog.md) ·
[o que existe hoje](../../back-end/microservices.md)

---

## Problema

A fase 1 pôs os sete serviços de pé ao lado do monolito, sem tocar no app. O
Flutter continua falando com `back-end/legacy/` na porta 8001.

A fase 2 fecha a distância entre o que o app consome e o que o stack novo
serve. Ela não é só rota faltando: das sete divergências medidas na fase 1,
**quatro são rotas que existem, respondem, e ainda assim quebram o app** — 405
porque a listagem está noutro path, 422 porque o corpo é outro, array puro onde
o app lê `{"items": …}`, inteiro onde o app faz `as String`.

Escopo desta fase: **tudo que o backlog da fase 1 marcou como fase 2** — a
paridade do commerce, as falhas vendorizadas e a limpeza de frota.

---

## Decisões

| Decisão | Escolha | Consequência principal |
|---|---|---|
| Escopo | Tudo que o backlog marcou fase 2 | Paridade + segurança + frota |
| Empacotamento | Um spec, quatro planos | Decisões de contrato num documento só |
| Alvo de contrato | **Réplica exata** do legacy nas rotas que o app consome | Fase 4 vira troca de `API_BASE_URL`; critério de aceite binário |
| Imagem de produto | Leitura (presign) na fase 2, upload na fase 3 | O agregado é serializado uma vez só |
| Dado entre serviços | HTTP interno com repasse do token do aluno | Sem replicação de PII; checkout ganha dependência síncrona |
| Ciclo de vida do pedido | Só a máquina real de staff; simulador na fase 3 | Segundo carve-out do critério binário |
| `CANCELADO` | Sexto valor `cancelled` no contrato, com o caso no enum do Dart já na fase 2 | Única linha de Dart da fase 2 |
| Língua do modelo | Agregado com cliente vira inglês, tabela e colunas | Migration de rename; as suítes do legacy portam sem tradução manual |

### Por que "réplica exata"

O Flutter faz `jsonDecode(body)['items']` e `as String` sobre `id`. Array puro
ou id inteiro levantam `TypeError` que o tratamento de erro do app não captura
— a tela quebra sem virar mensagem. Traduzir o caminho da rota resolve metade
do problema e esconde a outra metade atrás de um 200.

Réplica exata também dá à fase 2 um critério de aceite **binário**: as suítes do
legacy passam contra o commerce-service, ou não passam. Qualquer outra escolha
transforma "portar" em "reescrever de memória", que é a razão de o legacy ficar
vivo até a fase 4.

Isso inclui reproduzir as inconsistências. `/products` e `/cart` devolvem
envelope; `/orders`, `/support` e `/payment-methods` devolvem array puro;
dinheiro é string (`"49.90"`, para o cliente não herdar erro de float). Não é
elegante — é o contrato.

### Por que traduzir só os agregados que ganham cliente

O design da fase 1 estabeleceu "campos em inglês só onde há cliente", e usou
isso para deixar o commerce-service em português. **A fase 2 é exatamente o
momento em que o commerce ganha cliente** — mas só em dois agregados. Aplicar a
regra por agregado, e não por serviço, é o que a mantém consistente.

As alternativas descartadas, e por quê:

- **Enxerto bilíngue** (cada coluna mantém o nome de origem): mais rápido, mas
  produz um `Produto` com `nome` ao lado de `rating_avg` sem nenhuma regra que
  explique a mistura.
- **Português dentro, inglês só no schema**: coerente internamente, mas exige
  reescrever as 59 suítes antes de poder rodá-las. O critério de aceite deixaria
  de ser executável.

---

## Blocos

Quatro planos de implementação, nesta ordem: **A → B → C**, com **D** em
qualquer ponto depois de A.

### Bloco A — Falhas vendorizadas e limpeza de frota

Primeiro porque contém vulnerabilidade reproduzida ponta a ponta, e porque não
toca contrato nenhum.

**Segurança:**

| Serviço | O que |
|---|---|
| `learning-service` | `POST /diagnostic/answer` amarra `Questao.id.in_(questao_ids)` ao `payload.tema_id`. Hoje qualquer id existente grava resposta — que é a linha que o portão do gabarito checa — e o aluno vê a resposta certa de qualquer questão em duas requisições |
| `auth-users-service` | `birth_date` em ISO deixa de levantar `ValueError` não tratado (`auth.py:59-61`); todo campo de texto ganha `max_length`; `/auth/refresh` passa a consultar o banco |
| `api-gateway` | Teto no corpo bufferizado (`main.py:51`) — comprovado com POST não autenticado de 9,6 MB |
| `commerce-service` | Read→write atômicos em `ocorrencias.py:216-274` e `admin.py:99-109` (com `ge=0`, que hoje permite estoque negativo); leitura de ocorrências deixa de ser staff-wide (`:146`, `:196`); evento publicado **depois** do commit (`:295` vs `:308`) |
| `learning-service` + `notification-service` | `revision.scheduled` para de disparar uma vez por subtema com handler que ignora `subtema_id`; o scheduler passa a escrever `ultima_revisao`, que hoje faz renotificar todo dia para sempre |
| `analytics-service` | `nome` e `email` saem do `event_log` — gravados literalmente, para sempre, sem caminho de leitura |

O `preco_unitario` vindo do cliente em `POST /orders` **não** está aqui: a rota
que o usa é substituída no bloco C pela versão que lê o carrinho e o preço do
catálogo.

**Frota:** os quatro blocos faltantes do `pyproject` do `edu-common` e os dois
`# noqa` que só existem por causa deles; `asyncio_default_test_loop_scope` no
gateway; `cors_origins` declarado e não lido no auth-users-service; `httpx` de
runtime→dev em learning, commerce e notification; as duas variantes de
`Dockerfile.dockerignore`; o whitelist de `requer_papel` no chatbot, que o
chatbot não define; os três `test_health.py` que testam OpenAPI e os dois
serviços sem teste de health; `get_current_user_id`/`get_current_student_id`/
`get_current_student` unificados; `sessionmaker(..., class_=AsyncSession)` →
`async_sessionmaker`; a entrada morta `"addresses"` no `SERVICE_MAP`.

> **Armadilha entre blocos.** A lista de frota inclui
> `commerce-service/app/config.py:17` — `google_maps_api_key` declarado e não
> lido. **O bloco C é quem passa a lê-lo**, em `GET /orders/{id}/route`. O bloco
> A não pode removê-lo; anota que aguarda C.

### Bloco B — Catálogo, reviews, carrinho, payment-methods

`products` traduzido, com PK UUID, `type`/`subtype`/`rating_avg`/`rating_count`
e `image_url` como chave de objeto com presign. Tabela `reviews` nova. `carts`,
`cart_items` e `payment_methods` portados inteiros — não existem no commerce.
Seed do catálogo portado.

### Bloco C — Pedido, checkout, rastreio, rota

`orders`/`order_items` traduzidos, com PK UUID e os oito `ship_*`. Estado
`CONFIRMADO`. `POST /orders` lendo o carrinho. Snapshot de endereço via
auth-users-service. `GET /orders`, rebuy, tracking, `/route`, `predict-eta`.
Mapeamento 9→6 estados. Consumidores de evento acompanhando a troca de tipo do
`order_id`. O caso `cancelled` no enum do Dart.

### Bloco D — Support no chatbot-service

O chatbot-service **não tem banco**: sem `database.py`, sem `alembic/`, e o
compose zera o `DATABASE_URL` dele de propósito. Portar `support` para lá é
acrescentar um eixo de infraestrutura, não um router: `chatbot_db`,
`database.py`, `alembic/`, entradas no compose e no `initdb.d`.

> O compose unificado monta o `initdb.d` **script a script** — não dá para
> montar duas pastas no mesmo destino. Um script novo que não ganhe a linha de
> mount vira no-op silencioso.

---

## Contrato público

### Regra de língua de schema

**O schema segue a tabela, não o router.** `products` e `orders` viram inglês
porque as tabelas viraram. `occurrences`, `picking`, `delivery` e `admin`
continuam em português nos campos vindos de `ocorrencias`/`estoque`/
`fornecedores`, e passam a inglês nos campos vindos de `orders`.

Amarrar a língua ao router produziria `validation_alias` traduzindo
inglês→português, que é tradução para trás.

### Rotas que o app consome — réplica exata

| Rota | Forma | Detalhes que quebram se errados |
|---|---|---|
| `GET /products?q&limit&offset` | `{items,total,limit,offset}` | `limit` 1–100, default 20; `price` string; `id` UUID string; `image_url` presignada |
| `GET /products/categories` | `{items:[{type,count}]}` | — |
| `GET /products/{id}` | `ProductOut` | 404 `"Product not found"` |
| `GET /products/{id}/reviews` | `{items,total,rating_avg,rating_count}` | `rating_avg`/`rating_count` vêm do produto, não da página |
| `POST /products/{id}/reviews` | 201 `ReviewOut` | `rating` 1–5, `comment` ≤2000; `author` via `/auth/me` |
| `GET /cart` | `{items,total}` | `subtotal` por item; dinheiro string |
| `POST /cart/items` | **201** `CartOut` | `quantity` 1–999; 404 `"Product not found"` |
| `DELETE /cart/items/{product_id}?quantity` | 200 `CartOut` | sem `quantity` remove o item inteiro; 404 `"Item not in cart"` |
| `GET /orders?limit&offset` | **array puro** | ordenado por `created_at desc`; `limit` 1–100, default 50 |
| `POST /orders` | 201 `OrderOut` | **corpo opcional**; 400 `"Cart is empty"`, 400 `"Invalid delivery address"` |
| `POST /orders/{id}/rebuy` | `CartOut` | produto fora do catálogo é pulado, não falha |
| `GET /orders/{id}/tracking` | `OrderTrackingOut` (objeto) | `headline`, `steps[4]`, `location`, `kit`, `carrier`, `map_url` |
| `GET /orders/{id}/route` | `RouteOut` | 503 `"Rota indisponível no momento"` quando falta chave ou endereço |
| `POST /orders/{id}/predict-eta` | `ETAPredictionOut` | — |
| `GET /payment-methods` | **array puro** | padrão primeiro |
| `POST /payment-methods` | 201 | `extra="forbid"` — rejeita PAN e CVV |
| `PATCH /payment-methods/{id}` | 200 | só `is_default` |
| `DELETE /payment-methods/{id}` | 204 | — |
| `GET /support` | **array puro** | ordenado por `created_at` |
| `POST /support` | **201**, lista completa | `body` 1–2000 |

Toda rota exige o bearer do aluno.

### Duas colisões com rotas existentes

**`GET /orders/{id}/tracking` está ocupada.** Hoje devolve o histórico de
status; o app espera o objeto que a tela renderiza. A réplica exata fica com a
rota, e o histórico se muda para **`GET /orders/{id}/status-history`**.

**`GET /orders/mine` é a razão de `GET /orders` responder 405.** Some, absorvida
por `GET /orders`. `GET /orders/{id}` e `GET /orders/{id}/delivery-estimate` não
têm equivalente no legacy, não colidem, e ficam — traduzidas: o detalhe passa a
devolver o mesmo `OrderOut` da listagem, e `PrevisaoEntregaOut` acompanha o
rename da coluna que o alimenta.

### Mapeamento de status: 9 internos → 6 do contrato

```
CRIADO                                            → pending
CONFIRMADO                                        → confirmed
AGUARDANDO_SEPARACAO, EM_SEPARACAO, SEPARADO      → separating
AGUARDANDO_COLETA, EM_TRANSITO                    → out_for_delivery
ENTREGUE                                          → delivered
CANCELADO                                         → cancelled
```

`CONFIRMADO` entra entre `CRIADO` e `AGUARDANDO_SEPARACAO`, e quem o dispara já
existe: `confirmar_pagamento`, em `admin.py`. `CANCELADO` segue alcançável dos
mesmos pontos que hoje.

A timeline de `/tracking` mantém os quatro passos visíveis (`confirmed`,
`separating`, `out_for_delivery`, `delivered`), derivados do estado interno pelo
mapeamento acima.

**Por que `cancelled` precisa existir.** O enum do Flutter tem
`default: return OrderSummaryStatus.pending`. Qualquer status desconhecido vira
"Pendente": um pedido cancelado apareceria como ativo, no passo 0 do stepper,
para sempre. E `CANCELADO` é alcançável por pedido do app — a resolução
`CANCELAR_PEDIDO` de uma ocorrência é decisão do próprio aluno. O caso entra no
enum do Dart já na fase 2: é aditivo, fica código morto enquanto o app fala com
o legacy (que nunca emite `cancelled`), e no dia do corte a tela já está certa.

---

## Modelo de dados

### Tabelas

| Hoje | Depois | Motivo |
|---|---|---|
| `produtos` | **`products`** | agregado com cliente → inglês, tabela e colunas |
| `pedidos` | **`orders`** | idem |
| `pedido_itens` | **`order_items`** | idem |
| `fornecedores`, `estoque`, `ocorrencias`, `pedido_status_historico` | inalteradas | sem cliente |
| — | **`reviews`**, **`carts`**, **`cart_items`**, **`payment_methods`** | novas, portadas do legacy |
| — | **`support_messages`** (em `chatbot_db`) | bloco D |

A regra é enunciável: **o agregado que ganha cliente vira inglês; o que não
ganha, fica.**

`categoria` e `type` são o mesmo conceito com dois nomes — os valores do seed do
legacy são `apostila`, `curso`, `digital`. Colapsam em `type`. `subtype` é
coluna nova.

`orders` troca `endereco_entrega Text NOT NULL` pelos oito `ship_*` nullable do
legacy, e ganha `payment_method` e `status_updated_at`. Os schemas de staff que
hoje mostram `endereco_entrega` passam a compor a string a partir dos oito.

O rename de `orders` é da tabela inteira, não só das colunas que o app lê:
`aluno_id`→`user_id`, `valor_total`→`total`, `separador_id`→`picker_id`,
`entregador_id`→`deliverer_id`, `transportadora_nome`→`carrier_name`,
`data_prevista_entrega`→`estimated_delivery_at`, `criado_em`→`created_at`,
`atualizado_em`→`updated_at`. Em `order_items`: `produto_id`→`product_id`,
`fornecedor_id`→`supplier_id`, `quantidade`→`quantity`,
`preco_unitario`→`unit_price`, mais o snapshot que vem do legacy
(`product_name`, `image_url`, `rating_avg`, `rating_count`). `supplier_id` fica
nullable: o carrinho não tem noção de fornecedor, e quem o define é a separação.

### PK UUID e o efeito cascata

`products.id`, `orders.id` e `order_items.id` viram `UUID`. Isso arrasta oito
referências:

`estoque.produto_id` · `order_items.product_id` · `order_items.order_id` ·
`pedido_status_historico.pedido_id` · `ocorrencias.pedido_id` ·
`ocorrencias.produto_id` · `ocorrencias.produto_escolhido_id` · e
**`ocorrencias.produtos_sugeridos`**, que é JSONB com lista de ids — vira lista
de UUID em string, e `substituicao_ia.py` acompanha.

`fornecedores.id` continua `Integer`: sem cliente, e não enumerável de fora.

UUID casa com o Flutter, casa com o legacy, e elimina IDs enumeráveis.

### Estratégia da migration

O `commerce-service` não tem seed nem script de insert, e o `initdb.d` só cria
bancos vazios. O `commerce_db` **nunca teve dado de produção** — o app fala com
o legacy desde sempre.

Então a migration é uma **reconstrução declarada**, não uma sequência de vinte
`ALTER` com conversão de tipo de PK: as tabelas dos agregados afetados são
recriadas na forma nova, com a razão escrita no docstring da revision. As
tabelas sem cliente sofrem só o `ALTER` das colunas de FK.

Isso é uma **suposição verificável, não uma certeza**: antes de gerar a
migration, o plano confere a contagem de linhas nas tabelas afetadas do
`commerce_db` em execução. Se houver dado que importe, a migration vira
preservadora e o custo sobe.

`compare_server_default=True` já está nos cinco `alembic/env.py` — a fase 1
fechou essa armadilha. O check de sincronia (`autogenerate` produzindo migration
vazia) volta como portão de cada bloco.

### Seed do catálogo

`legacy/app/seeds/products.py` espelha o catálogo mock do Flutter
(`mock_marketplace.dart`) e baixa as fotos para o MinIO em
`products/seed-{i}.jpg`, gravando a **chave** em `image_url`. Sem catálogo em
`commerce_db`, o marketplace abre vazio no dia do corte. O alvo de Makefile
acompanha.

### Imagem de produto

`Product.image_url` guarda uma **chave de objeto** (`products/<uuid>.jpg`), não
uma URL. A serialização a transforma em URL presignada de vida curta, memoizada
no Redis para que a mesma chave devolva a mesma URL dentro da janela — sem isso
o app rebaixa o próprio cache de imagem a cada listagem. `products`, `cart` e
`order_items` passam todos por esse serializador.

O `POST /products/{id}/image`, a validação de magic bytes, o teto de tamanho e o
`require_admin` ficam na fase 3.

---

## Acoplamento entre serviços

`commerce-service/app/services/auth_client.py`, espelhando
`chatbot-service/app/services/diagnostico_client.py`: repassa o **mesmo** bearer
do aluno, timeout de 10s, e o `raw_token` nunca vai para log nem para corpo de
erro.

| Chamada | Para quê | Estado |
|---|---|---|
| `GET /auth/addresses/{id}` | snapshot `ship_*` no checkout | **rota nova** no auth-users-service — hoje só existe a listagem |
| `GET /auth/me` | `author` da review | já existe |

Mapeamento de erro, escolhido para casar com o legacy: endereço inexistente ou
de outro usuário → **400 `"Invalid delivery address"`** (é assim que o legacy
trata id obsoleto, não 404); auth inalcançável ou 5xx → **503**.
`AUTH_SERVICE_URL` entra no `config.py` e no compose do commerce.

O JWT carrega `sub`, `role`, `type`, `iat`, `exp`, `jti` — não carrega `name`.
Pôr o nome no token o colocaria em todo header `Authorization`, que vai para log
de acesso; por isso a chamada.

O acoplamento síncrono no checkout é um modo de falha novo, que o legacy não
tinha. É o preço de não replicar PII num segundo banco, e fica registrado como
tal.

---

## Eventos

`pedido_id` deixa de ser inteiro e passa a UUID em string nos cinco eventos de
pedido (`order.created`, `order.status_changed`, `order.stock_issue`,
`order.delivery_delayed`, `order.occurrence_resolved`). Os consumidores
acompanham: `analytics.event_log` e as cinco filas do notification-service.

Isso **fecha um item da fase 4**: o backlog registra que `data.order_id` chega
como UUID string vindo do legacy e como inteiro vindo do notification-service —
mesma chave, tipo diferente. Depois do bloco C, os dois concordam.

As **chaves** do payload continuam em português (`pedido_id`, `aluno_id`,
`valor_total`). Renomeá-las dessincronizaria produtor e consumidor sem nenhum
cliente pedindo — mesma razão que o design já dá para learning/analytics.

---

## Testes

Das 59 suítes do legacy, **20 tocam a fase 2 e 17 entram no critério de aceite**:

| Origem | Em escopo | Adiadas |
|---|---|---|
| `modules/products/` | `test_routes`, `test_services` | `test_image_upload` |
| `modules/cart/` | `test_routes`, `test_services` | — |
| `modules/orders/` | `test_routes`, `test_services` | `test_lifecycle`, `test_status_pipeline` |
| `modules/payment_methods/` | `test_routes` | — |
| `modules/support/` | `test_routes` | — |
| `tests/test_tracking_*` | 6 arquivos | — |
| `seeds/` | `test_products_seed` | — |
| `core/` | `test_media`, `test_storage` (metade de leitura) | metade de escrita |

As outras 39 são de auth, addresses, notifications, admin e e-mail — outros
serviços, outras fases.

**Dois carve-outs**, ambos consequência de decisões desta fase, ambos para a
fase 3:

- `test_image_upload.py` e a metade de escrita de `test_storage.py` — o endpoint
  de upload é fase 3.
- `test_status_pipeline.py` e `test_lifecycle.py` — o simulador Celery é fase 3.
  Até lá, um pedido criado pelo app só anda se alguém trabalhar a fila de
  separação.

As 69 suítes atuais do commerce e as 23 do chatbot são **atualizadas, não
removidas** — elas travam o comportamento de staff que a tradução não pode
mudar.

Constraints herdadas do backlog da fase 1, que valem em todos os quatro planos:

1. **Todo teste de regressão precisa ser provado quebrando o que ele trava.**
   Apareceu em 5 tasks.
2. **Nunca alimentar o teste com a própria constante da implementação.**
3. **Desconfie do instrumento antes de concluir que o código está limpo.**
4. **Monkeypatch no módulo que define, não no que importa** — `from x import y`
   cria um nome novo.
5. **`default=` do SQLAlchemy é client-side** e não cria DEFAULT no banco.
6. **Comentário que era verdade e virou mentira** — seis casos na fase 1,
   invisíveis a revisão de task única por construção.
7. **`docker ps` reporta saudável container que não serve** — o watcher
   `--reload` do granian trava se arquivos somem debaixo dele.

Código novo segue Red-Green-Refactor.

---

## Riscos

**A tradução tem raio maior que o agregado.** Renomear `pedidos` toca `picking`,
`delivery`, `occurrences`, `admin` e as 69 suítes do commerce. Mitigação: o
rename é um commit mecânico próprio, com a suíte verde antes e depois, separado
de qualquer mudança de comportamento.

**Duas dependências de runtime novas no commerce-service** — MinIO e Redis, num
serviço que não tinha nenhuma. Os dois já sobem no compose.

**Dependência síncrona no caminho crítico do checkout.** Ver "Acoplamento entre
serviços".

**Volume.** É a maior das quatro fases, agora com escopo ampliado. Os quatro
planos existem por isso; cada um é executado e revisado em sessão própria.

---

## Correções ao design da fase 1

Duas frases do
[design das 4 fases](2026-08-02-microservices-migration-design.md) foram
escritas antes de a fase 1 medir o código real do Flutter, e este documento as
substitui:

1. **"O histórico completo dos 8 estados continua visível em
   `GET /orders/{id}/tracking`."** Essa rota é ocupada pelo objeto que a tela do
   app renderiza. O histórico se muda para `GET /orders/{id}/status-history`.
2. **A contradição da imagem de produto.** A tabela de reconciliação por
   agregado põe "`image_url` via MinIO" na fase 2; a lista da fase 3 põe "upload
   e storage de imagem de produto" na fase 3. A leitura (presign) é fase 2, a
   escrita (upload) é fase 3.

Além disso, o design conta "8 estados internos" (7 + `CONFIRMADO`) e omite
`CANCELADO`, que já existe no commerce e é alcançável de quase todo ponto do
fluxo. São **9**, e o contrato expõe **6**.

---

## Fora de escopo

- Upload de imagem, simulador Celery, rate limiting, idempotência de
  consumidores, FCM e SQLAdmin — fase 3.
- Apontar o Flutter para o gateway — fase 4. A única linha de Dart da fase 2 é o
  caso `cancelled` no enum.
- Reescrever as telas mockadas de logística e quiz do Flutter.
- Trocar JWT HS256 por RS256.
- Circuit breaker e observabilidade no gateway.
- Integração real de transportadora.
