# Dívida técnica registrada da fase 2 (blocos B, C e D)

Este é o inventário do que a migração do commerce e do suporte para
microserviços **deixou de propósito para depois**. Não é uma lista de bugs
abertos por descuido: cada item aqui foi levantado durante a execução,
discutido, e adiado com justificativa. O que estava errado e barato foi
corrigido na hora e não aparece neste documento.

**Para que serve:** a fase 4 (o corte — apontar o app para o gateway e desligar
o monolito) precisa saber o que ainda não está pronto. Comece pela seção
[§1](#1-o-que-morde-primeiro-no-dia-do-corte): são os sete itens que mudam de
"incômodo" para "incidente" exatamente no dia em que a frota subir junto pela
primeira vez.

**Como este documento foi produzido:** as revisões de cada task registraram
73 pendências (51 no bloco C, 22 no bloco B), mais 20 no bloco D. A revisão
final de cada branch triou uma a uma em três categorias — bloqueia o merge,
dívida registrada, descartar. O que bloqueava foi corrigido antes do merge. O
que foi descartado (resolvido por task posterior, cosmético, ou não era
defeito) não está aqui. Sobrou o que segue.

**Sobre os números de linha:** os dos blocos B e C foram medidos na árvore
daquela branch em 2026-08-10, no commit `f7df208`; os do bloco D
([§9](#9-bloco-d--chatbot-service-e-o-módulo-support)), na branch
`feat/microservices-phase-2d`, no commit `12f3ccd`. Eles envelhecem; o nome do
arquivo e o do símbolo, não. Quando divergirem, confie no símbolo.

**Por que o bloco D está aqui e não num arquivo próprio:** boa parte do que ele
deixou em aberto não é do `chatbot-service` — é da frota inteira, e três itens
(a engine de módulo, o `dependency_overrides.clear()` e a ausência de
sync-check em teste) só valem a pena se forem corrigidos nos seis serviços de
uma vez. Separar por bloco esconderia exatamente isso.

**O que este documento NÃO é:** não é a lista de divergências deliberadas entre
o commerce-service e o monolito — essas estão em
[`commerce-parity.md`](commerce-parity.md), e são decisões, não dívida. Também
não cobre a fase 3 (simulador de avanço de status, e os carve-outs listados na
§9.5 daquele registro).

---

## 1. O que morde primeiro no dia do corte

Sete itens. Os quatro primeiros têm detalhe nas seções abaixo; o quinto está na
[§3](#3-mensageria-e-consumidores) e os dois últimos, do bloco D, na
[§9](#9-bloco-d--chatbot-service-e-o-módulo-support).

| # | Item | Por que é agora |
|---|---|---|
| 1 | [Idempotência do seed é read-then-write](#21-a-idempotência-do-seed-é-read-then-write) | `make services-seed` nunca foi executado. O corte é a primeira execução. |
| 2 | [`put_object` antes do `commit()`](#22-put_object-acontece-antes-do-commit) | Mesma primeira execução: um rollback deixa objeto órfão no MinIO. |
| 3 | [`DeadlockDetectedError` ~1/200 nas formas de pagamento](#41-o-select-de-lock-ordena-por-coluna-mutável) | Frequência baixa por requisição, alta por volume de produção. |
| 4 | [Título de notificação renderiza UUID de 36 caracteres](#71-o-título-da-notificação-de-pedido-mostra-o-uuid-inteiro) | Visível ao aluno no primeiro push depois do corte. |
| 5 | [Nenhum consumidor tem dead-letter queue](#31-nenhuma-fila-tem-dead-letter-exchange) | Foi o mecanismo que engoliu notificações em silêncio durante o próprio bloco C. |
| 6 | [`/support` não tem teto de linhas](#92-o-rabo-de-linhas-sem-teto-em-support) | É o único item do bloco D que **piora com tráfego real**, e o corte é quando o tráfego real chega. |
| 7 | [Aluno desativado mantém o suporte por até 60 minutos](#93-aluno-desativado-continua-com-acesso-ao-suporte-por-até-60-minutos) | Divergência de comportamento contra o módulo que está sendo substituído, e ela nasce no instante em que o `support` novo entra no ar. |

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

---

## 9. Bloco D — `chatbot-service` e o módulo `support`

O bloco D tirou o módulo `support` do monolito e o pôs no `chatbot-service`,
que até então não tinha banco. Cinco commits, `049a7bc..1689a0a`. A revisão
final da branch **não achou nenhum defeito de código**: o que o serviço faz foi
verificado correto, inclusive a sua única propriedade crítica de segurança (a
cláusula `where user_id ==` que separa a conversa de um aluno da do outro,
provada por mutação — derrubá-la reprova exatamente um teste, e nenhum outro).
O que sobrou, e está aqui, é o que foi adiado de propósito.

Caminhos relativos a `back-end/chatbot-service/` salvo quando dito o contrário.

**Um aviso sobre o escopo, porque muda a decisão de correção:** dos treze itens
abaixo, **seis não são do `chatbot-service`** — são da frota (§9.6, §9.7, §9.9
e os três da §9.11). Corrigi-los num serviço só deixa a frota mais desigual do
que está, e custa quase o mesmo que corrigi-los nos seis. Outros dois (§9.3 e
§9.4) foram encontrados aqui mas têm a mesma forma nos seis serviços. Trate os
oito como manutenção da frota, não como pendência deste bloco.

**Proveniência dos números:** as linhas foram medidas no commit `12f3ccd`. Os
resultados do portão (§9.12) são **transcritos** da execução do portão do bloco
D, em 2026-08-10 — não foram re-executados para escrever esta seção, e a metade
que destrói volumes não é repetível sem nova autorização do usuário.

### 9.1 As duas divergências declaradas — decisões, não dívida

Mesma distinção que o [`commerce-parity.md`](commerce-parity.md) faz na §5 e na
§9.3 dele: isto **não** é para corrigir. Está aqui para não ser redescoberto
como defeito nem "consertado" por engano.

| # | Divergência | Onde | Razão | Quem decidiu |
|---|---|---|---|---|
| 1 | **`GET /support` sem paginação** | `app/services/suporte.py::listar_mensagens`, `app/routers/suporte.py` | Contraria a regra 4 do `CLAUDE.md` (paginação obrigatória). É réplica exata do legacy (`legacy/app/modules/support/services.py`), e réplica exata é o critério de aceite deste bloco. Mesma forma da divergência nº 2 do bloco B, em `GET /payment-methods`. A conta que ela deixa aberta está na §9.2 | Plano do bloco D, ratificado na revisão final |
| 2 | **403 vs 401 sem header `Authorization`** | `packages/edu-common/src/edu_common/deps.py:16-23` | Propriedade do `edu-common`, não deste serviço: `HTTPBearer(auto_error=False)` mais checagem manual devolve **403** para credencial ausente e **401** para token presente-mas-inválido; o legacy devolve 401 nos dois. Já registrada como divergência nº 1 do bloco B (task B0) e **vale igual aqui**: as duas asserções de `TestAuthRequired` foram portadas de `== 401` para `== 403` | Task B0, herdada |

A nº 1 ganhou, nesta correção, a única coisa que lhe faltava: o motivo está
agora **no código**, no docstring de `listar_mensagens`. Antes disso um
`grep -n "pagina"` no router, no serviço, nos schemas e no model devolvia
zero linhas, e a justificativa vivia só no plano e num registro git-ignored —
os dois somem quando o bloco fecha.

### 9.2 O rabo de linhas sem teto em `/support`

**Onde:** `app/routers/suporte.py` (as duas rotas) e
`app/services/suporte.py::listar_mensagens`.

**O que é:** a conversa não tem teto por nenhum lado. Não há paginação, não há
rate limit no POST, e não há limite de mensagens por conversa. O limite de
2000 caracteres é **por mensagem**, não por thread
(`app/models/suporte.py:40`, `app/schemas.py:36`). E como o POST devolve a
conversa **completa** — que é contrato, não descuido —, não é só o `GET` que
materializa a thread inteira: **todo POST também**. Um aluno autenticado que
mande mensagens em laço faz cada requisição seguinte ficar mais cara, para ele
mesmo e para o banco, sem violar regra nenhuma.

É o único item do bloco D que **degrada com tráfego real**. Todos os outros ou
são de manutenção, ou dependem de um caminho que ninguém percorre hoje.

**Por que foi adiado:** é a conta da divergência nº 1. Pôr paginação, teto ou
rate limit dentro deste bloco quebraria a paridade que o bloco existe para
provar, e a paridade era o critério de aceite acordado.

**O que custaria:** a paridade acaba no corte, e é lá que a correção cabe. Três
peças independentes, em ordem de retorno: rate limit no POST (o Redis já está
na frota, e a regra 11 do `CLAUDE.md` manda usar `cache.incr()`, nunca
read→modify→write); um teto de mensagens por conversa; e paginação no `GET`,
que é a mais cara porque muda o contrato que o app consome. Um a dois dias com
teste de carga que prove o teto.

### 9.3 Aluno desativado continua com acesso ao suporte por até 60 minutos

**Onde:** `app/dependencies.py` e `app/routers/suporte.py`, contra
`legacy/app/modules/auth/dependencies.py:48`.

**O que é:** o legacy carrega o usuário do banco a cada requisição e rejeita
quem não estiver ativo — `if user is None or not user.is_active: raise
_UNAUTHORIZED`. Este serviço **não tem tabela de usuários**: a identidade vem
inteira do JWT, e não há nada para consultar. Desativar um aluno, portanto, não
derruba o acesso dele ao suporte; o acesso morre quando o token expira.

A janela é a validade do access token:
`auth-users-service/app/config.py:17` é
`access_token_expire_minutes: int = 60`. O refresh **é** barrado — a rota de
refresh checa `not user.ativo` (`auth-users-service/app/routers/auth.py:188`)
—, então a exposição é limitada e não se renova. Mas ela existe, e é real.

**Por que está aqui:** ao contrário do 403-vs-401, que foi decidido e
registrado na task B0, **isto nunca tinha sido escrito em lugar nenhum**. É uma
divergência de comportamento contra o módulo que está sendo replicado, e foi
descoberta na revisão final da branch, não na tradução das asserções.

**Por que foi adiado:** é arquitetural e vale para a frota inteira — todo
serviço que valida JWT sem consultar o auth tem a mesma janela, não só este.
Fechá-la exige escolher entre três desenhos: TTL curto de access token (o mais
barato, e piora a experiência), consulta ao auth-users-service por requisição
(acopla e custa latência em todo endpoint), ou uma denylist de tokens em Redis
alimentada pelo evento de desativação (o certo, e o mais caro).

**O que custaria:** a decisão antes do código. Depois dela, a denylist em Redis
é de um a dois dias, e resolve os seis serviços de uma vez.

### 9.4 `sub` malformado devolve 500 onde o legacy devolvia 401

**Onde:** `app/routers/suporte.py:21` e `:36` — as duas chamadas
`uuid.UUID(user_id)`, sem `try`.

**O que é:** um token **validamente assinado** cujo `sub` não seja um UUID faz
o `uuid.UUID()` levantar `ValueError` dentro do handler, e o FastAPI devolve
500. O legacy trata o mesmo caso: `legacy/app/modules/auth/dependencies.py:42-45`
embrulha a conversão num `try` e captura `ValueError`/`TypeError`, respondendo
401. É **comportamento do legacy que este porte não replicou** — não é uma
questão de estilo, e é assim que deve ser lido.

**Qual o risco de verdade:** quase nenhum, e vale registrar por quê, para que
ninguém trate isto como urgente. Chegar até essa linha exige uma assinatura
válida, isto é, o `JWT_SECRET`; e quem emite os tokens sempre põe um UUID no
`sub` — `auth-users-service/app/routers/auth.py:40` e `:191` chamam
`create_access_token(str(user.id), ...)`, com o id do usuário como primeiro
argumento posicional. Não há caminho de produção que produza o token
necessário. O que sobra é um 500 em vez de um 4xx num cenário que só um
detentor da chave alcança.

**Por que foi adiado:** a forma é da frota — `commerce-service/app/routers/pedidos.py:57`
faz a mesma conversão nua. Corrigir aqui só troca um serviço de lugar na fila.

**O que custaria:** o lugar certo é o `edu-common`, devolvendo o id já
convertido em `uuid.UUID` (ou 401) de dentro de `get_current_user_id`, o que
apaga a conversão de todos os call sites de uma vez. Algumas horas mais um
teste por serviço.

### 9.5 A conversa ordena por `created_at` sem desempate

**Onde:** `app/services/suporte.py:29`.

**O que é:** `.order_by(SupportMessage.created_at)`, e `created_at` é
`server_default=func.now()` (`app/models/suporte.py:41`). O `now()` do Postgres
é o horário de **início da transação**, não do INSERT: duas mensagens gravadas
dentro da mesma transação recebem o mesmo timestamp e a ordem entre elas passa
a ser indefinida.

**Por que foi adiado:** hoje cada requisição é a sua própria transação e grava
uma mensagem só, então o empate não é alcançável pelas rotas. E, sobretudo,
**isto é o legacy verbatim** — a paridade proíbe mudar dentro deste bloco.

**O que custaria:** `.order_by(SupportMessage.created_at, SupportMessage.id)`.
Uma linha, e sai de graça: os ids são UUIDv7 (`app/ids.py`), que ordena no
tempo, então o desempate é o próprio relógio com mais resolução. Faça junto com
a primeira mudança que já quebre paridade.

### 9.6 Nenhuma suíte da frota pega divergência entre modelo e migration

**Este é o item de maior valor do bloco D.** É também o mais fácil de não
enxergar, porque o sintoma é uma suíte **verde**.

**Onde:** `tests/conftest.py:40` (`Base.metadata.create_all`) neste serviço, e
o equivalente nos outros cinco.

**O que é:** o schema de teste é construído pelos **modelos**, com
`create_all`, e **nenhum teste da frota invoca o Alembic**. Medido, da raiz de
`back-end/`:
`grep -rn "compare_metadata\|autogenerate\|upgrade head" --include="*.py" */tests/`
não devolve **nenhuma linha** — nem nos seis serviços, nem no legacy. Os
`test_migration_guard*.py` do commerce e do notification não contradizem isso:
eles travam guards de perda de dado dentro de migrations específicas, não a
correspondência entre modelo e schema. Consequência: alguém edita um model, esquece a
migration, e a suíte continua verde — porque ela testa contra o schema
derivado do model que acabou de mudar — enquanto o banco real fica para trás.
O erro só aparece em produção, como coluna que não existe.

Hoje model e migration **concordam** neste serviço, e isso foi conferido contra
o schema vivo, coluna a coluna. Mas concordam porque um humano lembrou de rodar
o autogenerate e ler a saída. Não há nada que force isso a continuar valendo.

O sync-check existe, mas como **ritual de portão**, não como teste: os blocos B
e C o fizeram à mão, em bancos descartáveis `syncchk_*`
([`commerce-parity.md`](commerce-parity.md) §8). Ritual de portão não roda em
CI e não roda no `git push` de ninguém.

**Por que foi adiado:** veio do desenho de fixture da task D2, que é anterior à
task que criou o model, e a correção certa é fleet-wide.

**O que custaria:** um teste por serviço que suba um banco descartável, rode
`alembic upgrade head` e asserte que uma comparação de autogenerate volta
**vazia** — a mesma coisa que o portão já faz à mão, virada em código. Um dia
para os seis, e o retorno é permanente. Atenção a um detalhe que o portão
aprendeu à própria custa: o teste tem que usar um banco **descartável**, nunca
o de dev (veja a §9.7 e a §9.12).

### 9.7 A engine de módulo aponta para o banco de **dev**

**Onde:** `app/database.py:6` — `engine = create_async_engine(settings.database_url)`,
no corpo do módulo.

**O que é:** `settings.database_url` é o `chatbot_db` de **desenvolvimento**,
não o `chatbot_test`. A engine e o `async_session` que sai dela
(`app/database.py:10`) são criados no import, dentro da suíte inclusive. Quem
protege o teste é o `dependency_overrides[get_db]` do `conftest.py:103`, que
troca a sessão nas rotas — proteção que só cobre quem **recebe** a sessão por
injeção.

**O perigo não se materializou, e é importante dizer isso:** as duas funções de
serviço recebem `db: AsyncSession` como parâmetro
(`app/services/suporte.py:10` e `:34`), e nenhum call site alcança
`async_session` diretamente. O código de hoje está certo.

**Por que está registrado mesmo assim:** é uma armadilha armada para o
próximo. Na primeira função de serviço que abrir a própria sessão com
`async_session()` em vez de receber uma — o idioma óbvio para uma task
assíncrona, um comando de manutenção ou um consumidor de evento — a suíte passa
a **escrever no banco de dev**, sem override que a pegue e sem teste que falhe.

**O que custaria:** ou fazer o `Settings` recusar apontar para o banco de dev
quando `PYTEST_CURRENT_TEST` está no ambiente, ou (mais limpo e sem mágica)
criar a engine dentro de uma factory em vez de no corpo do módulo, para que o
teste possa construí-la apontando para outro lugar. Meio dia, fleet-wide.

### 9.8 Uma coluna, dois esquemas de UUID

**Onde:** `app/models/suporte.py:31-32` — `default=new_uuid` na linha 31,
`server_default=text("gen_random_uuid()")` na 32.

**O que é:** os dois caminhos geram versões diferentes de UUID. `new_uuid`
(`app/ids.py`) devolve **v7**, e o próprio arquivo justifica a escolha pela
localidade de inserção em B-tree; `gen_random_uuid()` do Postgres devolve
**v4**, que é aleatório e joga fora exatamente essa propriedade. Uma linha
gravada por fora do ORM — `psql`, um seed, outro serviço — cai numa posição
arbitrária do índice.

**Por que foi adiado, e por que a escolha é defensável:** o PG 17 não tem
gerador nativo de v7, então não existe `server_default` que preserve a
propriedade sem instalar extensão. O `server_default` está ali como rede de
segurança para o insert que escapa do ORM, e nesse papel ele é o correto. Nada
grava nesta tabela por fora do ORM hoje.

**O que custaria:** um comentário de uma linha na coluna dizendo que o
`server_default` é um backstop v4 consciente. O que **não** se quer é que
alguém leia as duas linhas, conclua que é inconsistência e "arrume" uma delas.

### 9.9 `new_uuid` está na terceira cópia

**Onde:** `app/ids.py`, `commerce-service/app/ids.py` e
`legacy/app/core/ids.py`.

**O que é:** a mesma função, copiada pela terceira vez. Duas cópias eram
defensáveis sob KISS — a regra de três linhas repetidas valendo mais que uma
abstração prematura. Três cópias é o ponto em que a regra vira o contrário de
si mesma, e é exatamente o critério do `packages/edu-common`: geração de id não
é config, é a forma de uma chave primária que atravessa serviços.

**Por que foi adiado:** mover para o `edu-common` toca três projetos e os locks
deles, e o bloco D não podia gastar isso.

**O que custaria:** um módulo no `edu-common`, três imports trocados, e o
`legacy/app/core/ids.py` deixado quieto — ele morre no corte de qualquer forma.
Poucas horas.

### 9.10 Buracos de cobertura do bloco D

Nenhum é regressão: são caminhos que nunca tiveram teste. Os dois são baratos e
podem ir juntos.

| Onde | O que falta | Custo |
|---|---|---|
| `tests/test_support_model.py:21` (`test_sender_defaults_to_user`) | O nome promete mais do que o teste checa: o ORM preenche `sender` **antes** do INSERT (`default="user"`), então o `server_default` nunca é exercido por teste nenhum. O banco tem o default — foi conferido no schema vivo —, mas quem confia no nome do teste está confiando no lugar errado. Fecha com um insert por SQL cru, sem passar pelo ORM. | Uma hora |
| `app/schemas.py:32-33` | O comentário descreve, em prosa, que um corpo só de espaços vira `""` depois do `str_strip_whitespace` e é rejeitado com 422. Nenhum teste cobre esse caso. O comportamento **foi verificado** na revisão, então o comentário não é mentira — mas é prosa segurando uma garantia, e prosa não reprova ninguém. | Uma linha de teste |

### 9.11 Higiene herdada da frota

Sem efeito observável hoje. Estão aqui porque **não são deste serviço**: valem
para os seis, e a correção só faz sentido nos seis de uma vez.

| Onde | O que é | Custo |
|---|---|---|
| `app/database.py:14` (`get_db`) | Sem anotação de retorno, contra o "type hints em toda assinatura pública" do `CLAUDE.md`. Medido na frota: **cinco** dos seis serviços estão assim (`auth-users`, `chatbot`, `commerce`, `learning`, `notification`); o `analytics-service/app/database.py:27` já declara `-> AsyncIterator[AsyncSession]` e é o modelo a copiar. | Minutos, se forem os cinco |
| `app/database.py:11` | `declarative_base()` é a API da SQLAlchemy 1.4; a forma 2.x é `class Base(DeclarativeBase)`. Três linhas acima há um comentário se parabenizando por não carregar formas 1.4. Idêntico nos **seis** serviços — trocar em um só deixa a frota mais desigual do que está. | Meio dia, nos seis |
| `tests/conftest.py:107` | `app.dependency_overrides.clear()` apaga **todos** os overrides, não só o de `get_db`, e está **fora de um `finally`**: uma exceção que escape do context manager do client vaza o override para os testes seguintes. Foi ditado pelo plano, verbatim, e é a forma que a frota usa. Correção barata e óbvia: `finally: app.dependency_overrides.pop(get_db, None)`. | Minutos por serviço |

### 9.12 O que o portão do bloco D fechou, e o que deixou aberto

O portão nomeou quatro lacunas de verificação. **Três foram fechadas depois**,
com medição, e não devem ser herdadas como abertas por quem ler um relatório
antigo. A quarta continua aberta, de propósito.

**Fechada — caminho de clone limpo.** O usuário autorizou destruir os volumes
Docker depois de um `pg_dumpall` **conferido, não presumido**:
`/home/elias/edu-backup-2026-08-10.sql`, 101292 bytes, com o conteúdo contado —
12 pedidos, 2 mensagens de suporte (as do legacy) e 2 usuários. Depois de
`docker compose down -v` e de uma subida do zero, `chatbot_db` e `chatbot_test`
apareceram criados **pelo script do `initdb.d`, no volume virgem**, sem ninguém
rodar `make services-dbs`. Essa é a prova de verdade da armadilha de linha de
mount descrita em [`microservices.md`](microservices.md) §11 (o compose monta o
`initdb.d` **script a script**, então um script novo sem a linha de mount vira
no-op silencioso) — e ela não mordeu.

**Fechada — `make services-migrate` de ponta a ponta.** Roda até o fim e **sai
com 0**, passando por `→ chatbot-service` e por
`Running upgrade -> 36a408e36e8d, baseline schema`. O `chatbot_db` no volume
zerado ficou com exatamente `alembic_version` e `support_messages`. Havia uma
pré-condição operacional, e ela está registrada como armadilha em
[`microservices.md`](microservices.md) §11: a imagem do chatbot precisou ser
**reconstruída** antes, porque `make stack-up` é `docker compose up -d` sem
`--build` e a imagem em cache não continha a árvore `alembic/`.

**Fechada — rede, granian, imagem Docker e gateway.** Pelo gateway na 8100, com
um bearer de aluno: `POST /api/support` → **201** devolvendo a conversa inteira
(duas mensagens depois do segundo POST); `GET /api/support` → uma **lista**
JSON, com as chaves exatamente `['body', 'created_at', 'id', 'sender']`, em
ordem cronológica e com ids UUIDv7. Um segundo aluno recebeu `[]` com HTTP
**200** — indistinguível de uma conversa vazia, sem vazar sinal de existência.
Requisição sem header recebeu **403**, confirmando a divergência nº 2 da §9.1
contra a pilha real, e não só em processo.

**Aberta, e corretamente — cinco dos seis sync-checks de schema não foram
re-executados.** Re-executá-los significa aplicar migrations pendentes a bancos
de serviço **vivos**. Só o `commerce_db` tem **12** pendentes, três delas
destrutivas por construção, com `downgrade()` que levanta erro de propósito:
recuperação seria restore de backup. Os blocos B e C checaram esses cinco
([`commerce-parity.md`](commerce-parity.md) §8) e nada mudou neles no bloco D.
Isto é **recusa deliberada, não esquecimento** — e some sozinho quando a §9.6
virar teste, que é o argumento mais forte a favor dela.

### 9.13 Consolidação do fechamento da fase 2 — sem dono

**O que é:** cada um dos quatro blocos da fase 2 produziu a sua própria lista
de asserções adaptadas e de carve-outs. Ninguém as juntou num inventário só, e
a fase 4 precisa **de um**, não de quatro — é dela a pergunta "o que exatamente
o app deixa de ter quando o monolito sair do ar". A revisão do portão do bloco
D marcou isto como fora do escopo do portão, o que está certo, e não atribuiu
dono, o que deixa o item órfão.

**O que não pode se perder no caminho** — os três carve-outs declarados de fase
3, hoje registrados na §9.5 do [`commerce-parity.md`](commerce-parity.md):

1. `legacy/tests/modules/products/test_image_upload.py` — upload de imagem de produto;
2. `legacy/tests/modules/orders/test_lifecycle.py` — ciclo de vida automático do pedido;
3. `legacy/tests/modules/orders/test_status_pipeline.py` — pipeline de status por Celery.

E, junto deles, a **metade de escrita** de `legacy/tests/core/test_storage.py`:
o caminho de leitura foi classificado como carve-out, mas `put_object` e
`delete_object` do commerce vão para produção sem um teste que exercite a
implementação real.

**O que custaria:** um dia de leitura dos quatro registros e uma tabela só.
Barato agora, e caro exatamente quando ninguém mais lembrar por que uma
asserção do legacy foi adaptada.
