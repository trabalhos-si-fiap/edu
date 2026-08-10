# Dívida técnica registrada da fase 2 (blocos B e C)

Este é o inventário do que a migração do commerce para microserviços **deixou
de propósito para depois**. Não é uma lista de bugs abertos por descuido: cada
item aqui foi levantado durante a execução, discutido, e adiado com
justificativa. O que estava errado e barato foi corrigido na hora e não aparece
neste documento.

**Para que serve:** a fase 4 (o corte — apontar o app para o gateway e desligar
o monolito) precisa saber o que ainda não está pronto. Comece pela seção
[§1](#1-o-que-morde-primeiro-no-dia-do-corte): são os cinco itens que mudam de
"incômodo" para "incidente" exatamente no dia em que a frota subir junto pela
primeira vez.

**Como este documento foi produzido:** as revisões de cada task registraram
73 pendências (51 no bloco C, 22 no bloco B). A revisão final da branch triou
uma a uma em três categorias — bloqueia o merge, dívida registrada, descartar.
O que bloqueava foi corrigido antes do merge. O que foi descartado (resolvido
por task posterior, cosmético, ou não era defeito) não está aqui. Sobrou o que
segue.

**Sobre os números de linha:** todos foram medidos na árvore desta branch em
2026-08-10, no commit `f7df208`. Eles envelhecem; o nome do arquivo e o do
símbolo, não. Quando divergirem, confie no símbolo.

**O que este documento NÃO é:** não é a lista de divergências deliberadas entre
o commerce-service e o monolito — essas estão em
[`commerce-parity.md`](commerce-parity.md), e são decisões, não dívida. Também
não cobre a fase 3 (simulador de avanço de status, e os carve-outs listados na
§9.5 daquele registro).

---

## 1. O que morde primeiro no dia do corte

Cinco itens. Os quatro primeiros têm detalhe nas seções abaixo; o quinto está
na [§3](#3-mensageria-e-consumidores).

| # | Item | Por que é agora |
|---|---|---|
| 1 | [Idempotência do seed é read-then-write](#21-a-idempotência-do-seed-é-read-then-write) | `make services-seed` nunca foi executado. O corte é a primeira execução. |
| 2 | [`put_object` antes do `commit()`](#22-put_object-acontece-antes-do-commit) | Mesma primeira execução: um rollback deixa objeto órfão no MinIO. |
| 3 | [`DeadlockDetectedError` ~1/200 nas formas de pagamento](#41-o-select-de-lock-ordena-por-coluna-mutável) | Frequência baixa por requisição, alta por volume de produção. |
| 4 | [Título de notificação renderiza UUID de 36 caracteres](#71-o-título-da-notificação-de-pedido-mostra-o-uuid-inteiro) | Visível ao aluno no primeiro push depois do corte. |
| 5 | [Nenhum consumidor tem dead-letter queue](#31-nenhuma-fila-tem-dead-letter-exchange) | Foi o mecanismo que engoliu notificações em silêncio durante o próprio bloco C. |

---

## 2. Seed do catálogo

O seed (`commerce-service/app/seeds/products.py`, alvo `make services-seed`)
**foi escrito na fase 2b e nunca executado** — a proibição de mexer no stack
vivo do usuário valeu do começo ao fim dos dois blocos. Tudo nesta seção é
código que nunca rodou fora da suíte.

### 2.1 A idempotência do seed é read-then-write

**Onde:** `back-end/commerce-service/app/seeds/products.py:262` (a leitura) e
`:312` (o único `commit()`); `back-end/commerce-service/app/models/produto.py:59`.

**O que é:** `seed_products` monta um dicionário `existing` com os produtos já
gravados, decide item a item quem falta, e só então comita. Entre a leitura e a
escrita não há nada segurando o conjunto: `Product.name` é
`Column(String(160), nullable=False, index=True)` — **índice, não `unique`**. Duas
execuções concorrentes do seed leem "está vazio" e inserem as seis linhas cada
uma: doze produtos, seis pares de duplicatas, e nenhum erro.

**Por que foi adiado:** a suíte prova idempotência **sequencial**
(`tests/test_products_seed.py::TestProductsSeed::test_is_idempotent` — o node id
completo; o teste vive dentro da classe `TestProductsSeed`), que é o cenário que
existia enquanto o alvo não rodava. A corrida exige duas conexões contendentes,
que nenhum teste da fase 2 montou. `microservices.md` diz a mesma coisa na
seção de subida do stack: sequencial medido, concorrente não.

**O que custaria:** uma migration acrescentando `UNIQUE` em `products.name`
mais um `ON CONFLICT DO NOTHING` no insert; ou, mais barato e sem migration, um
lock distribuído no Redis em volta de `main()` — o seed é manual e não tem
requisito de paralelismo. Meio dia com teste de corrida.

### 2.2 `put_object` acontece antes do `commit()`

**Onde:** `back-end/commerce-service/app/seeds/products.py:273`, dentro de
`_apply_image`, contra o `commit()` de `:312`.

**O que é:** a foto de cada produto é baixada e enviada ao MinIO **antes** de a
transação fechar. Se o commit falhar — ou se o processo morrer no meio do laço
—, os objetos `products/seed-{i}.jpg` ficam no bucket sem nenhuma linha
apontando para eles. O `delete_object` de compensação que existe logo abaixo é
para a chave *substituída*, não para a que acabou de subir.

**Por que foi adiado:** a janela só é alcançável numa execução real contra
MinIO, que é justamente o que nunca aconteceu.

**O que custaria:** mover os uploads para depois do commit (o `image_url` do
produto já é determinístico — `products/seed-{index}.jpg` —, então dá para
gravar a chave primeiro e subir o objeto depois), ou envolver o laço num
`try/except` que apaga o que subiu. Algumas horas.

### 2.3 Os valores literais do catálogo não estão todos travados

**Onde:** `back-end/commerce-service/tests/test_products_seed.py:47`
(`test_catalog_matches_the_legacy_contract`) e `:68`.

**O que é:** o teste de contrato trava `name`, `type`, `subtype`, `price` e a
**ordem** das seis entradas (a ordem é contrato: o índice vira a chave
`products/seed-{i}.jpg`). Não trava `rating_avg`/`rating_count`, nem qual foto
pertence a qual produto — o teste de fotos só confere formato de URL e
unicidade.

**Por que foi adiado:** nenhum cliente lê esses campos do seed hoje; eles são
dado de vitrine.

**O que custaria:** duas colunas a mais na tabela `_CATALOGO_LEGACY` que o teste
já mantém. Uma hora.

### 2.4 O docstring do módulo descreve um fallback inalcançável

**Onde:** `back-end/commerce-service/app/seeds/products.py:20`.

**O que é:** o texto diz que `_solid_png()` é mantido como fallback stdlib "para
qualquer entrada futura sem `photo_url`". `_apply_image` retorna cedo quando
`photo_url` é falsy, e as seis entradas têm uma — `_solid_png` não tem nenhum
chamador em `app/`, só em `tests/test_products_seed.py:132`.

**Por que foi adiado:** é uma linha de prosa, e a conclusão prática (a função
fica no arquivo) não muda.

**O que custaria:** uma linha.

---

## 3. Mensageria e consumidores

### 3.1 Nenhuma fila tem dead-letter exchange

**Onde:** `back-end/packages/edu-common/src/edu_common/events.py`,
`EventConsumer.bind` — `declare_queue(queue_name, durable=True)`, sem
`arguments`. Os handlers: `analytics-service/app/events/consumer.py:52`,
`learning-service/app/events/consumer.py:18`, e cinco em
`notification-service/app/events/consumer.py` (`:23`, `:39`, `:78`, `:121`,
`:147`).

**O que é:** todo handler embrulha o trabalho em `async with message.process():`
sem `except`. Nesse modo o `aio_pika` faz ACK no sucesso e **reject com
`requeue=False`** na exceção. Sem dead-letter exchange declarada, reject com
`requeue=False` **descarta a mensagem** — sem log de aplicação, sem retentativa,
sem rastro. Um `TypeError` de serialização, um deploy com schema divergente ou
um Postgres momentaneamente fora derrubam eventos em silêncio.

Isso não é teórico: foi exatamente este caminho que engoliu as notificações
perdidas entre as tasks C3 e C10 deste bloco, e só foi percebido porque alguém
foi conferir o banco.

**Por que foi adiado:** é mudança de topologia de broker que atravessa três
serviços e o pacote comum, e precisa de decisão de operação (para onde vai a
DLQ, quem a drena, com que alarme). Não cabia dentro de nenhuma task de porte.

**O que custaria:** declarar uma DLX e passar `arguments={"x-dead-letter-exchange":
...}` em `declare_queue`, mais uma fila de retenção por serviço e um runbook de
drenagem. Um a dois dias, incluindo o teste de que uma exceção no handler
entrega a mensagem na DLQ em vez de sumir.

### 3.2 O docstring do stub de eventos ficou desatualizado

**Onde:** `back-end/commerce-service/tests/conftest.py:111`.

**O que é:** o texto do `_stub_publish_event` explica a lista de captura dizendo
que `confirm-payment` chamado duas vezes publica UM único
`order.status_changed`. Desde que a rota passou a encadear duas transições, uma
chamada bem-sucedida já publica dois. O teste que ele descreve continua correto
— só a explicação envelheceu.

**O que custaria:** uma linha.

---

## 4. Concorrência e atomicidade

### 4.1 O `SELECT` de lock ordena por coluna mutável

**Onde:** `back-end/commerce-service/app/services/pagamento.py:81`
(dentro de `listar_metodos`, que começa em `:77`) e `:96` (dentro de
`_listar_metodos_com_lock`, que começa em `:86`) — as duas linhas que
`grep -n "order_by" app/services/pagamento.py` devolve.

**O que é:** o select que toma `with_for_update()` ordena por
`is_default.desc(), created_at`. `is_default` é justamente a coluna que as rotas
concorrentes estão mudando, então duas transações podem enxergar ordens
diferentes e pegar as travas em ordem diferente — deadlock. Medido em contenção
tripla: `DeadlockDetectedError` em cerca de 1 a cada 200 rodadas.

**Por que foi adiado:** a frequência é baixa o bastante para não reprovar a
suíte e o efeito é um 500 isolado, não corrupção — o índice único parcial
`ix_payment_methods_one_default_per_user` continua garantindo a invariante.

**O que custaria:** ordenar o select **de lock** por uma chave imutável (`id`) e
deixar a ordem de exibição só em `listar_metodos`. Poucas horas; o difícil é o
teste, que precisa de contenção real.

### 4.2 `except IntegrityError` é incondicional

**Onde:** `back-end/commerce-service/app/services/pagamento.py:146`.

**O que é:** `criar_metodo` captura qualquer `IntegrityError` e reinsere o método
como não-default. A intenção é tratar a corrida do índice único parcial, mas o
`except` não olha qual constraint estourou: a violação de outra constraint
qualquer também viraria um 201 com `is_default:false` — estado errado devolvido
como sucesso.

**O que custaria:** identificar a constraint que estourou antes de decidir
refazer — o driver expõe o nome no erro original — e relançar o resto. Algumas
horas, mais um teste que force outra violação e exija que ela suba.

### 4.3 A corrida de zero linhas devolve `is_default:false`

**Onde:** mesmo bloco de `pagamento.py:146`.

**O que é:** consequência do desenho acima, registrada de propósito: quando dois
`criar_metodo` do mesmo usuário zerado correm juntos, o perdedor volta como
não-default. É defensável (alguém tem que perder), mas o cliente pediu
`is_default: true` e recebeu `false` com 201 — sem nenhum campo indicando que a
intenção foi rebaixada.

**O que custaria:** ou devolver 409, ou acrescentar um campo de aviso na
resposta. É decisão de contrato antes de ser código.

### 4.4 `TestDefaultLockConcurrency` fica vácuo quando rodado isolado

**Onde:** `back-end/commerce-service/tests/test_payment_methods_parity.py:319`.

**O que é:** a classe depende de estado semeado por testes que rodam antes dela
no arquivo. Invocada sozinha (`pytest ...::TestDefaultLockConcurrency`), passa
sem exercitar a contenção que existe para medir. O caminho de CI, que roda o
arquivo inteiro, está protegido.

**O que custaria:** uma fixture própria que semeia os três métodos. Uma hora.

### 4.5 A recompra concorrente não tem prova

**Onde:** `back-end/commerce-service/app/routers/pedidos.py`, rota de rebuy.

**O que é:** a rota é não-idempotente por decisão (recomprar duas vezes dobra o
carrinho, e há teste sequencial travando isso). O que não existe é prova de que
duas recompras **concorrentes** do mesmo pedido não corrompem o carrinho.

**O que custaria:** duas conexões contendentes num teste, como o de checkout
concorrente que já existe. Meio dia.

### 4.6 `transicionar_pedido` comita por dentro

**Onde:** `back-end/commerce-service/app/routers/separacao.py`, função
`transicionar_pedido`; call sites encadeados em `app/routers/admin.py`
(`confirmar_pagamento`) e no próprio `separacao.py` (`finalizar_separacao`,
`SEPARADO -> AGUARDANDO_COLETA`).

**O que é:** a função comita antes de publicar o evento, e publish que falha
propaga. Qualquer rota que encadeie duas transições fica, portanto, com um
estado intermediário commitado se a segunda não acontecer.
`confirmar_pagamento` foi tornado **retentável** antes do merge (a primeira
transição virou condicional ao estado atual), o que fecha o beco sem saída.
`finalizar_separacao` tem a mesma forma e é **anterior a esta branch**: seu
estado intermediário, `SEPARADO`, também não é oferecido por nenhuma outra rota.

**Por que foi adiado:** a correção estrutural — uma transação envolvendo as duas
transições, ou publicação fora do caminho de request — exige tirar o `commit()`
de dentro de `transicionar_pedido`, que **cinco rotas** compartilham
(`confirmar_pagamento`, `confirmar_coleta`, `confirmar_entrega`,
`iniciar_separacao` e `finalizar_separacao` — sete chamadas ao todo, porque
`confirmar_pagamento` e `finalizar_separacao` encadeiam duas cada;
`grep -n "await transicionar_pedido(" app/routers/*.py | sort`), e mover a
publicação para um outbox. É refatoração, não correção de fechamento.

**O que custaria:** um padrão de outbox transacional (tabela de eventos escrita
na mesma transação, publicada por um worker). Vários dias, e é a mesma solução
que resolve a §3.1 pela outra ponta.

### 4.7 Duas rotas ainda desarmam o `FOR UPDATE` pelo identity map

**Onde:** `back-end/commerce-service/app/routers/separacao.py:233`
(`finalizar_separacao`) e `.../entrega.py:147` (`confirmar_entrega`). Esse
pre-read de entidade sem lock aparece em cinco linhas —
`grep -n "result = await db.execute(select(Order).where(Order.id == pedido_id))" app/routers/*.py | sort`
devolve também `admin.py:111`, `admin.py:128` e `ocorrencias.py:170` — mas só
estas duas são seguidas de uma chamada a `transicionar_pedido` na mesma sessão;
as outras três (`atribuir_separador`, `atribuir_entregador` e
`listar_ocorrencias_pedido`) não passam pelo funil de transição.

**O que é:** as duas leem a **entidade** `Order` antes de chamar
`transicionar_pedido`, e essa leitura põe a instância no identity map da sessão.
Quando `transicionar_pedido` roda o próprio `SELECT ... FOR UPDATE` na mesma
sessão, o Postgres devolve a linha nova mas o ORM devolve a instância já
carregada **sem repopular os atributos** (padrão do SQLAlchemy — só
`populate_existing()` repopula), então o lock não protege nada: o chamador
concorrente revalida contra um status velho, passa em `validar_transicao` e
grava por cima. O envenenamento depende de a instância continuar viva, e nas
duas rotas ela continua — a local `pedido` é usada para a checagem de posse e
segue referenciada.

**Por que foi adiado:** as duas são **anteriores a esta branch** e estão fora do
escopo da correção que fechou o mesmo defeito em `confirmar_pagamento`
(§4.6 e `test_two_concurrent_confirm_payments_leave_one_pair_of_transitions`).
O mecanismo foi medido lá, com duas sessões e interleave determinístico; estas
duas **não** têm harness de corrida rodado contra elas — o que está medido é que
a forma do código é a mesma, não o efeito em cada uma. O efeito esperado é o
mesmo de lá: linha de histórico duplicada e `order.status_changed` publicado
duas vezes, que `notification-service` e `analytics-service` consomem duas
vezes.

**O que custaria:** um `.populate_existing()` no `SELECT ... FOR UPDATE` de
`transicionar_pedido` fecharia **as três rotas de uma vez**, no único ponto por
onde todas passam — uma linha, mais um teste de corrida por rota (o de
`confirm-payment` serve de molde). A alternativa por call site (trocar cada
pre-read de entidade por `select(Order.<coluna>)`, como `confirmar_pagamento`
fez) não serve igual aqui: as duas rotas precisam de mais de uma coluna
(`picker_id`/`deliverer_id` além do status), então o escalar viraria uma tupla e
o ganho de clareza some.

---

## 5. Migrations e schema

### 5.1 Os nomes de constraint continuam em português

**Onde:** as migrations de rename do bloco C, em
`back-end/commerce-service/alembic/versions/`.

**O que é:** `pedidos` virou `orders` e `pedido_itens` virou `order_items`, mas
as constraints e FKs mantiveram os nomes antigos
(`pedido_itens_pedido_id_fkey`, `pedido_status_historico_pedido_id_fkey`,
`ocorrencias_pedido_id_fkey`). Um banco migrado e um banco criado do zero por
`Base.metadata.create_all()` passam a ter nomes de constraint diferentes — e é
`create_all()` que a suíte usa.

**Por que foi adiado:** renomear constraint é migration pura, sem ganho
funcional, e os nomes estão documentados nas três migrations que os usam.

**O que custaria:** uma migration de `ALTER ... RENAME CONSTRAINT` por nome.
Baixo risco, algumas horas.

### 5.2 As mensagens dos guards apontam para um caminho que não existe na imagem

**Onde:** `back-end/commerce-service/alembic/versions/099099b0c1a8_...py:116`,
`1308bb221890_...py:58` e `bd410bba0e85_...py:133`.

**O que é:** quando o guard de perda de dado dispara, a mensagem manda o
operador ler `.superpowers/sdd/2026-08-05-phase-2c-order-and-tracking/...`. Esse
diretório é o workspace temporário do fluxo de desenvolvimento: **não existe na
imagem do serviço**, e deixa de existir no repositório quando o fluxo fecha.
Quem levar esse erro em produção não terá o que ler.

**O que custaria:** trocar por uma referência a este documento e ao
`commerce-parity.md`. Três linhas.

### 5.3 Os testes de guard comparam a constante com um literal

**Onde:** `back-end/commerce-service/tests/test_migration_guard_c4.py:102` e
`tests/test_migration_guard.py:110`.

**O que é:** o docstring promete pegar "alguém acrescenta uma tabela à migration
e esquece do guard". A asserção é
`set(revision._TABELAS_AFETADAS) == {"orders", "order_items"}` — compara a
constante com uma lista escrita à mão, não com o que o `upgrade()` de fato
reescreve. Acrescentar uma tabela ao corpo da migration sem acrescentá-la à
constante mantém o teste **verde**: exatamente o cenário que ele diz cobrir.

**O que custaria:** extrair as tabelas do corpo do `upgrade()` (por inspeção das
chamadas registradas num `op` de mentira, padrão que
`test_migration_guard_c10_pedido_id_uuid.py` já usa) e comparar com a constante.
Meio dia, e um fix cobre os dois arquivos.

### 5.4 `len(conn.consultas) == 2` não distingue os dois casos

**Onde:** `back-end/commerce-service/tests/test_migration_guard_c4.py:76` e
`:93`; `tests/test_migration_guard.py:101`.

**O que é:** a asserção quer dizer "as duas tabelas foram consultadas". Ela
também passa se a mesma tabela for consultada duas vezes e a outra, nenhuma.
Os testes de `test_migration_guard_c4.py` mitigam isso conferindo o conteúdo
das consultas logo abaixo; a contagem sozinha não prova nada.

**O que custaria:** trocar a contagem por comparação de conjunto de tabelas
citadas. Uma hora.

### 5.5 TOCTOU no guard de `downgrade()` do notification

**Onde:** `back-end/notification-service/alembic/versions/886205d547cc_...py`,
`_falhar_se_pedido_id_tiver_dado_no_downgrade`.

**O que é:** o guard conta as linhas com `pedido_id` preenchido e só então roda o
`ALTER`. Uma linha inserida entre a contagem e o `ALTER` é zerada assim mesmo.
A janela é estreita e vale só para o `downgrade`, que não roda no corte — o lado
que roda, o `upgrade`, ganhou o mesmo guard antes do merge.

**O que custaria:** `LOCK TABLE notificacoes IN EXCLUSIVE MODE` antes da
contagem, ou parar o consumidor durante a migration. Uma linha de SQL, mas com
efeito de bloqueio que merece decisão de operação.

---

## 6. Buracos de cobertura

Todos medidos como ausentes. Nenhum é regressão: são caminhos que nunca tiveram
teste.

| Onde | O que falta | Custo |
|---|---|---|
| `commerce-service/app/routers/ocorrencias.py:200` | Nenhum teste permanente passa pelo `Product.id.in_(ocorrencia.produtos_sugeridos)` com lista **não vazia** — a coerção `str` → `uuid` foi provada por um teste descartado durante a revisão. Precisa semear `Estoque` para dois produtos. | Poucas horas |
| `commerce-service/tests/test_occurrences_routes.py` | A resolução `remover_item` de uma ocorrência não tem teste (`grep -c '"remover_item"'` devolve 0), e ela passa por um caminho de flush assíncrono. | Poucas horas |
| `commerce-service/app/services/auth_client.py::get_address` | Nenhum teste exercita `GET /auth/addresses/not-a-uuid`; o 422 foi medido à mão. | Uma hora |
| `commerce-service` ↔ `auth-users-service` | Nenhum teste faz os dois serviços falarem HTTP de verdade; o cliente é sempre stubado. Inerente à suíte por serviço — entra no checklist de corte, não numa correção de código. | Ambiente, não código |
| `front-end-flutter/test/features/logistics/` | Existem três arquivos (`logistics_api_test.dart`, `occurrence_test.dart`, `order_test.dart`), e **nenhum é teste de widget**: os três cobrem cliente HTTP e parsing de domínio. As telas de staff (`picking_*`, `delivery_*`, `tracking_screen`) continuam sem cobertura. O lado marketplace foi coberto (`orders_screen_test.dart`). | Um a dois dias |
| `commerce-service/tests/test_cart_parity.py:345` | `_e_select_lock_item` casa mais consultas do que o próprio docstring diz travar. O fix já está escrito na entrada original: exigir a substring `"cart_items.product_id = "`. | Uma hora |

---

## 7. Decisões de produto e contrato pendentes

Estes **não são bugs a corrigir sem antes decidir**. Estão aqui para que
ninguém os "conserte" por engano nem os redescubra como novidade.

### 7.1 O título da notificação de pedido mostra o UUID inteiro

**Onde:** `back-end/notification-service/app/events/consumer.py:111`, `:136` e
`:153` — as três notificações de pedido.

**O que é:** os títulos são montados como `f"Pedido #{payload['pedido_id']}"`
(mais um sufixo nos dois últimos), e `pedido_id` passou a ser UUID na fase 2. O
aluno recebe um push com 36 caracteres hexadecimais onde antes lia um inteiro
curto. É regressão de UX real, e nenhum teste asserta o título dessas
notificações.

**Por que não foi corrigido:** escolher o formato é decisão de produto —
primeiros 8 caracteres (como o `idCurto` do Flutter), um número de pedido
sequencial separado, ou nenhum identificador no título.

**O que custaria:** trivial depois da decisão, mais um teste que trave o
formato escolhido.

### 7.2 `idCurto` trunca o UUID em 8 caracteres

**Onde:** `front-end-flutter/lib/features/logistics/domain/order.dart:146`,
usado em sete pontos das telas de staff.

**O que é:** `id.substring(0, 8).toUpperCase()`. Oito caracteres hex são 4
bilhões de combinações — colisão é improvável, mas as telas de operação mostram
esse valor como se identificasse o pedido, e dois pedidos colididos ficariam
indistinguíveis para o separador.

**Por que não foi corrigido:** é a mesma decisão da §7.1, e as duas deveriam ser
tomadas juntas.

### 7.3 Pedido cancelado ainda mostra previsão de chegada

**Onde:** o construtor de rastreio do commerce e
`front-end-flutter/lib/features/order_tracking/`.

**O que é:** um pedido cancelado volta com `estimated_arrival` preenchido e com
timestamp no passo `delivered`. Isso é **fidelidade ao legacy** — foi conferido
que o monolito faz o mesmo. O modelo do Flutter tem `isCancelled`
(`order_model.dart:205`) e o provider já o usa para parar o polling
(`order_provider.dart:80`), mas a **tela** de rastreio não o consulta para
esconder a previsão.

**Por que não foi corrigido:** mudar o backend quebraria a paridade que o bloco
inteiro existe para provar. A correção certa é na tela.

### 7.4 As mensagens de 404 estão em português

**Onde:** `back-end/commerce-service/app/routers/pedidos.py:128`, `:166`, `:195`
e `:269` — `"Pedido não encontrado"`, onde o legacy responde
`"Order not found"`.

**O que é:** divergência de contrato não registrada. O
[`commerce-parity.md`](commerce-parity.md) §9.3 afirma hoje que há uma única
diferença de chave em tudo; esta é uma diferença de **valor** que merece uma
linha lá.

**O que custaria:** decidir o idioma das mensagens de erro do serviço, e uma
linha no registro de paridade de qualquer forma.

### 7.5 `.order_by(Order.id)` não é mais ordem de inserção

**Onde:** `back-end/commerce-service/app/routers/admin.py:30` e
`app/routers/entrega.py:30`, `:52`.

**O que é:** com PK inteira, ordenar por `id` era ordenar por inserção. Agora a
PK é UUID: os inserts do ORM usam UUIDv7 (`app/ids.py`), que é ordenável no
tempo e preserva quase toda a intenção, mas o `server_default`
`gen_random_uuid()` é **v4** — qualquer insert que não passe pelo ORM cai numa
posição aleatória da listagem.

**O que custaria:** trocar por `.order_by(Order.created_at, Order.id)` nas três
listagens. Uma hora, mas muda a ordem que as telas de staff já mostram.

### 7.6 Os query params de staff estão em português

**Onde:** `back-end/commerce-service/app/routers/admin.py:91` (`separador_id`) e
`:108` (`entregador_id`).

**O que é:** as rotas de atribuição recebem os ids por query param com nome em
português, contra o resto do serviço em inglês. Foi medido que **nenhum cliente
Flutter chama essas rotas**, então o rename é livre a qualquer momento.

**O que custaria:** trivial, e sem coordenação com o app.

### 7.7 `Pedido.fromJson` usa casts duros — de propósito

**Onde:** `front-end-flutter/lib/features/logistics/domain/order.dart:150-154`.

**O que é:** os casts (`json['id'] as String` etc.) não são defendidos por
nenhum `try` — `order.dart` não tem nenhum (`grep -c "try"` nele devolve `0`).
Os `try` do módulo estão no arquivo vizinho,
`front-end-flutter/lib/features/logistics/data/logistics_api.dart` — `:54`
(`_listaPedidos`) e `:73` (`_patchPedido`), com os blocos `try`/`on` indo até
`:63` e `:82` — e envolvem só a chamada HTTP: convertem falha de rede em
`LogisticsException` e deixam de fora `jsonDecode(...)` e
`Pedido.fromJson(...)`, que rodam DEPOIS do `try`. (O terceiro `try` do
arquivo, `:90`, é outro assunto: protege o parse do corpo de ERRO dentro de
`_mensagemErro`.) Uma mudança de contrato no
backend vira, portanto, exceção visível, não campo silenciosamente vazio. Foi
discutido e **mantido**: numa tela de operação, tela de erro é melhor que dado
errado.

**Não corrija sem decidir o contrário.** Está aqui só para não ser
redescoberto como defeito.

---

## 8. Higiene de código

Itens pequenos, sem efeito observável, agrupados para serem varridos juntos
quando alguém tocar nos arquivos.

| Onde | O que é | Custo |
|---|---|---|
| `commerce-service/app/services/previsao_entrega.py:45`, `app/services/priorizacao_fila.py:60` | Anotados como `dict[int, ...]`; as chaves são UUIDs desde a fase 2. Sem efeito em runtime — mentem sobre o tipo para quem lê e para o type checker. | Minutos |
| `commerce-service/tests/test_admin_routes.py:38` | `_historico_do_pedido(db_session, pedido_id: int)` — mesmo problema, no helper de teste. | Minutos |
| `commerce-service/app/routers/pedidos.py:199` e `:206` | `estimar_prazo_entrega` é chamada duas vezes na mesma requisição; a primeira só aproveita `amostras`. Uma query desperdiçada por request. | Uma hora |
| `commerce-service/app/services/auth_client.py:105` | O log de transporte inalcançável para `/auth/addresses` não diz **qual** host falhou, enquanto o irmão de `/auth/me` (`:65`) inclui a URL. Diagnóstico perdido a custo zero de PII (`settings.auth_service_url` não tem dado de aluno). | Minutos |
| `commerce-service/app/models/pedido.py:151` | Comentário cita `\d pedido_itens` e a coluna `fornecedor_id` — a tabela virou `order_items` e a coluna, `supplier_id`. Evidência de banco colada em código de produção, que envelheceu junto com o rename. | Minutos |
| `front-end-flutter/lib/features/marketplace/presentation/orders_screen.dart:511` | Docstring de `_FinishedOrderCard` cita "revisão de correção 1", um artefato do processo de desenvolvimento que não significa nada para quem ler o arquivo depois. | Minutos |
| `commerce-service/tests/` (seis arquivos) | A fixture `seeded_products` está duplicada em `test_cart_parity.py:30`, `test_cart_services_parity.py:36`, `test_orders_parity.py:118`, `test_orders_services_parity.py:65`, `test_products_parity.py:27` e `test_products_services_parity.py:62`. Vai para o `conftest.py` quando alguém precisar mudar as seis juntas. | Meio dia |
