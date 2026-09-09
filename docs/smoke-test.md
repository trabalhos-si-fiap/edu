# Smoke test do corte (specs A, B e C)

**Para que serve:** confirmar, em cerca de trinta minutos, que a plataforma
inteira funciona sobre um backend só depois que o monolito foi apagado. Não é
suíte de regressão — as 968 asserções de backend e as 201 do Flutter (medidas
em 2026-09-09, ao fechar a spec C) já rodam em CI e cobrem unidade e
integração. Este documento cobre o que teste automatizado não alcança: um
humano atravessando o produto de ponta a ponta, alternando entre os quatro
perfis, contra o stack de verdade.

**Quando rodar:** depois do runbook de corte da §5 de
[`back-end/microservices.md`](back-end/microservices.md) — e, para as etapas
da spec B, depois do runbook "Aplicando a spec B a um stack existente" da mesma
seção —, e de novo na véspera de qualquer apresentação.

**Regra de leitura:** a seção [O que não funciona, e não é
bug](#o-que-não-funciona-e-não-é-bug) é obrigatória antes de começar. Metade
dos "defeitos" que aparecem num smoke test deste sistema são lacunas
conhecidas e documentadas, e confundi-las com regressão na véspera da
apresentação custa horas.

## Preparação

O runbook do corte tem que ter rodado inteiro, na ordem. Sem `make
stack-rebuild`, as imagens ainda contêm o código anterior à spec A e quatro
das correções daquela entrega ficam inertes sem nenhum erro visível.

Para as etapas da spec B, o runbook "Aplicando a spec B a um stack existente"
(§5 do `microservices.md`) também tem que ter rodado, e nesta ordem:
`stack-rebuild` → `stack-up` → `services-migrate` → `services-seed` →
`npm run build` no `web-admin`. Migration antes do seed é obrigatório: o seed
escreve em colunas que só existem depois dela.

Para as etapas da spec C não há seed novo — só duas revisions aditivas
(`c1d2e3f4a5b6` no `commerce_db`, `d4c5b6a7e8f9` no `notification_db`) — mas
`make stack-rebuild` continua obrigatório: o `commerce-service` ganhou uma
dependência nova (`apscheduler`) e um `app/scheduler.py` importado no
`main.py`, e uma imagem em cache não os tem. Confira `EMAIL_BACKEND`
(`console` por padrão, não fala com a rede) no `.env`, e deixe
`AVANCO_AUTOMATICO_SEGUNDOS` **ausente** a menos que o critério de pronto 6
seja exatamente o que você quer exercitar — ver
[`back-end/order-flow.md`](back-end/order-flow.md) §4.

Você vai precisar de:

- A senha das contas de demonstração (`DEMO_ACCOUNTS_PASSWORD`, mínimo de 8
  caracteres com pelo menos um especial).
- Um emulador ou dispositivo com o app. `make front` acerta a URL sozinho.
- Um terminal com acesso ao Postgres para as conferências de banco:
  `docker exec -i edu-postgres psql -U edu -d <banco> -c "..."`.

As quatro contas são `aluno@demo.edu`, `separador@demo.edu`,
`entregador@demo.edu` e `admin@demo.edu`, todas com a mesma senha. A tabela
está em [`back-end/demo-accounts.md`](back-end/demo-accounts.md).

## Etapa 0 — a frota está de pé e é a nova

Antes de tocar no app, oito conferências de trinta segundos. Elas separam
"o sistema está no ar" de "o sistema no ar é o que eu acabei de construir",
que é a distinção que o dia do corte torna cara.

| # | Conferência | Como | Esperado |
|---|---|---|---|
| 0.1 | Nenhum container de monolito | `docker compose -f back-end/docker-compose.yml ps --services` | Sete serviços mais a infra. Nada chamado `api`, `worker` ou `migrate`. |
| 0.2 | O gateway responde | `curl -s localhost:8100/health` | 200. |
| 0.3 | As filas nasceram com dead-letter | `docker exec edu-rabbitmq rabbitmqctl list_queues name arguments` | As onze filas de trabalho (sete até a spec B; a spec C acrescenta `notification.staff_created`, `notification.order_created`, `notification.occurrence_resolved` e `notification.shipment_created` — [`back-end/microservices.md`](back-end/microservices.md) §8) trazem `x-dead-letter-exchange`, e existe uma `edu.events.dead`. |
| 0.4 | O catálogo foi semeado uma vez só | `docker exec -i edu-postgres psql -U edu -d commerce_db -c "SELECT count(*), count(DISTINCT name) FROM products;"` | Os dois números iguais. Diferentes significa que a corrida do seed aconteceu — o que o lock consultivo da spec A existe para impedir. |
| 0.5 | O schema da spec B foi aplicado | `docker exec -i edu-postgres psql -U edu -d commerce_db -c "\\dt estoque_ajustes carriers"` e `-c "SELECT version_num FROM alembic_version;"` | As duas tabelas existem e a revision é `b1a2c3d4e5f6`. Se não, `make services-migrate` não rodou (ou rodou contra uma imagem em cache). |
| 0.6 | O seed da spec B rodou | `docker exec -i edu-postgres psql -U edu -d commerce_db -c "SELECT nome, ativo, origem_rotulo FROM fornecedores;"` e `-c "SELECT count(*) FROM estoque WHERE fornecedor_id IS NULL;"` | Dois fornecedores com origem preenchida, e **zero** linhas de estoque sem fornecedor. `ativo` é `f` para `Edu` e `t` para o parceiro externo — isso é o esperado, não bug: `Edu` é o fornecedor da própria loja e não uma vitrine, e a seção de parceiros do app deve listar **um** elemento. Estoque órfão significa que o seed não adotou os produtos próprios: a seção de parceiros do app fica vazia e todo pedido novo sai sem origem. |
| 0.7 | O schema da spec C foi aplicado | `docker exec -i edu-postgres psql -U edu -d commerce_db -c "\\dt carregamentos posicao_entrega"` e `-c "SELECT version_num FROM alembic_version;"`; e `docker exec -i edu-postgres psql -U edu -d notification_db -c "\\dt staff"` e `-c "SELECT version_num FROM alembic_version;"` | As duas tabelas existem no `commerce_db` com a revision `c1d2e3f4a5b6`, e `staff` existe no `notification_db` com a revision `d4c5b6a7e8f9`. Se não, `make services-migrate` não rodou (ou rodou contra uma imagem em cache — veja o aviso de `apscheduler` acima). |
| 0.8 | O registro de staff tem as três contas | `docker exec -i edu-postgres psql -U edu -d notification_db -c "SELECT papel, nome FROM staff;"` | Três linhas — `admin`, `separador`, `entregador` — uma por conta de demonstração não-aluno. Zero linhas significa que o `staff.created` de cada uma foi publicado para uma fila que ainda não existia quando o seed rodou (mesma classe de armadilha de ordem que a §5 do `microservices.md` descreve para `student.created`): recrie as contas de demo depois de aplicar a migration e reiniciar o `notification-service`. |

A 0.3 é a que pega a imagem velha: se as filas não têm `arguments`, o
`edu-common` que está rodando é anterior à spec A, e o rebuild não
aconteceu ou não pegou. A 0.5 e a 0.6 fazem o mesmo pela spec B; a 0.7 e a
0.8, pela spec C.

## Etapa 1 — aluno: catálogo, carrinho, pedido

Entre com `aluno@demo.edu`.

1. A home abre. **Meta e prazo aparecem preenchidos** — hoje são valores fixos
   na tela (`home_screen.dart`), não vêm do backend. É mock conhecido, escopo
   da spec D.
2. Abra a loja. Os seis produtos do seed aparecem, **com foto**. Foto quebrada
   aponta para o MinIO, não para o corte.
3. **Role a loja até a seção "Parceiros"**
   (`marketplace_screen.dart` → `partners_section.dart`). Ela lista um bloco
   por fornecedor ativo, com o rótulo de origem de cada um. Se estiver vazia,
   o `make services-seed` da spec B não rodou — veja a triagem no fim deste
   documento.
4. Abra o parceiro externo e adicione um item dele ao carrinho.
5. Volte para o catálogo e tente adicionar um produto próprio (do fornecedor
   "Edu"). **Uma mensagem tem que aparecer na tela**, com este texto:

   > Seu carrinho já tem itens de outro parceiro. Finalize ou esvazie o
   > carrinho antes de misturar.

   A frase vem do backend (409 de `POST /api/cart/items`), verbatim — o app
   não guarda cópia dela. Se o app não fizer **nada** ao misturar parceiros,
   isso é regressão.
6. Esvazie o carrinho e adicione dois produtos do **mesmo** parceiro, com
   quantidades diferentes.
7. Feche o pedido escolhendo PIX. **O código vem do servidor**
   (`POST /api/orders/{id}/confirm-payment`), não do cliente. Confira que ele
   é **estável**: feche e reabra a caixa de diálogo, e o código tem que ser o
   mesmo — ele é derivado do id do pedido. Antes da spec B era sorteado a cada
   chamada, e reabrir a caixa dava outro código.

   > O código tem a **forma** de um EMV de PIX e não é pagável em lugar
   > nenhum. Não há integração com provedor de pagamento neste sistema.

8. Anote os oito primeiros caracteres do id do pedido, em maiúsculas. É o
   identificador que a etapa 4 vai conferir contra o título da notificação.

O pedido nasce em `pending` para o aluno e `CRIADO` internamente.

## Etapa 2 — admin: confirmar o pagamento e despachar

Saia e entre com `admin@demo.edu`. A tela inicial é o dashboard.

1. Liste os pedidos (`GET /api/admin/orders`). O pedido da etapa 1 está lá.
2. Confirme o pagamento (`PATCH /api/admin/orders/{id}/confirm-payment`). O
   pedido atravessa `CONFIRMADO` e para em `AGUARDANDO_SEPARACAO` na mesma
   chamada — não existe simulador que faça essa transição sozinho, então parar
   em `CONFIRMADO` deixaria a fila de separação vazia para sempre.
3. Atribua um separador (`PATCH /api/admin/orders/{id}/assign-picker`).
4. Confira o estoque (`GET /api/admin/inventory`) e faça um ajuste
   (`PATCH /api/admin/inventory/{estoque_id}/adjust?quantidade=&motivo=`).
   Desde a spec B o `motivo` é **obrigatório** e o id do path é o da linha de
   **estoque**, não o do produto. Cada ajuste grava uma linha de auditoria em
   `estoque_ajustes`, legível em
   `GET /api/products/{product_id}/stock-adjustments`.
5. **Crie o carregamento que a etapa 5 vai usar** (spec C). Na aba
   "Carregamentos" (app ou painel), escolha a transportadora do seed e crie
   um carregamento (`POST /api/shipments`, corpo `{transportadora_id}`). A
   resposta traz `codigo` e `senha` **uma única vez** — anote os dois, eles
   não voltam em nenhuma listagem nem em nenhuma tela depois desta. Atribua o
   pedido da etapa 1 a ele (`POST /api/shipments/{id}/orders`, corpo
   `{pedido_id}`); um pedido de origem diferente da já congelada no lote
   daria 409. O que a credencial autoriza está em
   [`back-end/order-flow.md`](back-end/order-flow.md) §2.

`PATCH /api/admin/orders/{id}/confirm-payment` **gera notificação**: o
pedido atravessa `CONFIRMADO` (suprimido, transitório) e para em
`AGUARDANDO_SEPARACAO`, que avisa o aluno **e** o separador (tabela de
destinatário da spec C, [`back-end/order-flow.md`](back-end/order-flow.md)
§5 — confira na seção "Conferência do push" mais abaixo). `assign-picker` e
`assign-deliverer`, e a criação do carregamento em si, continuam sem publicar
notificação — não mudam o status do pedido.

## Etapa 3 — separador: a fila e a separação

Saia e entre com `separador@demo.edu`. O login roteia direto para a fila de
separação, sem passar pela home do aluno — isso é o `switch` de papel em
`login_screen.dart` e é parte do que se está testando.

1. A fila (`GET /api/picking/queue`) mostra o pedido.
2. Inicie a separação (`PATCH /api/picking/{id}/start`). O pedido vai para
   `EM_SEPARACAO`.
3. Marque os itens e finalize (`PATCH /api/picking/{id}/finish`). O pedido vai
   para `SEPARADO`.

Toda transição publica `order.status_changed`
(`app/routers/separacao.py::transicionar_pedido`) — não só esta; o que a
spec C mudou não foi a publicação (já existia), foi o **destinatário** de
cada uma (seção "Conferência do push" mais abaixo). O passo 2
(`EM_SEPARACAO`) avisa só o aluno; o passo 3 (`SEPARADO`) também. É este
último que a etapa 4 vai conferir.

## Etapa 4 — a notificação chegou, com o identificador certo

Volte para `aluno@demo.edu` e abra a tela de notificações.

Deve existir uma notificação cujo título é `Pedido #XXXXXXXX`, com os oito
caracteres que você anotou na etapa 1, em maiúsculas. **Esse é o teste da task
3 da spec A**: antes, o título trazia os 36 caracteres do UUID.

Conferência de banco, se a tela deixar dúvida:

```bash
docker exec -i edu-postgres psql -U edu -d notification_db \
  -c "SELECT titulo, pedido_id FROM notificacoes ORDER BY criado_em DESC LIMIT 5;"
```

O `titulo` traz o identificador curto; a coluna `pedido_id` continua guardando
o UUID inteiro. O truncamento é de exibição, não de dado — se `pedido_id`
estiver truncado, isso sim é bug.

## Etapa 5 — entregador: coleta e entrega

Saia. Em vez de `entregador@demo.edu`, entre pelo **código do carregamento**
criado na etapa 2 (spec C) — na tela de login, toque em "Entrar com código de
carregamento" e informe `codigo`, `senha`, seu nome e um contato
(`POST /api/shipments/login`). O token vale só para os pedidos deste
carregamento, por até 12 horas, não é um papel de usuário da frota, e o
primeiro acesso grava quem pegou a carga (`entregador_nome`/`entregador_contato`/
`aberto_em`). Detalhe completo em
[`back-end/order-flow.md`](back-end/order-flow.md) §2.

> `entregador@demo.edu` continua funcionando pelo caminho antigo — login
> normal, sem código. As quatro rotas de `/delivery` aceitam os dois atores.
> Use-a se quiser demonstrar o fluxo sem carregamento, ou para a conferência
> de push do entregador (mais abaixo) — uma sessão aberta só pelo código não
> corresponde a nenhum usuário do registro de staff, então não recebe
> notificação própria.

1. A fila (`GET /api/delivery/queue`) mostra o pedido separado — filtrada
   pelo carregamento quando a entrada foi por código.
2. Colete (`PATCH /api/delivery/{id}/collect`). O pedido vai para
   `EM_TRANSITO`, e o aluno passa a ver `out_for_delivery`. É neste passo que
   o backend congela a coordenada de destino e o simulador de posição
   (`app/services/simulador_posicao.py`) começa a andar — **posição
   simulada: não há entregador real nem GPS neste sistema**, ver
   [`back-end/order-flow.md`](back-end/order-flow.md) §3. O mapa do
   comprador (tela de rastreio da etapa 1) passa a mostrar a posição se
   deslocando a cada ~10 segundos.
3. Confira `GET /api/delivery/mine` — o pedido aparece na lista do entregador.
4. Entregue (`PATCH /api/delivery/{id}/deliver`). O pedido vai para `ENTREGUE`.

**As duas transições publicam notificação**, endereçada pela tabela de
destinatário da spec C: a coleta avisa o aluno; a entrega avisa o aluno e o
admin (`back-end/order-flow.md` §5, seção "Conferência do push" abaixo). O
entregador nunca é notificado das próprias ações.

## Etapa 6 — ocorrência de falta de estoque

O caminho de exceção, e o segundo lugar que gera notificação.

1. Como separador, abra uma ocorrência de falta
   (`POST /api/occurrences/stock-shortage`) num pedido em separação.
2. Como aluno, a notificação `Pedido #XXXXXXXX: item em falta` aparece.
3. Ainda como aluno, resolva a ocorrência
   (`POST /api/occurrences/{id}/resolve`) — aceitando a substituição ou
   cancelando o pedido.
4. Se cancelar, o pedido vai para `CANCELADO` e o aluno vê `cancelled`, com o
   stepper fora do fluxo em vez de travado no passo 0. Se aceitar a
   substituição (ou remover o item), o pedido volta para `EM_SEPARACAO` — o
   separador ainda precisa pegar o item da prateleira — e **o separador é
   notificado** (`order.occurrence_resolved`, spec C): é ele quem estava
   bloqueado esperando esta decisão (`finalizar_separacao` recusa terminar
   com ocorrência aberta).

O mesmo vale para atraso de entrega (`POST /api/occurrences/delivery-delay`),
que gera `Pedido #XXXXXXXX: atraso na entrega`.

## Conferência do push, perfil por perfil

Critério de pronto 3 (spec C): cada transição gera push no perfil certo,
**verificado no aparelho**. A tabela completa de destinatário por transição
está em [`back-end/order-flow.md`](back-end/order-flow.md) §5; aqui vai o
roteiro para conferir, voltando rapidamente a cada perfil depois das etapas
acima. O sino que as telas de separador, entregador e admin ganharam nesta
spec (antes só o aluno tinha) abre a mesma `GET /api/notifications` que o
aluno já usava — "push" aqui é a notificação **dentro do app**, não um push
real de aparelho (ver a lacuna abaixo).

| Perfil | Quando conferir | O que deve estar lá |
|---|---|---|
| Admin, separador | a qualquer momento depois da etapa 1 | aviso de pedido criado (`order.created`) — o único evento que nunca notifica o aluno |
| Aluno, separador | depois do passo 2 da etapa 2 (confirmar pagamento) | `Pedido #XXXXXXXX` — foi para `AGUARDANDO_SEPARACAO` |
| Aluno | depois do passo 3 da etapa 3 (separação finalizada) | `Pedido #XXXXXXXX` — está `SEPARADO` (é a etapa 4) |
| Entregador | depois do passo 3 da etapa 3 | veja pela conta `entregador@demo.edu` (login normal), não pela sessão aberta por código de carregamento na etapa 5 — só a conta registrada aparece no registro de staff |
| Aluno | depois da coleta, na etapa 5 | `Pedido #XXXXXXXX` — saiu para entrega |
| Aluno, admin | depois da entrega, na etapa 5 | `Pedido #XXXXXXXX` — entregue |
| Separador | depois de resolver a ocorrência aceitando substituição/remoção, na etapa 6 | aviso de ocorrência resolvida |
| Aluno, admin | se cancelar pela ocorrência, na etapa 6 | `Pedido #XXXXXXXX` — cancelado |

## Etapa 7 — o painel: parceiro, produto, estoque e transportadora

Esta etapa é a spec B inteira pelo lado do administrador, e roda no navegador,
não no app. Suba o painel com `cd web-admin && npm start` (ou sirva o `dist/`
do `npm run build`) e entre com `admin@demo.edu`.

O painel fala com o **gateway**, na porta 8100. Se ele tentar `localhost:8080`
ou `/api/v1/...`, o build em execução é anterior à spec B.

1. **Parceiro com origem.** Em Parceiros, cadastre um parceiro novo com nome,
   contato e rótulo de origem (por exemplo, "Osasco, SP") com latitude e
   longitude. Ele aparece na lista.
2. **Produto sob o parceiro.** Em Produtos, crie um produto e **escolha o
   parceiro novo no seletor**. O seletor é alimentado por `GET /api/partners`.
   O produto nasce com uma linha de estoque no parceiro escolhido, na mesma
   transação — não existe produto sem estoque.
   - Repita com o **mesmo `sku`** não-vazio: tem que dar erro de duplicidade
     (409), não 500.
3. **Ajuste de estoque com motivo.** Abra o modal de ajuste do produto novo.
   **O motivo tem que nascer em branco** — se um preset já vier selecionado, é
   regressão: o campo existe para registrar decisão humana.
   Ajuste a quantidade, escolha um motivo, salve.
4. **Confira a trilha.** A auditoria do produto tem que mostrar a linha do
   ajuste, com quantidade anterior, quantidade nova, motivo e autor:

   ```bash
   docker exec -i edu-postgres psql -U edu -d commerce_db \
     -c "SELECT estoque_id, quantidade_anterior, quantidade_nova, motivo, autor_id
         FROM estoque_ajustes ORDER BY criado_em DESC LIMIT 5;"
   ```

   `autor_id` é o id do admin que fez o ajuste. Linha ausente é bug: o ajuste
   e a auditoria sobem na mesma transação.
5. **Transportadora.** Em Transportadoras, cadastre uma (nome, localidade,
   e-mail, prazo médio, SLA). Ela nasce `ACTIVE`. Alterne o status para
   `INACTIVE` e de volta.
6. **Ocorrência de dano.** Abra uma ocorrência do tipo `DANO` sobre o pedido da
   etapa 1, apontando a transportadora nova. Ela aparece na lista de
   ocorrências, filtrável por transportadora, tipo e status.
7. **Feche a ocorrência** pelo painel. O status vai para resolvida.
   - Conferência que vale fazer uma vez: **o aluno não consegue fechar essa
     ocorrência por conta própria.** `POST /api/occurrences/{id}/resolve` com o
     token do aluno tem que dar 400 numa ocorrência de transportadora. Se der
     200, o guard que separa os dois fluxos sumiu.
8. **O interruptor da seção de parceiros.** Ainda no painel, **desative** o
   parceiro externo (o do seed). Volte ao app e recarregue a loja: a seção de
   Parceiros perde aquele parceiro **sem recompilar nada**. Reative e ele
   volta. Quem decide isso é `fornecedores.ativo`, não código.

## Etapa 8 — a fila morta funciona

Vale rodar uma vez, porque é a correção mais difícil de perceber pela tela e a
que já engoliu notificação em silêncio antes.

A topologia é o que prova a correção, e ela se confere sem publicar nada:

```bash
docker exec edu-rabbitmq rabbitmqctl list_exchanges name type | grep dlx
docker exec edu-rabbitmq rabbitmqctl list_bindings source_name destination_name | grep dead
```

Esperado: `edu.events.dlx` do tipo `fanout`, e um binding dela para
`edu.events.dead`. Sem a exchange, uma mensagem rejeitada é **descartada em
silêncio** — o comportamento que a spec A corrigiu, e sinal de que o
`edu-common` em execução é o antigo.

Para exercitar o caminho de verdade, publique uma mensagem com corpo inválido
numa das routing keys consumidas e confira que `edu.events.dead` ganha uma
mensagem. Confira a sintaxe com `docker exec edu-rabbitmq rabbitmqadmin --help`
antes: o `rabbitmqadmin` mudou de sintaxe no RabbitMQ 4.x, e esta imagem é a
`4.2.3-management-alpine`.

O nome do container vem de `COMPOSE_PROJECT_NAME` (`edu` nesta máquina); o do
Postgres é fixo, `edu-postgres`.

## O que não funciona, e não é bug

Tudo nesta lista foi verificado na árvore. Nenhum item é regressão desta
entrega; cada um é lacuna conhecida com dono.

| Comportamento | Por quê | Dono |
|---|---|---|
| Não existe push real de aparelho (FCM) | O Firebase saiu do app na spec A, porque quem enviava era o monolito. A spec C endereçou a notificação por transição a quem precisa dela (aluno **e** staff, ver [`back-end/order-flow.md`](back-end/order-flow.md) §5) mas não trouxe FCM de volta — as notificações existem **na tela do app**, lidas de `GET /notifications` e abertas pelo sino. | não agendado |
| "Esqueci minha senha" não manda e-mail | O OTP é gerado, hasheado e guardado, e a resposta é sempre 200 — mas não existe provedor de e-mail configurado (`auth.py:229-231`). O remetente do reset continua sem existir; o primeiro envio real do backend desde a spec A foi a credencial do carregamento (spec C, e-mail à transportadora), não este. | não agendado |
| O pedido não avança sozinho | Continua verdadeiro **por padrão** — mas deixou de ser "não foi portado": a spec C trouxe uma rede de segurança equivalente (`app/services/avanco_automatico.py`), desligada por padrão (`AVANCO_AUTOMATICO_SEGUNDOS` ausente = `0`) e sempre perdendo para ação manual. Ligar é opt-in, com prazo longo de propósito — ver [`back-end/order-flow.md`](back-end/order-flow.md) §4. | ninguém — é o desenho |
| Meta, prazo e pontuação da home e do perfil são fixos | Valores escritos na tela, sem backend por trás. | spec D |
| Os códigos de PIX e boleto não são pagáveis | São emitidos pelo backend (`codigos_pagamento.py`) com a **forma** de um EMV e de uma linha digitável, sem provedor de pagamento por trás. O CRC do EMV é fixo e falso. Deliberado. | ninguém — é o desenho |
| O `web-admin` não tem suíte de teste | A spec B não criou uma (decisão D11). A verificação é `npm install && npm run build`: o build AOT faz type-check de template. Baseline: exit 0 com **três** avisos de budget SCSS. | não agendado |
| O painel desloga sozinho quando o access token expira | Não há refresh de token no `web-admin`. | não agendado |
| O dashboard perdeu o bloco de alunos, o gráfico de atividade e três mini-painéis | Não existe rota `/dashboard`; o painel é construído sobre `GET /analytics/executive-summary` mais dois `total`. Nada foi inventado no cliente. A spec C não tocou o dashboard (só acrescentou a aba de carregamentos). Lista completa em [`back-end/partners-inventory-carriers.md`](back-end/partners-inventory-carriers.md), §10. | spec D |
| "PARCEIROS ATIVOS" e "TRANSPORTADORAS ATIVAS" aparecem sob "(últimos N dias)" | São totais **atuais**, não do período. Os números estão certos; o cabeçalho acima deles é que não se aplica. | não agendado |
| "OCORRÊNCIAS ABERTAS" da tela de transportadoras conta ocorrência de estoque também | O backend não tem filtro "só de transportadora"; a contagem é `GET /occurrences?status=ABERTA` sem `carrier_id`. | não agendado |
| Busca e filtro de estoque baixo acontecem no cliente | `GET /admin/inventory` não tem `search` nem `lowStock`. A tela junta produto e estoque no cliente por falta de rota agregada. | não agendado |
| Com mais de 100 parceiros, alguns somem do seletor de produto; o CSV de transportadoras e o filtro de transportadora das ocorrências truncam em 100 | Teto de `limit` no servidor; esses três consumidores carregam uma página só. As **telas** paginam e enxergam tudo. | não agendado |
| O estoque avisa "mostrando as primeiras 2000" com exatamente 2000 linhas | `GET /admin/inventory` não devolve `total`, então o painel não distingue "teto batido" de "o teto coincidiu com o fim". Falso positivo do aviso, nada é cortado. | não agendado |
| A transportadora nasce com avaliação `0` | O formulário não coleta `rating`. Pré-existente. | não agendado |
| Os seis produtos próprios têm `sku` vazio | Até alguém editá-los. O índice único de `sku` é **parcial** (`WHERE sku <> ''`) justamente para isso. | não agendado |
| Não existe leitura global da trilha de estoque | `estoque_ajustes` só é lida por produto (`GET /products/{id}/stock-adjustments`). | não agendado |
| Um preço com três casas é aceito e arredondado | `price` não tem `decimal_places` no backend. O formulário do painel arredonda e escreve o valor arredondado de volta no campo; o app não cria produtos. | não agendado |
| A suíte não roda alembic | Ela monta o schema com `create_all`. A revision da spec B (`b1a2c3d4e5f6`) é a única desta cadeia com prova de aplicação registrada. | não agendado |

## Triagem de falhas

| Sintoma | Causa mais provável | Confirmação |
|---|---|---|
| Um serviço não sobe, log com `PRECONDITION_FAILED` | Fila antiga, declarada antes da dead-letter exchange | O passo de apagar as sete filas não rodou, ou rodou depois do `stack-up`. Veja a §11 do `microservices.md`. |
| `make services-seed-demo` dá `ModuleNotFoundError` | Imagem anterior à spec A | `make stack-rebuild` não rodou. |
| O seed de demonstração diz que a variável não está definida | A senha não chegou no container | O alvo passa `-e`; se você chamou `docker compose exec` à mão, precisa da flag. |
| Doze produtos no catálogo em vez de seis | A corrida do seed aconteceu | Só é possível com o `commerce-service` anterior à spec A. Confirme a imagem. |
| Título de notificação com 36 caracteres | `notification-service` anterior à spec A | Confirme a imagem. |
| O aluno de demonstração não tem progresso nem aparece no analytics | Os eventos do seed foram publicados para filas que ninguém consumia | Os passos 4 e 5 do runbook rodaram depois do seed. Apague as quatro linhas `@demo.edu` de `auth_db.users` e semeie de novo. |
| `make front` conecta em porta errada | `.env` sem `GATEWAY_PORT_EXTERNAL` | O Makefile cai no default 8100; confira `back-end/.env`. |
| A seção "Parceiros" do app está vazia | O seed da spec B não rodou | `make services-seed`. Sem ele nenhum produto pertence a parceiro nenhum, e todo pedido novo sai sem origem. |
| Todo pedido novo sai sem origem de expedição | O mesmo | `SELECT count(*) FROM estoque WHERE fornecedor_id IS NULL;` em `commerce_db`. |
| O painel dá 404 ou não carrega nada | Build anterior à spec B, ou apontando para a API Java | `grep -rn "8080\|/api/v1" web-admin/src` tem que voltar vazio. |
| O ajuste de estoque do painel dá 422 | Imagem do `commerce-service` anterior à spec B | `motivo` virou obrigatório na spec B. `make stack-rebuild` e `make services-migrate`. |
| `make services-migrate` reclama de revision desconhecida | Imagem em cache, sem `b1a2c3d4e5f6` | `make stack-rebuild` antes. Veja "Aplicando a spec B a um stack existente" na §5 do `microservices.md`. |
| Login por código de carregamento devolve 401 | Código ou senha errados, ou copiados com ambiguidade — o alfabeto não tem `I`, `O`, `0`, `1` | Recrie o carregamento e copie `codigo`/`senha` da resposta de criação — eles não voltam em nenhuma tela depois. |
| A fila do entregador (login por código) aparece vazia | O pedido não foi atribuído a este carregamento | `POST /api/shipments/{id}/orders`, etapa 2 passo 5. |
| O mapa do comprador não mostra o entregador andando | O pedido ainda não foi coletado (a coordenada de destino só é congelada na coleta), ou o simulador está mal configurado | Confira que o passo 2 da etapa 5 (coletar) já rodou; `SIMULADOR_POSICAO_SEGUNDOS` vem ligado por padrão (10s), diferente do avanço automático. |

## Critério de aprovação

O smoke test passa quando as etapas 0 a 7 e a "Conferência do push, perfil
por perfil" completam sem nenhuma falha que não esteja na tabela de lacunas
conhecidas. A etapa 8 é opcional no dia a dia e obrigatória depois de
qualquer mexida no `edu-common`.
