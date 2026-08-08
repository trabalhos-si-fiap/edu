# Paridade commerce-service × legacy — portão do bloco B

Documento do **portão** da fase 2b: mede se o `commerce-service` é réplica do
monolito (`back-end/legacy/`) nas rotas de catálogo, reviews, carrinho e formas
de pagamento, para que a fase 4 seja uma troca de `API_BASE_URL` no app
Flutter.

- Branch medida: `feat/microservices-phase-2b`, HEAD `9ea4398` (portão, task
  B11). O **buraco de porte** que o portão encontrou (§4) foi fechado depois,
  pela task B12, e re-medido em `63f8977` — as seções afetadas dizem qual das
  duas medições produziu cada número.
- Data da medição: 2026-08-07 (as duas).
- Registro cru, com a saída literal de cada comando:
  `.superpowers/sdd/2026-08-05-phase-2b-catalog-and-cart/task-B11-report.md`
  e `task-B12-report.md` (diretório temporário do SDD — este documento é o
  que sobrevive).

Toda afirmação abaixo tem um comando por trás. Onde não houve medição, está
escrito que não houve.

---

## 1. Veredito

| Item | Resultado |
|---|---|
| Chaves das quatro rotas que o app consome | **idênticas** ao legacy (diff vazio nas quatro) |
| Tipos JSON de cada valor | **idênticos** (zero divergências) |
| Suíte do commerce | **187 passando** (`63f8977`; eram 177 no portão) |
| Frota | 8/8 alvos, `ruff` limpo — 491 medidos no portão, **501 medidos** depois da B12 (§8) |
| Sync-check de schema | 5 de 5 vazios |
| Buracos de porte | **0** — o único (§4) foi fechado pela B12 |
| Divergências deliberadas | **5** (ver §5) |

**O corte é viável do ponto de vista do contrato HTTP.** O que falta é
operacional (§7), não de forma de resposta.

---

## 2. Contagem: portado vs. legacy

Comparação sobre o recorte que o plano define (rotas e serviços de products,
cart, payment_methods, seed do catálogo, media e storage).

| Lado | Testes |
|---|---|
| Legacy, no recorte comparado | **70** |
| Commerce, nos oito arquivos portados | **91** |

Commerce, arquivo a arquivo: `test_products_parity.py` 18,
`test_products_services_parity.py` 9, `test_cart_parity.py` 16,
`test_cart_services_parity.py` 8, `test_payment_methods_parity.py` 23,
`test_products_seed.py` 12, `test_media.py` 4, `test_storage.py` 1.

A conta fecha nome a nome: **70 − 6 ausentes = 64 em comum; 64 + 27
acrescentados = 91.**

Reconciliação re-medida na B12 com
`grep -c 'def test_' <arquivo>` dos dois lados. O legacy continua em 70:
`products/test_routes.py` 13, `products/test_services.py` 9,
`cart/test_routes.py` 9, `cart/test_services.py` 8,
`payment_methods/test_routes.py` 12, `seeds/test_products_seed.py` 10,
`core/test_media.py` 8, `core/test_storage.py` 1.

> No portão (`9ea4398`) esta conta era **70 − 14 = 56; 56 + 25 = 81**. Os 9
> testes de `products/test_services.py` saíram da coluna "ausentes" e entraram
> na de "em comum" quando a B12 os portou.
>
> O portão escreveu 15/55/26 aqui. Re-medido por diff de nomes conjunto a
> conjunto: os ausentes eram **14**, não 15 — um dos nove nomes,
> `test_returns_product`, já existia em `tests/test_products_parity.py` no
> próprio `9ea4398`. O total 81 estava certo (é `177 passed` medido), porque
> os dois erros se cancelavam.

### Os 6 ausentes

| Quantos | Origem | Classificação |
|---|---|---|
| 5 | `tests/core/test_media.py` (`test_validate_*`) | carve-out declarado — `validate_image_bytes` é de upload, fase 3 |
| 1 | `tests/core/test_storage.py` (`test_put_get_delete_roundtrip`) | carve-out declarado (metade de escrita). O arquivo tem **um** teste combinado, não duas metades; substituído por `test_generate_presigned_get_returns_a_signed_url` |

Os 9 de `tests/modules/products/test_services.py` **saíram desta tabela**: a
B12 portou os nove para `tests/test_products_services_parity.py` (§4).

`tests/modules/products/test_image_upload.py` (5 testes) é carve-out declarado
e não entra na conta.

### As 27 adições sobre o legacy

Ownership de carrinho (3) e de formas de pagamento (4), concorrência de
carrinho (3), de review (1) e de default de pagamento (3), deriva de catálogo
no carrinho (1), CHECK constraints no nível do banco (2), contrato de array
puro (1), ordenação (1), reviews extras (4 — a quarta é o POST **autenticado**
de review em produto inexistente, acrescentada pela B12; ver §4), contrato
literal do seed (1), injeção de `fetch_image` (1), presign isolado (1), janela
de cache do presign (1).

---

## 3. As quatro rotas, lado a lado

Prova **em processo** (`httpx.AsyncClient` + `ASGITransport`), cada app contra
o seu banco descartável, com a mesma semente. Os valores não batem (bancos
diferentes); as chaves e os tipos sim.

| Rota | Topo do JSON | Chaves | Diff |
|---|---|---|---|
| `GET /products?limit=2` | `dict` nos dois | 13 = 13 | vazio |
| `GET /products/categories` | `dict` nos dois | 3 = 3 | vazio |
| `GET /cart` | `dict` nos dois | 12 = 12 | vazio |
| `GET /payment-methods` | `list` nos dois | 8 = 8 | vazio |

```
/products          items, items[].{id,name,type,subtype,description,price,
                   image_url,rating_avg,rating_count}, total, limit, offset
/products/categories  items, items[].{type,count}
/cart              items, items[].{product_id,name,type,subtype,price,quantity,
                   subtotal,image_url,rating_avg,rating_count}, total
/payment-methods   [].{id,type,is_default,card_last4,card_brand,
                   cardholder_name,card_expiry,pix_key}
```

Contrato verificado item a item, idêntico nos dois lados:

- **Envelope** em `/products`, `/products/categories` e `/cart`; **array puro**
  em `/payment-methods` (o topo do JSON é `list` nos dois lados — não é
  esquecimento, é o contrato do legacy).
- `price`, `subtotal` e `total` do carrinho serializados como **string**
  (`"129.90"`, `"259.80"`).
- `id` / `product_id` como **string UUID** (UUIDv7 nos dois).
- `image_url` **presignada**: chave ausente → `""`; chave presente → URL SigV4
  de 291 caracteres, mesmo host, bucket, caminho e parâmetros nos dois lados.
- Status HTTP idêntico nas quatro (200).

### O que esta prova NÃO cobre

- A **camada de rede** — tudo rodou dentro do processo, por `ASGITransport`.
- O **granian** e o **Dockerfile**: nenhuma imagem desta branch foi construída
  ou executada.
- O **api-gateway** e o roteamento por `SERVICE_MAP`. O gateway mapeia
  `products`, `cart` e `payment-methods` para `commerce` em
  `api-gateway/app/routing.py`.

  **Correção medida, e ela muda o risco do corte.** Os blocos A e B
  trabalharam inteiros sobre a premissa de que "o app Flutter fala direto com
  o monolito na 8001, então nenhum cliente chega ao `SERVICE_MAP`". Isso é
  **falso** no código: `front-end-flutter/lib/core/network/api_config.dart:35-39`
  compila como default `http://localhost:8100/api` (e `10.0.2.2:8100` no
  emulador Android) — **o gateway**. Só `make front` / `make front-device`
  (`Makefile:42-43,55,59`) sobrescrevem para 8001. O
  `front-end-flutter/README.md:39,66-71` ainda descreve a 8001; o código não.
  Ou seja: o gateway já é o caminho padrão do app, e montar `cart` e
  `payment-methods` no `SERVICE_MAP` passa a ser mudança visível ao cliente,
  não preparação inerte.
- **Auth real**: a dependência de usuário foi sobrescrita nos dois apps.
- **Redis real** e **MinIO real**: stub em memória e assinatura local.

Nota operacional: o container `edu-commerce-service-1` que roda na 8103 é
construído do checkout principal e **não** tem as rotas do bloco B
(`GET /cart` e `GET /payment-methods` devolvem 404 nele). Qualquer comparação
por `curl` contra 8103 antes do corte mede o código errado.

---

## 4. O buraco de porte — encontrado no portão, FECHADO pela B12

### O que o portão (`9ea4398`) encontrou

`legacy/tests/modules/products/test_services.py` (**9 testes**) nunca tinha
sido portado como arquivo. Não era carve-out declarado: o plano cita esse
arquivo **uma única vez**, dentro do comando de comparação do próprio portão,
e nunca mandou nenhuma task portá-lo.

O portão escreveu aqui que "nenhum dos nove nomes existia no commerce sob
outro nome". **Re-medido: oito não existiam, um existia** —
`test_returns_product` já estava em `tests/test_products_parity.py` no próprio
`9ea4398` (`git grep -n test_returns_product 9ea4398 -- back-end/commerce-service/tests`).

Quanto ao que estava travado, a re-medição por mutação (11 mutações, cada uma
contra a suíte pré-B12) desenha assim, e **não** como o portão descreveu:

- **5 dos nove** já tinham guarda ao nível de rota — a mutação ficava vermelha
  sem os testes da B12.
- **1 pela metade**: `author` era pego, `user_id` não.
- **3 sem guarda nenhuma**: `test_q_filters_by_name_case_insensitive`,
  `test_pagination_limits_and_reports_full_total` e
  `test_missing_product_raises`. Com a propriedade quebrada, a suíte inteira
  ficava verde em `177 passed`.

A tabela de mutações abaixo lista como terceiro item o **POST 404 ao nível de
rota**, que é uma **adição** da B12 e não um dos nove — a terceira propriedade
sem guarda entre os nove é `test_missing_product_raises`. As três linhas da
tabela continuam corretas como medição; só a contagem "três dos nove" é que
misturava as duas listas.

### O que a B12 fez (`63f8977`)

Os nove foram portados para
`back-end/commerce-service/tests/test_products_services_parity.py`, mais uma
adição ao nível de rota em `tests/test_products_parity.py`
(`test_create_review_for_unknown_product_returns_404`).

As três propriedades agora estão travadas. Cada linha da tabela é a MESMA
mutação, medida duas vezes: antes (ignorando os testes novos, com
`--ignore=tests/test_products_services_parity.py --deselect
"tests/test_products_parity.py::TestReviews::test_create_review_for_unknown_product_returns_404"`)
e depois, com eles.

| Propriedade | Mutação | Antes da B12 | Depois | Teste que pega |
|---|---|---|---|---|
| Busca `?q=` case-insensitive | `Product.name.ilike` → `.like` em `app/services/produtos.py` | `177 passed` | `assert 0 == 1` | `test_q_filters_by_name_case_insensitive` |
| `total` reporta a contagem completa quando `limit` trunca | `total = len(items)` em `listar_produtos` | `177 passed` | `assert 2 == 3` | `test_pagination_limits_and_reports_full_total` |
| POST de review em produto inexistente **autenticado** → 404 | trocar `except ProductNotFoundError` do POST em `app/routers/produtos.py` | `177 passed` | `app.exceptions.ProductNotFoundError` propaga (sem 404) | `test_create_review_for_unknown_product_returns_404` |

Mais oito mutações cobrem os outros sete testes portados (agregados de review
não recomputados, `author` e `user_id` não propagados, `raise` de
`buscar_produto` removido, contagem de categorias falsificada, `offset+1`,
linha errada em `buscar_produto`, exceção errada em `criar_review`) — **11 de
11 ficam vermelhas**, cada uma na asserção que nomeia a propriedade. Saída
literal de cada uma em `task-B12-report.md`. Nenhum teste portado ficou sem
mutação que o derrube.

Toda mutação foi restaurada com `git checkout -- <path>`; nada de mutação foi
commitado (`git status --short` vazio entre as rodadas, fora dos dois arquivos
de teste da própria B12).

**A adição não é divergência.** Medido: o legacy também não tem POST
autenticado em produto inexistente — `grep -n "reviews"
legacy/tests/modules/products/test_routes.py` devolve seis linhas, e o único
POST em `uuid.uuid4()` é o de 401, sem `headers=`. Os dois roteadores traduzem
a mesma exceção no mesmo 404 `"Product not found"`
(`legacy/app/modules/products/routes.py:130-131` × `app/routers/produtos.py`),
comparados **por leitura**. Nenhum código de produção foi alterado.

Uma diferença real nessa mesma rota, que a leitura expôs e que a fase 4 precisa
saber: o POST do commerce chama `get_me` no auth-service **antes** de tocar o
banco, então ele tem um **503** que o legacy não consegue produzir. O 404 é
idêntico; o caminho de falha do auth não é.

---

## 5. As cinco divergências deliberadas do legacy

| # | Divergência | Onde | Razão | Quem decidiu |
|---|---|---|---|---|
| 1 | **403 vs 401** quando falta o header `Authorization` | `packages/edu-common/src/edu_common/deps.py` | `edu-common` responde **403** `{"detail":"Não autenticado"}` para header ausente e **401** `{"detail":"Token inválido ou expirado"}` para token presente-mas-inválido; o legacy responde 401 nos dois. Alinhar o `edu-common` afetaria 6 serviços e 53 asserções `== 403` em 16 arquivos **na medição da B0, em `d2427f5`** — o próprio bloco B acrescentou mais 5, então hoje são **58 asserções em 19 arquivos** (`git grep -c "== 403" HEAD -- "back-end/*.py" ":!back-end/legacy"`, descontando 1 ocorrência que é código de produção). Para um caso que o app quase não exercita — o `TokenRefresher` do Flutter dispara no **401**, idêntico dos dois lados. **Vale igual para o bloco C.** | Plano, confirmado por medição (task B0) |
| 2 | **`GET /payment-methods` sem paginação** | `commerce-service/app/routers/pagamento.py` | Contraria a regra 4 do `CLAUDE.md` (paginação obrigatória). Réplica exata do legacy. Medido: o conjunto é escopado por usuário mas **não tem teto** nem no banco nem na aplicação — e o legacy também não tem. | **Usuário, 2026-08-07**: o plano governa |
| 3 | **Lock de linha + índice único parcial** em `payment_methods` | `commerce-service/app/services/pagamento.py`; migration `942f75a9a3f2` | O legacy não tem nenhum dos dois e deixa **dois defaults simultâneos** em 10/10 tentativas de DELETE-do-default concorrente com POST. A regra 3 do `CLAUDE.md` (read→write atômico) é inviolável, e a proteção **não muda o contrato HTTP** — medido, o PATCH concorrente devolve `(200, 200)` com 1 default, igual ao legacy. | **Usuário, 2026-08-07**: pôr o lock |
| 4 | **Asserção de PNG substituída** no teste do seed | `commerce-service/tests/test_products_seed.py` | `validate_image_bytes` não existe no commerce (carve-out de upload). Virou checagem estrutural de PNG pela stdlib. Revisor mediu que a substituta é **estritamente mais forte**: um PNG com CRC calculado sobre `data` em vez de `typ+data` passa na checagem do legacy e falha na nova. | Task B10, ratificado na revisão |
| 5 | **`type` no lugar de `category`** na resposta de `/products` | `commerce-service/app/schemas/produto.py` | O `ProductOut` do commerce já expunha `category` na saída (o `validation_alias` só traduzia a **entrada**); o `ProductOut` do legacy expõe `type`. Manter `category` faria o commerce divergir do contrato replicado do legacy. Nenhum cliente consome a rota hoje. | **Usuário, 2026-08-07** (escalado como contradição do plano na task B3) |

---

## 6. Asserções adaptadas — "onde exatamente o commerce não é o legacy"

Formato `arquivo:linha | original | atual | razão`. Linhas medidas em `9ea4398`,
relativas a `back-end/commerce-service/` — exceto as quatro últimas linhas da
tabela, do arquivo que a B12 criou, medidas em `63f8977`.

| Arquivo:linha | Asserção original (legacy) | Asserção atual | Razão |
|---|---|---|---|
| `tests/test_products_parity.py:68` | `assert r.status_code == 401` (`test_list_requires_auth`) | `assert r.status_code == 403` | divergência 1 (403 vs 401) |
| `tests/test_products_parity.py:79` | `assert r.status_code == 401` (`test_create_review_requires_auth`) | `assert r.status_code == 403` | divergência 1 |
| `tests/test_cart_parity.py:63` | `assert r.status_code == 401` (`test_get_requires_auth`) | `assert r.status_code == 403` | divergência 1 |
| `tests/test_cart_parity.py:68` | `assert r.status_code == 401` (`test_add_requires_auth`) | `assert r.status_code == 403` | divergência 1 |
| `tests/test_payment_methods_parity.py:61` | `assert r.status_code == 401` (`test_list_requires_auth`) | `assert r.status_code == 403` | divergência 1 |
| `tests/test_cart_parity.py:111` | só `assert r.status_code == 404` | `+ assert r.json()["detail"] == "Product not found"` | fecha buraco que existia **no próprio legacy** — o texto nunca era assertado |
| `tests/test_cart_parity.py:164` | só `assert r.status_code == 404` | `+ assert r.json()["detail"] == "Item not in cart"` | idem |
| `tests/test_products_routes.py:52` | `assert isinstance(response.json(), list)` | `assert "items" in response.json()` | `/products` passou de array puro para o envelope do legacy |
| `tests/test_products_routes.py:68` | `assert len(response.json()) == 2` | `assert len(response.json()["items"]) == 2` | idem |
| `tests/test_products_routes.py:82` | `assert len(response.json()) <= 100` | `assert len(response.json()["items"]) == 20` | a original passava **vacuosamente** (contava as 4 chaves do envelope); alinhada ao default 20 do legacy |
| `tests/test_products_routes.py:88` | `product = response.json()[0]` | `product = response.json()["items"][0]` | dict de envelope não é indexável por inteiro |
| `tests/test_products_routes.py:120` | `item = response.json()[0]` | `item = response.json()["items"][0]` | idem |
| `tests/test_products_routes.py:89-99` | `set(product) == {id,name,description,price,category,image_url}` | `set(product) == {id,name,type,subtype,description,price,image_url,rating_avg,rating_count}` | divergência 5 (`category`→`type`) + três campos de catálogo do legacy |
| `tests/test_products_seed.py:131-143` | `test_solid_png_is_a_valid_image` via `validate_image_bytes` | leitura estrutural do PNG pela stdlib | divergência 4 |
| `tests/test_products_services_parity.py:146` | `pytest.raises(ProductNotFound)` (`test_missing_raises`) | `pytest.raises(ProductNotFoundError)` | a exceção do commerce leva sufixo `Error` (regra N818 do `ruff`) — mesma classe de renome já registrada em `app/exceptions.py` |
| `tests/test_products_services_parity.py:199` | `pytest.raises(ProductNotFound)` (`test_missing_product_raises`) | `pytest.raises(ProductNotFoundError)` | idem |
| `tests/test_products_services_parity.py:192` | `assert review.author == created_user.name` | `assert review.author == USER_NAME` (`"Maria Silva"`) | não há tabela de usuários no commerce (auth é outro serviço, outro banco). `USER_NAME` é o literal do `created_user` do legacy (`legacy/tests/modules/products/conftest.py:17`), então a asserção afirma o mesmo valor |
| `tests/test_products_services_parity.py:193` | `assert review.user_id == created_user.id` | `assert review.user_id == user_id` (fixture `uuid.uuid4()`) | `Review.user_id` é FK **lógica** para o auth-users-service, sem constraint física — um uuid solto exerce a propagação igual. Mesma decisão da task B8 em `test_cart_services_parity.py` |

### Testes removidos, não adaptados

| Teste | Arquivo | Razão |
|---|---|---|
| `test_products_can_be_filtered_by_category` | `tests/test_products_routes.py` | o parâmetro `?category=` saiu da rota — o legacy nunca teve esse filtro |
| `test_unknown_category_returns_empty_list` | `tests/test_products_routes.py` | idem |

Consequência registrada: **nenhum teste cobre filtragem do catálogo por
categoria hoje**. Remoção deliberada, mandada pelo plano.

---

## 7. O que ainda está devendo no corte

1. **`commerce_db` está no baseline e vazio.** Medido:
   `alembic_version = 62926745dd94`, tabela ainda chamada `produtos`, 0 linhas.
   As **sete** migrations do bloco B (`77290516f1b1` … `942f75a9a3f2`)
   **nunca foram aplicadas** ali. (`alembic/versions/` tem oito arquivos; o
   oitavo é a baseline `62926745dd94`, que já está aplicada — a cadeia é
   `62926745dd94 → 77290516f1b1 → 1308bb221890 → d3a5f5cd6ea8 → c28f71cb6e30
   → ae70488977ef → 6c409ccb480c → 942f75a9a3f2`.) O corte precisa de `alembic upgrade head` e depois do
   seed. Risco relacionado, medido na task B5: `server_default` **não** protege
   `ALTER COLUMN … SET NOT NULL` contra linha pré-existente com NULL (o
   Postgres não faz backfill). Hoje a tabela está vazia; se alguém popular
   antes de migrar, a migration falha em `type`, `description` e `image_url`.

2. **`make services-seed` foi escrito e nunca executado** (proibição de
   `docker compose` durante o bloco). O alvo existe e `make -n` prova que
   parseia. Falta provar que `app/seeds/` está na imagem publicada e que `uv`
   resolve no PATH do usuário do container. Uma rodada real é devida no
   primeiro `stack-up`.
   `docs/superpowers/plans/2026-08-05-phase-2c-order-and-tracking.md:237` já
   afirma que "A task B10 rodou `make services-seed`" — **falso nos dois
   pontos** (não rodou, e `products` não está populado). O bloco C não deve
   herdar isso como fato.

3. **`DeadlockDetectedError` de ~1/200 em contenção tripla**
   (PATCH + DELETE + POST no mesmo usuário) nas formas de pagamento. Causa
   medida: `_listar_metodos_com_lock` ordena por `is_default DESC, created_at`
   — coluna **mutável** — dentro de um `FOR UPDATE`, então transações com
   snapshots divergentes travam linhas em ordens diferentes, enquanto
   `apagar_metodo` trava primeiro a linha que apaga. Contido: 1000 iterações
   sem PATCH deram zero deadlocks, e a invariante de "um só default" nunca
   quebrou em nenhuma rodada. Correção candidata: ordenar só por
   `created_at`/`id`, checando antes se o "promove o mais antigo" de
   `apagar_metodo` não depende do termo `is_default DESC`.

4. ~~**O buraco de porte da §4**~~ — **fechado pela B12** em `63f8977`: os 9
   testes foram portados e as três propriedades sem guarda passaram a ter uma
   (§4). Não é mais uma pendência do corte.

5. **Nada foi provado em container, no granian, no Dockerfile ou pelo
   api-gateway** nesta branch (§3).

---

## 8. Estado da frota

A frota foi medida **duas vezes**, e a tabela abaixo é a segunda.

1. **No portão (`9ea4398`)**, quando o commerce tinha 177: `make services-test`
   e `make services-lint`, 8/8 alvos, exit 0, total **491**.
2. **Depois da B12**, pelo controlador da sessão, no commit `7496a5d`:
   `make services-test` de novo, na raiz do repositório. Cada linha da tabela
   abaixo é uma linha dessa saída — nenhuma é aritmética.

A própria B12 não re-rodou a frota (o brief dela proíbe `make services-test` /
`make services-lint` fleet-wide, porque `uv run` reescreve o `uv.lock` de
outros serviços). Ela re-rodou só o commerce, dentro de
`back-end/commerce-service/`:

```
uv run pytest -q                -> 187 passed
uv run ruff check .             -> All checks passed!
uv run ruff format --check .    -> 80 files already formatted
```

Todos os números da coluna "Agora" vêm da rodada 2:

| Serviço | Baseline (início do bloco B) | Agora | Δ |
|---|---|---|---|
| edu-common | 59 | 59 | 0 |
| api-gateway | 36 | 36 | 0 |
| auth-users | 61 | 61 | 0 |
| learning | 78 | 78 | 0 |
| **commerce** | **88** | **187** | **+99** |
| chatbot | 23 | 23 | 0 |
| notification | 24 | 24 | 0 |
| analytics | 33 | 33 | 0 |
| **total** | **402** | **501** | **+99** |

Os três `uv.lock` que a rodada reescreve (analytics, auth-users, chatbot) foram
revertidos; a árvore ficou limpa.

Nenhum serviço diminuiu. `ruff check` limpo nos oito no portão, e re-confirmado
no commerce na B12.

### Sync-check de schema (modelos × migrations)

Cinco bancos descartáveis (`syncchk_b11_*`), `alembic upgrade head` seguido de
`alembic revision --autogenerate`. **Nenhum banco de desenvolvimento foi
tocado.**

| Serviço | Revision gerada | Contagem de revisions antes/depois |
|---|---|---|
| commerce | `upgrade()` e `downgrade()` vazios | 8 / 8 |
| auth-users | vazios | 2 / 2 |
| learning | vazios | 2 / 2 |
| notification | vazios | 1 / 1 |
| analytics | vazios | 2 / 2 |

Os cinco arquivos gerados foram apagados e os cinco bancos descartados
(`SELECT datname FROM pg_database WHERE datname LIKE 'syncchk%'` → 0 linhas).

`grep -l compare_server_default */alembic/env.py | wc -l` = **5**, como o plano
previa.
