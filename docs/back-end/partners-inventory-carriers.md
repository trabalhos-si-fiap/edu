# Parceiros, estoque auditado e transportadoras (spec B)

O que a spec B (2026-09-08) acrescentou ao `commerce-service`: o parceiro
comercial, a origem de expedição, a trilha de auditoria de estoque, a
transportadora, a ocorrência de transportadora e os códigos de pagamento
emitidos pelo servidor.

**Nenhum serviço novo.** Tudo vive dentro do `commerce-service`, sobre
entidades que já existiam. O gateway ganhou duas entradas
(`partners`, `carriers`); o `web-admin` deixou de falar com a API Java e
passou a falar com o gateway.

Migration única: `b1a2c3d4e5f6` (`spec_b_schema`), descendente de
`c90210e9965c`. Aditiva — colunas com `server_default` e duas tabelas novas.

---

## 1. `Fornecedor` virou o parceiro

A tabela `fornecedores` já existia como cadastro de fornecedor de estoque.
A spec B deu cliente a ela (o app Flutter e o painel Angular) sem renomear a
tabela: o rename custaria uma revision destrutiva que a spec não pede. **A
tabela é `fornecedores`; a rota é `/partners`.** Isso é decisão registrada,
não esquecimento.

O que a spec B acrescentou (`app/models/produto.py::Fornecedor`):

| Coluna | Tipo | Por quê |
|---|---|---|
| `origem_rotulo` | `String(120)`, NOT NULL, default `''` | O rótulo humano da origem de expedição ("Cajamar, SP"). É o único campo de origem que sobe para o app. |
| `origem_lat` | `Numeric(9, 6)`, nullable | Latitude. `Numeric`, não `Float`: 6 casas dão ~11 cm, e a spec C lê estas colunas para montar rota. `Float` acumularia erro num valor que atravessa JSON duas vezes. |
| `origem_lng` | `Numeric(9, 6)`, nullable | Longitude, mesmo critério. |

`ativo` já existia e passou a ser o **interruptor da seção de parceiros do
app**: `GET /partners?active=true` só devolve ativos, e desativar um parceiro
no painel esvazia a seção do app sem recompilar nada.

**Não existe caminho especial para "produto sem parceiro".** Os seis produtos
próprios pertencem a um fornecedor chamado `Edu`, criado pelo seed como
qualquer outro. Um `if` por nome de parceiro é proibido e testado — ver §8.

**`Edu` é semeado com `ativo=False`, de propósito** (revisão final de branch,
finding 5). Ele é o fornecedor da própria loja, não uma vitrine de parceiro:
ativo, a seção de parceiros do app renderizava um bloco `Edu` repetindo os
seis produtos que a grade principal já mostra, mais um bloco `Leroy`
repetindo os outros quatro — dez produtos, vinte cards, onde a spec previa
"uma lista de um elemento". Desativá-lo **não** tira origem de pedido nenhum:
a origem resolve por `Estoque → Fornecedor` sem olhar `ativo`. A consequência
para o painel está na §10 (o seletor de fornecedor pede `active=false`, que
no backend significa "todos").

## 2. Um produto pertence a um parceiro **através do estoque**

Não existe `products.fornecedor_id`. A travessia é sempre
`Product → Estoque → Fornecedor`, e `estoque` tem
`UniqueConstraint("produto_id", "fornecedor_id")` — o **par** é único, o
produto **não**. Um mesmo produto pode ser estocado por dois fornecedores.

Essa é a fonte da armadilha mais recorrente desta entrega. Quatro funções
resolvem "de qual parceiro é este produto", e **as quatro precisam concordar**:

| Função | Arquivo |
|---|---|
| `obter_estoque_do_produto` | `app/services/estoque.py` |
| `_fornecedor_do_produto` | `app/services/carrinho.py` |
| `_origem_do_carrinho` | `app/services/carrinho.py` |
| o mapa `vinculos` da criação de pedido | `app/services/pedidos.py` |

**Invariante:** todas ordenam por `Estoque.id` e tomam a primeira linha — o
fornecedor de menor `Estoque.id` vence, sempre, independente do plano que o
Postgres escolher. Sem o `ORDER BY`, um `LIMIT 1` devolve o que o índice
`uq_produto_fornecedor` entregar (ordenado por `fornecedor_id`), e duas
funções podem discordar sobre o mesmo produto — o que produz 409 falso no
carrinho num caso e carrinho misto aceito em silêncio no espelho dele.
`scalar_one_or_none()` sobre um filtro só por `produto_id` levanta
`MultipleResultsFound` (500) no mesmo cenário.

Quem acrescentar uma quinta resolvedora tem que repetir o `order_by(Estoque.id)`.

O filtro de catálogo por parceiro (`GET /products?partner_id=`) usa
`WHERE products.id IN (subquery)`, **não** um `JOIN` no `FROM` externo: `IN`
não multiplica a linha externa, então um produto com dois fornecedores aparece
uma vez só e o `total` da paginação não conta duas vezes.

Parceiro inativo ou inexistente devolve **200 com lista vazia**, nunca 404 —
não existe branch de existência de parceiro no router nem no serviço. A UI
renderiza "sem produtos".

## 3. A regra de origem única do carrinho, e por que ela vive sob o lock

Um pedido sai de **uma** origem. Carrinho misto é proibido por decisão da spec,
não adiado: a spec C simula a rota de entrega a partir da origem, e um carrinho
misto produziria um pedido sem origem definida.

`POST /cart/items` com um item de outro parceiro devolve **409** com
`detail` igual a `CarrinhoOrigemMistaError.MENSAGEM`
(`app/exceptions.py`):

> Seu carrinho já tem itens de outro parceiro. Finalize ou esvazie o carrinho
> antes de misturar.

A frase mora no backend e o app a exibe **verbatim**, sem guardar cópia. Ela
tem um dono só. O teste do SnackBar no Flutter assere contra a string que o
409 mockado devolve, não contra uma constante Dart — de propósito.

**A checagem roda DENTRO do lock de linha do carrinho**
(`select(Cart.id).where(...).with_for_update()`), e a ordem importa: fora do
lock, duas adições simultâneas leem um carrinho vazio, ambas concluem "não há
origem ainda", e ambas gravam — carrinho misto sem nenhum erro aparecer. É a
regra 3 do `CLAUDE.md`, e o teste de concorrência que a cobre **falha com o
`with_for_update()` removido** (verificado por mutação, não presumido).

## 4. Estoque auditado: um núcleo de escrita, duas portas

`estoque_ajustes` (`app/models/estoque_ajuste.py`) é o porte de
`InventoryAdjustment` do Java. Guarda `quantidade_anterior` e
`quantidade_nova`, **não** o delta: o delta é `nova - anterior`, e gravá-lo
criaria uma terceira fonte da verdade para o mesmo fato. O schema o expõe como
campo calculado.

`motivo` é obrigatório (`String(300)`, NOT NULL) e é **stripado antes de
descer para o serviço** — uma auditoria com espaço à esquerda ou com três
espaços por motivo não registra decisão humana nenhuma. `autor_id` é o `sub`
do JWT, sem FK: o dono do usuário é o `auth-users-service`, com banco próprio.
O FK para `estoque` **não** tem `ondelete`, de propósito: uma linha de estoque
apagada não pode levar sua auditoria junto.

`app/services/estoque.py` tem **um** núcleo de escrita e **duas portas**:

- `aplicar_ajuste(..., delta=...)` — porta de delta, servida por
  `POST /products/{id}/stock-adjustments`.
- `definir_quantidade(..., quantidade=...)` — porta absoluta, servida por
  `PATCH /admin/inventory/{estoque_id}/adjust`. Converte para delta **dentro
  do mesmo lock** e delega.

As duas existem porque o painel manda valor absoluto e a spec pede uma rota de
delta. Duplicar o caminho de escrita duplicaria o lock e a regra de saldo
negativo.

Três coisas que não são ornamento:

1. **`with_for_update()`.** Com delta, o read→write é real: sem o lock, dois
   `+5` concorrentes sobre `10` produzem `15` e um lote some.
2. **`execution_options(populate_existing=True)`.** Sem ele, o `FOR UPDATE`
   do Postgres espera certo, mas o identity map do SQLAlchemy devolve a
   instância **de antes do lock** — a aritmética usa quantidade obsoleta e um
   ajuste desaparece. Foi medido: o teste de concorrência falhava de forma
   determinística. `obter_estoque_do_produto` devolve `int` (o id da linha),
   não a entidade, justamente para nenhuma instância pré-lock entrar na sessão
   por aquele caminho.
3. **Um `commit()` só.** O `UPDATE` do estoque e o `INSERT` da auditoria sobem
   juntos ou não sobem. Saldo negativo levanta **antes** de qualquer escrita.

Leitura da trilha: `GET /products/{id}/stock-adjustments`, paginada, admin.

## 5. Transportadora

`carriers` (`app/models/transportadora.py`) é o porte de `Carrier.java`, em
**inglês** — tabela e colunas — porque nasce com dois clientes (o painel e a
rota `/carriers`). Larguras copiadas do Java: `name` 150, `location` 150,
`email` 254, `status` 20, `rating` `Numeric(2,1)`, `sla_percentage`
`Numeric(5,2)`.

`CarrierStatus` é um `StrEnum` com `ACTIVE`/`INACTIVE` — enum de texto, não
booleano, porque o Java já modelava mais de dois estados possíveis. A coluna
guarda o `.value`.

**Ocorrência de transportadora não virou tabela nova.** `CarrierOccurrence` do
Java foi reconciliado dentro do `Ocorrencia` que já existia: a transportadora é
uma **dimensão** da ocorrência (`ocorrencias.transportadora_id`, nullable),
não um segundo dono. `pedido_id` continua NOT NULL — toda ocorrência é de um
pedido.

Os tipos: `FALTA_ESTOQUE` e `ATRASO_ENTREGA` já existiam;
`DANO`, `FALHA_ENTREGA` e `OUTRO` chegaram com a spec B. O `DELIVERY_DELAY` do
Java é o `ATRASO_ENTREGA` daqui, e por isso não virou um sexto valor. O
`Literal` que o schema aceita em `POST /occurrences/carrier` chama-se
`TipoOcorrenciaTransportadora` (`app/schemas/ocorrencia.py`) e vale
`ATRASO_ENTREGA | DANO | FALHA_ENTREGA | OUTRO`.

> **Nota de documentação.** O plano da spec B nomeou essa constante
> `TIPOS_TRANSPORTADORA` no bloco Interfaces e `TipoOcorrenciaTransportadora`
> no passo da task. O código seguiu o passo. Os valores são idênticos, um
> `tipo` desconhecido dá 422, e o painel consome isso por HTTP — risco de
> integração zero. O nome correto é `TipoOcorrenciaTransportadora`.

**A costura que essa reconciliação abriu, e que foi fechada:** no instante em
que os dois modelos passaram a dividir a mesma tabela, o
`POST /occurrences/{id}/resolve` **do aluno** — que ninguém tocou — passou a
agir sobre ocorrência de transportadora. Um admin abria um `DANO` no pedido do
aluno, o aluno chamava `/resolve` com `cancelar_pedido` e tomava 200,
contornando inteiro o `/close` admin-only. Hoje existe um guard em
`app/routers/ocorrencias.py`, logo depois da checagem de posse e **antes** do
dispatch de `resolucao`, que recusa os quatro ramos de uma vez quando
`transportadora_id` está preenchido. Ele não alcança fluxo legítimo do aluno:
`transportadora_id` é setado num único ponto do código, a rota admin de
criação; nem `/stock-shortage` nem `/delivery-delay` o setam.

O fechamento (`POST /occurrences/{id}/close`) é admin-only e lê a ocorrência
sob `with_for_update()` — dois admins fechando a mesma ocorrência ao mesmo
tempo não gravam duas vezes.

## 6. Códigos de pagamento — **não é pagamento real**

`app/services/codigos_pagamento.py` emite o código copia-e-cola de PIX e a
linha digitável do boleto.

> **NÃO É INTEGRAÇÃO COM PROVEDOR DE PAGAMENTO.** Nenhum banco, nenhuma API,
> nenhum dinheiro. O payload tem a **forma** de um EMV de PIX e a linha tem a
> **forma** de uma linha digitável, e nenhum dos dois é pagável em lugar
> nenhum. O CRC `6304ABCD` do fim do EMV é fixo e falso.

É o mesmo algoritmo que rodava dentro do app Flutter
(`checkout_screen.dart::_generatePixCode` e `::_generateBoletoCode`), movido
para onde o dado nasce. O que **mudou**: o identificador é derivado do
`order_id` por `sha256`, em vez de sorteado por `Random()`. O cliente antigo
produzia um código diferente a cada chamada — o aluno que fechasse e reabrisse
a caixa de diálogo recebia outro código do que já tinha copiado. Derivar do
pedido conserta isso e torna a rota **idempotente por construção**: chamar
duas vezes devolve a mesma string e nada é gravado.

O `sha256` não é segredo, não é assinatura e não protege nada — é só uma função
determinística de UUID para alfabeto. Por isso **não** usa `hmac` nem chave, e
usa `usedforsecurity=False` para dizer isso a quem lê (e ao ruff `S324`).

`POST /orders/{order_id}/confirm-payment` devolve
`{order_id, payment_method, payment_code}`. Cartão devolve `payment_code:
null` — não há nada para copiar, e devolver string vazia faria a tela abrir uma
caixa de diálogo vazia.

O controle de acesso não é gate de papel: é **filtro por dono** dentro de
`services.buscar_pedido`, que reaproveita `_buscar_com_itens`, o único lugar
que sabe filtrar pedido por dono. Pedido de outro aluno cai no mesmo 404 que
pedido inexistente, sem revelar qual dos dois é.

## 7. A origem congelada no pedido

`orders` ganhou `supplier_id`, `origem_rotulo`, `origem_lat` e `origem_lng`.
São **snapshot**, não referência viva: mudar a origem do parceiro depois não
move nenhum pedido já criado. A spec C lê essas colunas para montar rota e
não as recalcula.

Carrinho sem nenhuma linha de estoque produz pedido com as quatro colunas
nulas, 201 — não é caminho de erro.

## 8. A proibição do nome de parceiro

**A string `leroy` só pode aparecer em dado de seed.** Nunca em caminho de
decisão, nem no backend, nem no app, nem no painel. Quem decide se a seção do
app aparece é `fornecedores.ativo`.

Isso é testado: `test_no_partner_name_appears_in_a_decision_path` varre `app/`
com uma allow-list de exatamente um arquivo (`app/seeds/parceiros.py`).
**Alargar a allow-list para incluir `app/services/parceiros.py` destruiria o
propósito do teste** — aquele arquivo é exatamente onde tal caminho de decisão
seria escrito.

O mesmo grep, estendido ao Flutter e ao Angular, é verificação de costura da
task 14 e tem que voltar vazio.

## 9. Rotas novas

Todas atrás do gateway em `/api/<prefixo>/...`. Sem credencial: **403**
(credencial presente e inválida é que dá 401). Toda listagem devolve
`{items, total, limit, offset}` — exceto `GET /admin/inventory` e
`GET /admin/orders`, ver §10.

| Método e rota | Acesso | O que faz |
|---|---|---|
| `GET /partners` | autenticado | Lista parceiros. `active=true` filtra ativos. `limit` ≤ 100. |
| `GET /partners/{id}` | autenticado | Detalhe. Aberto a qualquer papel, de propósito — o app o consome. |
| `POST /partners` | admin | Cria parceiro com origem. |
| `PUT /partners/{id}` | admin | Atualiza parceiro e origem. |
| `GET /products?partner_id=` | autenticado | Catálogo filtrado por parceiro. Parceiro inativo/inexistente ⇒ 200 com lista vazia. |
| `GET /products?include_inactive=true` | admin | Escotilha do painel: inclui produto com `active = false`. Papel errado ⇒ 403. |
| `POST /cart/items` (produto inativo) | dono do carrinho | **404**, a mesma resposta de produto inexistente. Nenhuma linha de carrinho é criada. |
| `POST /products` | admin | Cria produto. Exige `fornecedor_id` — a linha de estoque nasce na mesma transação. |
| `PUT /products/{id}` | admin | Atualiza produto. **Não** toca estoque. |
| `POST /products/{id}/stock-adjustments` | admin | Ajuste por **delta**, com `motivo`. Grava a auditoria. |
| `GET /products/{id}/stock-adjustments` | admin | Trilha de auditoria do produto, paginada. |
| `PATCH /admin/inventory/{estoque_id}/adjust` | admin | Ajuste **absoluto** (`quantidade` + `motivo` na query). O id do path é o do **estoque**, não do produto. |
| `GET /carriers` | admin | Lista transportadoras. Filtros `search` e `status`. `limit` ≤ 100. |
| `GET /carriers/{id}` | admin | Detalhe. |
| `POST /carriers` | admin | Cria transportadora. |
| `PUT /carriers/{id}` | admin | Atualiza transportadora. |
| `PATCH /carriers/{id}/status` | admin | `ACTIVE` ⇄ `INACTIVE`. |
| `GET /occurrences` | admin | Toda ocorrência, com ou sem transportadora. Filtros `carrier_id`, `tipo`, `status`. `limit` ≤ 100. |
| `POST /occurrences/carrier` | admin | Abre ocorrência de transportadora sobre um pedido. |
| `POST /occurrences/{id}/close` | admin | Fecha sem lógica de substituição. Sob lock de linha. |
| `POST /orders/{id}/confirm-payment` | dono do pedido | Devolve o código de PIX/boleto. Idempotente. |

Três regras valem para a superfície inteira que esta spec acrescentou, e
foram fechadas na revisão final de branch:

- **Produto inativo não aparece e não é comprável.** `products.active` era
  escrito, exibido e lido por nada. Agora `GET /products` filtra
  `active IS TRUE` no catálogo E no filtro por parceiro, `POST /cart/items`
  recusa um produto inativo com **404** (a mesma forma que produto
  inexistente — para o cliente, o que saiu da vitrine não está no catálogo, e
  reusar o erro existente evita uma quinta forma), e `POST /orders/{id}/rebuy`
  o **pula** com o `continue` que já pulava o descontinuado, devolvendo ao
  aluno o resto do pedido. `include_inactive=true` é do painel e exige
  `admin`. O que a regra NÃO faz é retroativo — §10.
- **Todo id inteiro é `app.ids.Int32Id`** (`ge=1, le=2_147_483_647`). Um id
  fora da faixa chegava no asyncpg e virava `DataError` — 500 onde cabe 422.
  A classe foi corrigida ponto a ponto três vezes e deixada aberta em nove
  sites; o alias é o que impede a décima. Quem acrescentar rota com id
  inteiro anota `Int32Id` e herda a faixa.
- **`detail` exibível é em português** nas rotas que esta spec criou —
  "Parceiro não encontrado", "Transportadora não encontrada", "Registro de
  estoque não encontrado". É o que os dois clientes mostram a usuário
  brasileiro, e o que `CarrinhoOrigemMistaError.MENSAGEM` já fazia. Rotas
  herdadas não foram varridas (§10).

`SkuDuplicadoError` ⇒ **409**. `products.sku` tem índice único **parcial**
(`WHERE sku <> ''`): dois produtos com `sku` vazio são legais, e só `sku`
não-vazio repetido é recusado. A recusa sai do `IntegrityError` do próprio
`INSERT`, sem pré-check `SELECT` — o índice é a única fonte da verdade e não
existe janela entre checar e inserir.

## 10. Limitações conhecidas

Nenhuma é regressão desta entrega; cada uma foi medida e deixada de propósito.

### Backend

- **`GET /admin/inventory` e `GET /admin/orders` devolvem lista pura**, sem
  `total`, ao contrário de todas as listagens desta spec. São paginadas de
  verdade (`limit` ≤ 200, `offset` ≥ 0), mas o cliente não tem como saber
  quantas linhas existem. É convenção pré-existente do router de admin,
  anterior à spec B. O painel se adapta paginando até vir uma página curta.
- **`GET /admin/inventory` não tem `search` nem `lowStock`.** O painel filtra
  no cliente sobre o que carregou.
- **Não existe rota de leitura global de `estoque_ajustes`** — só por produto.
- **`price` não tem restrição de casas decimais.** `"10.999"` é aceito e o
  Postgres arredonda para `11.00`. O formulário do painel arredonda e escreve
  o valor arredondado de volta no campo; o app Flutter não cria produtos.
- **O `search` de `/carriers` passa `%` e `_` para o `ILIKE` como curinga
  literal.** É parâmetro bound — não é injeção, é comportamento de busca. O
  painel escapa os dois antes de mandar, para uma busca por "50%" não casar
  com tudo.
- **Os seis produtos próprios ficam com `sku` vazio** até alguém editá-los. O
  índice único é parcial justamente por isso.
- **A suíte monta o schema com `create_all` e não roda alembic.** A revision
  da spec B é a única desta cadeia com prova de aplicação registrada
  (`upgrade` do zero, `alembic current`, `\d` das sete tabelas e round-trip de
  `downgrade -1`, contra `commerce_test`).
- **Os produtos da Leroy continuam na grade principal do app.**
  `GET /products` sem filtro devolve o catálogo inteiro, `Edu` e Leroy
  juntos, e a seção de parceiros mostra os da Leroy uma segunda vez logo
  abaixo. Semear `Edu` inativo tirou a duplicação de BLOCO (a seção agora tem
  um elemento só, como a spec previa); se a grade principal deveria ou não
  se restringir ao catálogo próprio é outra pergunta, e ela fica em aberto —
  decisão explícita, não esquecimento.
- **Carrinho e pedido já existentes sobrevivem à desativação do produto, de
  propósito.** A regra do `active` é *prospectiva*: `POST /cart/items` recusa
  um produto inativo (404, mesma forma que produto inexistente) e a recompra o
  pula como pula o descontinuado, mas nada é retroativo — um carrinho montado
  antes da desativação mantém o item e fecha o pedido, e um pedido passado
  continua listando o item com que foi feito. Varrer carrinho alheio ou
  reescrever histórico exigiria decidir estorno e estoque, e ninguém pediu
  isso. Ver §9 e `tests/test_inactive_product_rule.py`.
- **As rotas anteriores à spec B continuam respondendo em inglês.**
  `GET /products/{id}` e `POST /cart/items` devolvem `"Product not found"`.
  Só a superfície nova foi alinhada para o português; varrer o herdado é uma
  mudança maior do que esta rodada de correção deveria carregar.
- **Um `DeprecationWarning` do Starlette** aparece na suíte do commerce:
  `HTTP_422_UNPROCESSABLE_ENTITY` foi renomeado para
  `HTTP_422_UNPROCESSABLE_CONTENT`. É a biblioteca, não o código do projeto.

### Painel (`web-admin`)

- **Não existe suíte de teste**, e a spec B não criou uma. A verificação é
  `npm install && npm run build` — o build AOT faz type-check de template, que
  é o que pega mudança de forma de payload. O baseline é exit 0 com **três**
  avisos de budget SCSS (`products-stock`, `dashboard`, `carriers`).
- **Tetos de 100 no servidor.** `/partners`, `/products`, `/carriers` e
  `/occurrences` travam `limit` em 100. O painel pagina até vir uma página
  curta, então as **telas** enxergam tudo. Mas três consumidores carregam uma
  página só e truncam a partir de 100 registros:
  - o seletor de parceiro do formulário de produto (`listPartners(false, 100, 0)`
    — `false` é "todos", porque o fornecedor da própria loja é um parceiro
    inativo e o admin precisa poder escolhê-lo) — além de 100 parceiros,
    alguns ficam impossíveis de escolher;
  - a exportação CSV de transportadoras (`getAllCarriers()`);
  - o filtro por transportadora da tela de ocorrências (`getAllCarriers()`).
- **O aviso de truncamento do estoque tem um falso positivo.** O painel pagina
  o estoque até um teto duro de 2000 linhas e mostra "mostrando as primeiras
  2000" quando o teto é atingido. Como `GET /admin/inventory` não devolve
  `total`, o algoritmo não distingue "teto batido" de "o teto coincidiu com o
  fim dos dados" — um estoque de **exatamente** 2000 linhas exibe o aviso sem
  nada ter sido cortado.
- **"OCORRÊNCIAS ABERTAS" da tela de transportadoras conta toda ocorrência
  aberta**, `FALTA_ESTOQUE` incluída, porque o backend não oferece um filtro
  "só de transportadora". É `GET /occurrences?status=ABERTA` sem
  `carrier_id`.
- **"PARCEIROS ATIVOS" e "TRANSPORTADORAS ATIVAS" do dashboard são totais
  atuais**, exibidos sob um cabeçalho que diz "(últimos N dias)". Os números
  estão certos; o rótulo acima deles é que não se aplica a eles. Com o seed
  atual, "PARCEIROS ATIVOS" mostra **1** — `Edu` é parceiro inativo (§1), e
  o tile conta vitrines.
- **O dashboard perdeu o bloco educacional, o gráfico de atividade e três
  mini-painéis**, porque não existe rota `/dashboard` — ele é construído a
  partir de `GET /analytics/executive-summary?dias=30` mais os dois `total`
  acima. Mostra: pedidos criados no período, pedidos por status, ocorrências
  abertas e resolvidas, o resumo executivo, e os dois totais. Perdeu:
  `registeredStudents`, `activeStudents`, `newRegistrations`,
  `inactiveRiskStudents`, `activityHistory`, `registeredProducts`,
  `lowStockProducts`, `lowStock[]`, `carriers[]`, `recentOccurrences[]`.
  Nenhum foi inventado no cliente.
- **`rating` da transportadora é gravado como `0` na criação**, porque o
  formulário não o coleta. Pré-existente ao redesenho do painel.
- **`dashboard.component.scss` tem regras órfãs** para a marcação que foi
  removida. É por isso que o aviso de budget dele continua igual em vez de
  diminuir.
- **O painel não faz refresh de token.** A sessão expira com o access token.

### App (Flutter)

- **`AddToCartButton` agenda um `Future.delayed(1200ms)` para reverter o
  próprio rótulo e nunca o cancela no `dispose()`.** Bug latente
  pré-existente, descoberto quando o primeiro widget test apertou aquele
  botão: o teardown falha com "A Timer is still pending". Contornado pelo lado
  do teste (`pump(1300ms)`). Correção de uma linha: guardar o `Timer` e
  cancelá-lo no `dispose()`. Follow-up, não bloqueio.

---

## 11. Aplicando isto a um stack existente

Ver **"Aplicando a spec B a um stack existente"** na §5 de
[`microservices.md`](microservices.md). O código no disco não basta: a imagem
do `commerce-service` precisa ser reconstruída e a migration precisa ser
aplicada, nessa ordem.
