# Spec B — Parceiros, estoque e transportadora — Registro de execução

**Data:** 2026-09-08 e 2026-09-09
**Plano:** [`2026-09-08-spec-b-parceiros-estoque-transportadora.md`](2026-09-08-spec-b-parceiros-estoque-transportadora.md)
**Spec:** [`../specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md`](../specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md)
**Registro anterior:** [`2026-09-07-spec-a-corte-e-consolidacao-execution-record.md`](2026-09-07-spec-a-corte-e-consolidacao-execution-record.md)
**Branch:** `feat/spec-b-parceiros-estoque-transportadora`, 29 commits de
implementação sobre `0a082ea` (mais o commit do plano e o do `.gitignore`)

Este documento registra o que aconteceu quando o plano foi executado: onde ele
estava errado, o que foi decidido no lugar, e o que ficou por fazer. O plano
descreve a intenção; este arquivo descreve a execução.

Cada task foi implementada por um agente com contexto limpo, a partir de um
briefing extraído do plano, e revisada por um segundo agente contra o diff.
**Oito das treze tasks precisaram de rodada de correção**, e na maioria delas o
defeito encontrado não era do implementador: estava no código literal do
plano. As três lições do registro da spec A foram carregadas em todo dispatch,
e é por isso que este documento tem tantos achados — não porque a execução
correu pior, mas porque o mecanismo que os encontra funcionou. As tasks 4, 6, 7
e 9 fecharam com **zero findings** — e as quatro receberam no dispatch,
nomeados de antemão, os defeitos que as tasks anteriores tinham custado caro.

## O que foi entregue

| Task | Entrega | Commits |
|---|---|---|
| 1 | Schema da spec B: `origem_*` em `Fornecedor`, `sku`/`active` em `Product`, `estoque_minimo`, `estoque_ajustes`, `carriers`, `transportadora_id` em `Ocorrencia`, origem em `orders`. Revision `b1a2c3d4e5f6` | `fd4a45e` |
| 2 | CRUD de parceiros em `/partners`, mais `partners` e `carriers` no `SERVICE_MAP` do gateway | `7868da6`, `6b19a6f` |
| 3 | Estoque com trilha de auditoria: um núcleo atômico, duas portas | `c626ec7`, `4e06db7`, `da81c52`, `ba6a413` |
| 4 | Transportadoras em `/carriers` | `c1167ab` |
| 5 | Ocorrência de transportadora dentro do `Ocorrencia` existente | `0aace7f`, `b692af4`, `c2c673a` |
| 6 | CRUD admin de produto atrás de `/products` | `34d3448` |
| 7 | Catálogo filtrado por parceiro | `e98b8c6` |
| 8 | Regra de origem única no carrinho, com 409 exibível | `58ff0f9`, `4f70579` |
| 9 | Origem de expedição congelada no pedido | `122dfce` |
| 10 | Códigos de PIX e boleto emitidos pelo backend | `08100dc`, `e661219` |
| 11 | Seed dos dois parceiros e do catálogo do parceiro externo | `9bffca3`, `96bf0ee`, `2b80c31` |
| 12 | Flutter: seção de parceiros, 409 na tela, saída do mock de pagamento | `eaa50cc`, `6766e17`, `6a84105`, `9268b22` |
| 13 | `web-admin` falando com o gateway | `abf72f7`, `c608f4d`, `5185aa3`, `4355832` |
| 14 | Documentação, pendências e verificação de costura | este documento |

## Medição final

Medida do zero em 2026-09-09, depois do último commit de código, serviço a
serviço. **Nenhum número foi copiado de documento anterior.** O bloco de
baselines do plano tinha dois erros, e os dois estão corrigidos aqui: o
`flutter analyze` era **7** avisos `info`, não 6 (ver a decisão 16), e o plano
diz "os outros **cinco** serviços" antes de listar **seis**. Nenhum dos dois
mudou nada na execução; os dois teriam mudado se alguém tivesse "consertado"
até bater o número escrito.

| Alvo | Antes | Depois |
|---|---|---|
| api-gateway | 36 | **37** |
| auth-users-service | 72 | 72 |
| learning-service | 78 | 78 |
| commerce-service | 367 | **491** |
| chatbot-service | 37 | 37 |
| notification-service | 36 | 36 |
| analytics-service | 34 | 34 |
| packages/edu-common | 62 | 62 |
| **Total Python** | **722** | **847** |
| Flutter (`flutter test`) | 161 | **179** |
| Flutter (`flutter analyze`) | 7 `info`, exit 1 | 7 `info`, exit 1 |
| `web-admin` (`npm run build`) | exit 0, 3 avisos de budget SCSS | exit 0, 3 avisos de budget SCSS |

Os seis serviços que este plano não toca ficaram **exatamente** onde estavam.
Isso era o teste de costura mais barato disponível e ele passou.

`flutter analyze` continua devolvendo os mesmos sete avisos, nos mesmos
arquivos e nas mesmas linhas: `admin_scaffold.dart` (×2), `admin_widgets.dart`,
`logistics_api.dart`, `incident_resolution_screen.dart` (×2) e
`order_provider_test.dart`. **Nenhum está em arquivo que esta spec tocou.**

A suíte do commerce emite **um** `DeprecationWarning`, do Starlette:
`HTTP_422_UNPROCESSABLE_ENTITY` virou `HTTP_422_UNPROCESSABLE_CONTENT`. É da
biblioteca, não do código do projeto.

### As quatro verificações de costura que nenhuma task possuía

Rodadas na árvore final. As três primeiras têm que voltar **vazias**, e
voltaram:

1. Nome de parceiro em caminho de decisão (backend, app e painel, fora do seed
   e dos testes): vazio.
2. Gerador de código de pagamento no cliente Flutter
   (`_generatePixCode|_generateBoletoCode|BR.GOV.BCB.PIX`): vazio.
3. Referência à API Java no painel (`8080|/api/v1` em `web-admin/src` e no
   `proxy.conf.json`): vazio.
4. `docker compose -f back-end/docker-compose.yml config --quiet`: `compose ok`.

Mais duas de integração:

- Todo model novo está no `create_all` da suíte — `estoque_ajuste` e
  `transportadora` estão importados no `conftest.py`.
- Os onze primeiros segmentos de path do commerce
  (`admin`, `carriers`, `cart`, `delivery`, `health`, `occurrences`, `orders`,
  `partners`, `payment-methods`, `picking`, `products`) estão todos no
  `SERVICE_MAP` do gateway, **exceto `health`, que é interno**.

> Nota de método, para quem repetir isto: a medição de rotas **tem que sair do
> OpenAPI**, não de `app.routes`. Nesta versão do FastAPI cada `include_router`
> vira uma entrada `_IncludedRouter` com `path=None`, e iterar `app.routes`
> devolve `['docs', 'health', 'openapi.json', 'redoc']` — uma medição que diz
> "não há rota" sobre um serviço com 57 rotas. O `microservices.md` já
> registrava essa armadilha na §3; ela mordeu de novo aqui.

---

## Decisões tomadas durante a execução

Dezessete pontos precisaram de decisão depois que o plano começou a rodar.
Cada uma está registrada com o motivo e com o que custaria se estivesse errada.

### 1. O `and` e o `__import__` inline do teste da task 1 saem

`autor_id=fornecedor.id and __import__("uuid").UUID(int=1)` virou um
`import uuid` no topo e `autor_id=uuid.UUID(int=1)`. O `and` era ruído sem
efeito e o `__import__` inline é ilegível.

### 2. `LIMIT 1` sem `ORDER BY` sobre um filtro não-único — o defeito que apareceu em quatro tasks

Este é o achado central desta execução e merece a seção mais longa.

`Estoque` tem `UniqueConstraint("produto_id", "fornecedor_id")`. O **par** é
único; o `produto_id` sozinho **não é**. Um produto pode ser estocado por dois
fornecedores — e a própria task 7 do plano diz isso em prosa. Mas quatro
lugares do plano resolviam "de qual fornecedor é este produto" filtrando só
por `produto_id`:

| Onde | Forma no plano | Consequência |
|---|---|---|
| `services/estoque.py::obter_estoque_do_produto` (task 3) | `scalar_one_or_none()` | `MultipleResultsFound` ⇒ 500 no ajuste de estoque |
| `services/carrinho.py::_fornecedor_do_produto` (task 8) | `scalar_one_or_none()` | 500 em `POST /cart/items` |
| `services/carrinho.py::_origem_do_carrinho` (task 8) | `.limit(1)` **sem** `order_by` | resolve fornecedor diferente do anterior |
| `services/pedidos.py`, o mapa `vinculos` (task 9) | dict comprehension sem `order_by` | a **última** linha vence, seja lá qual |

As duas primeiras foram pegas no pre-flight, antes de qualquer dispatch. A
terceira **não foi** — ela tinha `.limit(1)`, o que fazia o `scalar_one_or_none`
parecer seguro, e passou por mim e pelo implementador. Quem a achou foi o
revisor da task 8, e ele a provou empiricamente contra o `commerce_test`:
`uq_produto_fornecedor` é índice composto, então um index scan com igualdade em
`produto_id` devolve na ordem da coluna final, `fornecedor_id`, e **não** de
`Estoque.id`. Com duas linhas inseridas de modo que as duas ordens fiquem
invertidas, a função devolvia um fornecedor diferente de
`_fornecedor_do_produto`. Consequência: 409 falso numa adição legítima do mesmo
parceiro, e no espelho disso, o carrinho misto que a task 8 existe para
impedir, aceito em silêncio.

A suíte estava verde porque as tabelas de teste são pequenas — sorte, não
garantia.

E aqui está a parte que fortalece o achado, medida pelo implementador durante o
fix: ele esperava precisar desligar `seqscan` para expor a divergência, e um
`EXPLAIN` mostrou que o Postgres **já escolhe Index Only Scan** sobre
`uq_produto_fornecedor` por padrão com uma tabela de duas linhas. A divergência
aparecia no plano **padrão**, sem forçar nada.

A quarta incidência eu achei lendo o brief da task 9 antes de despachar, e ali
o custo seria maior que nos outros três: o fornecedor escolhido vira
`supplier_id` e origem de expedição **gravados num registro histórico
permanente**, que a spec C lê e não recalcula.

**Invariante que ficou:** as quatro funções ordenam por `Estoque.id` e tomam a
primeira. Está escrito em comentário nas quatro, não só nos relatórios, e está
em [`../../back-end/partners-inventory-carriers.md`](../../back-end/partners-inventory-carriers.md).

Custo se errado: escolher o fornecedor de menor `id` quando há dois é
arbitrário — mas é determinístico, e nenhum caminho desta entrega cria o
segundo fornecedor.

### 3. `StatusPedido.EM_TRANSPORTE` não existe

O membro é `EM_TRANSITO`. O plano usava o nome errado em quatro lugares da
task 5. Custo se errado: nenhum — o `StrEnum` estouraria `AttributeError` na
coleta do teste.

### 4. `CarrierStatus` é `StrEnum`, não `(str, Enum)`

O código literal do plano reprova o lint do projeto (ruff `UP042`) e contradiz
o único idioma de enum de string usado no serviço.

### 5. A revision importa `UUID` do dialeto explicitamente

`sa.dialects.postgresql.UUID(...)` levanta `AttributeError` em runtime:
`sqlalchemy.dialects.postgresql` não é alcançável como atributo só com
`import sqlalchemy as sa`. Medido pelo implementador da task 1.

### 6. Os commits ficam com a atribuição de quem escreveu o código

O plano manda terminar cada mensagem com `Co-Authored-By: Claude Opus 5`. Os
implementadores rodaram em sonnet e aplicaram a própria atribuição, que é a
correta. Reescrever custaria um rebase da branch para corrigir uma linha de
crédito que já está certa.

### 7. Rota sem credencial devolve **403**, não 401

O plano copiou a convenção errada, e o texto literal se repetia nas tasks 4, 5
e 6. Verificado na árvore: `edu_common.deps.build_auth_deps` reserva 401 para
credencial **presente e inválida**. Um teste que assere o status errado passaria
a documentar um contrato que o serviço não tem.

### 8. Os dois buracos de autorização da task 2 viram fix round, não pendência

`PUT /partners/{id}` era admin-gated sem teste negativo, e `GET /partners/{id}`
prometia estar aberto a qualquer papel autenticado sem nunca ser exercido por
um. Deixar parqueado propagaria o buraco para as tasks 3, 4, 5 e 6, que usam o
mesmo molde de teste.

### 9. Um teste negativo **por rota**, não por grupo de rotas

Foi exatamente isso que o brief da task 2 errou. Passou a valer para toda task
seguinte que criasse rota gated por papel. Custo se errado: alguns testes
redundantes.

### 10. O `PATCH /admin/inventory/{id}/adjust` deve teste negativo nesta spec

O implementador da task 3 alegou que o guard é anterior à task. O revisor
concordou comigo contra ele, e deu o argumento melhor que o meu: **o poder do
handler cresceu**. Ele agora escreve linha de auditoria atribuída a
`user["sub"]`, então `user` deixou de ser parâmetro só de guarda e virou valor
consumido. Trocar `requer_papel("admin")` por `get_current_user` compilaria e
deixaria a suíte verde, liberando qualquer estudante autenticado a reescrever
estoque e forjar auditoria atribuída a si mesmo.

### 11. `fastapi.Query` entra no `extend-immutable-calls` do commerce

O B008 do ruff pula sozinho quando a anotação é um tipo imutável embutido (por
isso `limit: int = Query(...)` nunca precisou de nada), mas dispara para um
enum nosso — `status: CarrierStatus | None = Query(...)`. A alternativa era um
`# noqa` numa linha. Pedi ao revisor que **confirmasse a premissa** em vez de
aceitar meu raciocínio, e ele montou uma config baseline sem a entrada nova:
aparece exatamente um B008, na linha do enum. A premissa era verdadeira.

### 12. O nome da constante de tipo de ocorrência fica como o código escreveu

O plano chamou a constante produzida de `TIPOS_TRANSPORTADORA` no bloco
Interfaces e de `TipoOcorrenciaTransportadora` (um `Literal`) no passo da task.
O código seguiu o passo. Valores idênticos, `tipo` desconhecido dá 422, e o
painel consome isso por HTTP — risco de integração zero. **A documentação é que
estava errada, e a task 14 a acertou.**

### 13. O tie-break de `Estoque.id` vira invariante das quatro resolvedoras

Ver a decisão 2.

### 14. `CodigoPagamentoError` e o `except Exception` largo saem agora

Os dois existiam só porque o bloco Interfaces do plano os nomeou: `sha256`
sobre um `uuid.UUID` tipado não tem modo de falha, então nem a exceção nem o
`except` são alcançáveis. O revisor recomendou follow-up; discordei do
adiamento porque a task 14 é docs e costuras, não faxina, e código morto em
caminho de request é exatamente o que a revisão final encontraria de novo.
Um 500 honesto é melhor que um 502 que ninguém exercita.

Regra que ficou junto: a contagem tinha que ficar em **484** depois da
remoção — nenhum teste cobria os dois itens deletados, então se o número
andasse, outra coisa teria mudado. Não andou.

### 15. A docstring que citava o nome do parceiro é reescrita — a allow-list não

O teste de costura `test_no_partner_name_appears_in_a_decision_path`, que o
próprio plano manda escrever, **falhava** contra a árvore antes da task 11: a
docstring que a task 2 escreveu explicava a proibição **citando** ela, e a
citação continha o nome literal. Docstring não é caminho de decisão — o código
não violava a regra, o teste é que estava na forma certa e o texto errado.

**Alargar a allow-list para incluir `app/services/parceiros.py` foi proibido
explicitamente**: aquele arquivo é exatamente onde tal caminho de decisão seria
escrito, então isentá-lo destruiria o único propósito do teste. O implementador
trocou o nome por um placeholder, não mexeu na allow-list, e ainda achou de
brinde uma referência morta na mesma docstring — ela apontava para um nome de
teste que nunca existiu.

### 16. O baseline do `flutter analyze` é **7**, não 6

Medido durante a task 12, e reconfirmado do zero na task 14. O número 6 veio do
enunciado e do plano, copiado de uma medição anterior. Nenhum dos sete está em
arquivo que esta spec tocou, e a contagem é idêntica antes e depois de cada
task. Isto é **correção de baseline, não regressão** — e é a lição 1 do
registro da spec A acontecendo de novo, ao vivo.

O implementador da task 12 reportou 7 em vez de repetir o número esperado. Esse
é o comportamento certo, e vale registrar como tal: um implementador que
"conserta" até bater o número errado faz estrago.

### 17. A fiação do 409 até a tela é devida na task 12, não adiada

O implementador entregou a mensagem do 409 chegando verbatim em
`CartStore.errorMessage` — e sinalizou, com honestidade, que **nenhum widget lê
esse campo**: `CartStore.add()` é fire-and-forget e ninguém aguarda no call
site. O revisor confirmou a alegação.

Mensagem capturada com perfeição e renderizada em lugar nenhum não entrega "o
aluno vê a frase". A lacuna apareceria no smoke test manual como "o app não faz
nada quando misturo parceiros", que é o pior jeito possível de descobrir. O
implementador acertou em declarar em vez de inventar UI não testada; escopada e
testada, construiu. Custo: ~20 linhas em 3 arquivos, no idioma que o app já
usa.

---

## Os defeitos que nenhum teste da própria task teria pego

Cinco achados desta execução não seriam encontrados por nenhuma suíte da task
que os continha. Cada um vale um padrão.

### O identity map do SQLAlchemy anulando um `FOR UPDATE`

**Task 3, achado do implementador, não previsto pelo plano nem pelo dispatch.**

O código literal do brief lia a linha de estoque **sem** lock
(`obter_estoque_do_produto`) e depois a relia **com** lock dentro do núcleo, na
mesma sessão. O `FOR UPDATE` do Postgres esperava certo e devolvia a linha nova
— mas o identity map do SQLAlchemy, achando o id já carregado, devolvia a
instância **velha**, de antes do lock. A aritmética usava quantidade obsoleta e
um ajuste sumia: dois `+5` sobre `10` davam `15`.

Falhava de forma determinística em
`test_concurrent_deltas_do_not_lose_an_adjustment`. Corrigido com
`.execution_options(populate_existing=True)` nos dois `SELECT` travados, e
depois endurecido no fix round: `obter_estoque_do_produto` passou a devolver
`int` (o id), não a entidade, para que **nenhuma instância pré-lock entre na
sessão por aquele caminho**.

Este é exatamente o buraco que a regra 3 do `CLAUDE.md` existe para tapar, e
ele atravessou o plano inteiro sem ser visto. O lock estava lá. O lock estava
certo. E não funcionava.

### Dois testes de concorrência que passavam com o lock removido

**Tasks 5 e 8.**

Na task 5, mandei espelhar o rendezvous de um teste de concorrência que já
existia, com a exigência explícita de **confirmar que o teste novo falha com o
`with_for_update()` removido**. A primeira versão passava **5/5 sem o lock**. O
implementador não passou por cima: mediu o porquê — o `close` tem um `execute()`
só antes do commit, contra quatro do `resolve`, então a segunda leitura sem lock
não tem latência real suficiente para perder a corrida neste ambiente — e
corrigiu o harness com um `asyncio.sleep(0.05)` depois do sinal de rendezvous,
que é no-op quando o lock existe, porque o segundo request fica bloqueado no
Postgres e não no sleep. Reverificou: 5/5 falha sem o lock, 5/5 passa com ele.

Na task 8, a exigência de falsificação foi carregada no dispatch **com o
precedente da task 5 citado por extenso**, e o implementador trocou o
`asyncio.gather()` simples do brief por um rendezvous com spy antes mesmo de
medir. O revisor reproduziu a falsificação por conta própria.

O revisor da task 3 fez o mesmo por iniciativa própria: **mutation-testou** o
lock em vez de acreditar no relatório, neutralizando `with_for_update()` e, em
separado, o `populate_existing` — as duas mutações mataram o teste com
`assert 15 == 20`.

**Um teste de concorrência que passa sem o lock certifica o que nunca checou.**
É pior que nenhum teste, porque compra silêncio.

### A task que "não tocou em arquivo nenhum" e mudou o comportamento de um endpoint

**Task 5, achado do revisor, reproduzido ao vivo contra o banco de teste.**

`POST /occurrences/{id}/resolve` é a rota do **aluno**, e a task 5 tem diff
vazio em `tests/test_occurrences_routes.py` e no handler. Mesmo assim ela mudou
o comportamento dele: no instante em que `CarrierOccurrence` e `Ocorrencia`
passaram a dividir a mesma tabela, o `/resolve` do aluno passou a agir sobre
ocorrência de transportadora.

O admin abria um `DANO` no pedido do aluno; o aluno chamava `/resolve` com
`cancelar_pedido` e tomava **200** — o pedido ia a `CANCELADO`, a ocorrência do
admin ficava `RESOLVIDA`, e o `/close` admin-only que a task existe para criar
era contornado inteiro. Segundo buraco: ocorrência `ATRASO_ENTREGA` aberta pelo
admin não tem `nova_data_sugerida`, e o aluno aceitando "nova data" zerava
`estimated_delivery_at` para `NULL` em silêncio.

É o padrão 3 do registro da spec A — a revisão por task não vê as costuras. Só
que **desta vez a costura foi vista**, porque o dispatch mandou olhar a
fronteira **no diff** em vez de aceitar "não toquei no arquivo". Campo opcional
novo que muda a forma de uma resposta existente conta como mudança; enum
alargado que faz endpoint antigo aceitar valor que antes recusava também.

O guard que fechou os dois buracos foi provado não-largo-demais pelo lado
certo: `transportadora_id` é setado num único ponto do código, a rota admin, e
nem `/stock-shortage` nem `/delivery-delay` o setam.

### Um teste de idempotência que nunca exercitava o laço que interessa

**Task 11, achado do revisor — o que eu mandei procurar.**

`test_the_seed_is_idempotent_over_two_full_passes` chamava `seed_parceiros`
duas vezes, mas nunca chamava `seed_products` antes. Sem produto órfão, o laço
de **adoção** não era exercitado por ele; e os dois testes que exercitam adoção
chamavam o seed uma vez só. Resultado: a idempotência da adoção tinha sido
provada por dois scripts descartáveis — o do implementador e o do revisor — e
nenhum dos dois existia mais.

"O seed adotou o mesmo produto duas vezes" é justo a falha que ficaria calada
no banco até um filtro de parceiro ou uma origem de pedido sair errada.

O fix estendeu o teste existente com uma terceira chamada. O implementador
verificou a própria correção injetando o bug de re-adoção de propósito, e
reportou com honestidade uma distinção que ninguém teria cobrado: nesse caso o
teste falha por `UniqueViolationError` durante a terceira chamada, não pelo
`assert` comparando valores. Efeito prático igual; a distinção é justa.

### Uma tela que anunciava um total que nunca mediu

**Task 13, revisão feita por opus, oito findings.**

O painel passou a paginar no cliente sobre um array de no máximo 200 linhas
carregado com `offset` fixo em 0. Com 500 linhas de estoque, o usuário via as
100 primeiras, um rodapé dizendo "de 100 resultados", um card "TOTAL DE
PRODUTOS 100", e uma busca por um produto da linha #300 devolvendo "Nenhum
produto encontrado" — falso negativo, sem nada na tela avisando que a busca
cobriu uma fatia. O pager em si não mentia; quem mentia eram os contadores, os
cards e o resultado vazio da busca. O pior era "ESTOQUE BAIXO": subcontagem lê
para o operador como "não falta nada".

O segundo finding alto tinha uma fronteira que ninguém tinha notado: o join de
nome de produto quebrava a partir de **101 produtos**, não de 101 linhas de
estoque, porque `/products` tem teto de 100 no servidor e ordena por **nome**,
enquanto estoque ordena por **id** — as duas janelas não têm relação nenhuma.

O terceiro: o modal de ajuste preenchia o motivo da auditoria pelo usuário. O
`reasonPreset` começava com um preset real, então o `required` já nascia
satisfeito e um admin gravava "Recebimento de lote" sem ter escolhido nada. O
backend tornou `motivo` obrigatório justamente para a linha registrar decisão
humana; default pré-selecionado transforma isso numa constante.

**Escolher opus para esta revisão se pagou.** Era a maior superfície de
integração do plano e a única task sem suíte de teste — o review era o gate mais
forte que aquele código ia receber. O revisor conferiu cada interface declarada
**campo a campo** contra o schema Pydantic, que é exatamente o que o build AOT
não pega: um tipo declarado errado compila feliz.

---

## O que ficou registrado como dívida

Nenhum destes é bug a corrigir; todos foram medidos e deixados de propósito. A
lista completa, com o detalhe de cada um, está em
[`../../back-end/partners-inventory-carriers.md`](../../back-end/partners-inventory-carriers.md),
§10, e as que um operador encontra no dia da apresentação estão em
[`../../smoke-test.md`](../../smoke-test.md).

**Backend**

- `GET /admin/inventory` e `GET /admin/orders` devolvem lista pura, sem
  `total`, ao contrário de toda listagem desta spec. Convenção pré-existente
  do router de admin, anterior à spec B. O painel se adapta paginando até vir
  uma página curta.
- `GET /admin/inventory` não tem `search` nem `lowStock`.
- Não existe rota de leitura global de `estoque_ajustes` — só por produto.
- `price` não tem `decimal_places`: três casas são aceitas e o Postgres
  arredonda.
- O `search` de `/carriers` passa `%` e `_` para o `ILIKE` como curinga
  literal. Parâmetro bound — não é injeção, é comportamento de busca. O painel
  os escapa antes de mandar.
- Os seis produtos próprios ficam com `sku` vazio até alguém editá-los.
- A suíte monta o schema com `create_all` e não roda alembic. A revision desta
  spec é a **única** da cadeia com prova de aplicação registrada.

**Painel**

- Não tem suíte de teste (decisão D11); a verificação é `npm run build`.
- Tetos de 100 no servidor truncam três consumidores que carregam uma página
  só: o seletor de parceiro do formulário de produto, o CSV de transportadoras
  e o filtro de transportadora das ocorrências. As telas paginam e veem tudo.
- O aviso de truncamento do estoque tem um falso positivo em exatamente 2000
  linhas, porque não há `total` para distinguir "teto batido" de "o teto
  coincidiu com o fim".
- "OCORRÊNCIAS ABERTAS" conta `FALTA_ESTOQUE` também: o backend não tem filtro
  "só de transportadora".
- "PARCEIROS ATIVOS" e "TRANSPORTADORAS ATIVAS" são totais atuais sob um
  cabeçalho que diz "(últimos N dias)".
- O dashboard perdeu onze campos que não têm fonte no backend — **nenhum foi
  inventado no cliente**.
- `rating` da transportadora nasce `0` porque o formulário não o coleta.
- `dashboard.component.scss` tem regras órfãs para marcação removida; é por
  isso que o aviso de budget dele não diminuiu.
- Não há refresh de token: a sessão expira com o access token.

**App**

- `AddToCartButton` agenda um `Future.delayed(1200ms)` e nunca o cancela no
  `dispose()`. Bug latente **pré-existente**, descoberto porque o primeiro
  widget test que apertou aquele botão falhou no teardown com "A Timer is still
  pending". Contornado pelo lado do teste; a correção é uma linha (guardar o
  `Timer` e cancelá-lo). Follow-up explícito, não bloqueio.

---

## O que este plano ensinou sobre planos

As três lições do registro da spec A foram carregadas em todo dispatch, e as
três incidiram de novo. Estas quatro são o que a spec B acrescenta.

**Um número medido envelhece — inclusive um que o registro anterior mandou
medir.** O `flutter analyze` era 6 no enunciado, 6 no plano, e **7** na árvore.
Ninguém errou de propósito: o número foi copiado de uma medição que estava
certa quando foi feita. A defesa que funcionou não foi um número melhor, foi um
critério **relativo** — "os mesmos avisos, nos mesmos arquivos, antes e depois"
— mais um implementador que reportou o que mediu em vez do que era esperado
dele.

**Um plano pode conter o mesmo defeito quatro vezes, e nas quatro ele parece
diferente.** O `LIMIT 1` sem `ORDER BY` apareceu como `scalar_one_or_none()` em
duas tasks, como `.limit(1)` aparentemente seguro numa terceira, e como um dict
comprehension numa quarta. O pre-flight pegou duas. As outras duas foram pegas
por um revisor e por mim, lendo um brief. Nenhuma teria sido pega pela suíte da
própria task, porque **as tabelas de teste são pequenas demais para o planner
escolher o caminho que expõe o problema** — e, quando escolhe, escolhe o
errado por ser mais barato.

Quando um defeito reaparece, a correção não é corrigir as ocorrências: é
**nomear a invariante e escrevê-la no código**, para que a quinta ocorrência
tenha onde esbarrar.

**Falsificação é obrigação, não zelo.** Dois testes de concorrência desta
execução passavam com o lock removido. Os dois só foram descobertos porque o
dispatch exigiu, por escrito, que o implementador rodasse o teste **com a
proteção neutralizada** e reportasse o resultado. Um deles era um teste que eu
mesmo tinha mandado escrever, no molde de um que já existia e funcionava.
Nenhuma revisão de código teria visto: o teste era bonito, o lock estava lá, e
o verde era falso.

**Vários defeitos só apareceram porque alguém rodou o código em vez de lê-lo.**
O `/resolve` do aluno agindo sobre ocorrência de transportadora, os limites
numéricos que davam 500 em vez de 422, a corrida de `sku` duplicado, a
divergência do planner entre duas resolvedoras de fornecedor — todos foram
reproduzidos ao vivo, contra o Postgres de teste, por um revisor que preferiu
probar a acreditar no relatório. Um revisor chegou a montar uma config de lint
baseline para verificar se a premissa de uma decisão minha era verdadeira (era).

O dispatch que produz isso é o que diz **o que provar**, não o que ler:
"diga o que um usuário com 500 linhas de estoque VÊ", "responda se este teste
passaria com o lock removido", "prove o snapshot mudando a origem depois",
"confirme a premissa em vez de aceitar meu raciocínio". Limite declarado que
não é alcançado não prova nada.
