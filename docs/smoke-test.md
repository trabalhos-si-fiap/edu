# Smoke test do corte (spec A)

**Para que serve:** confirmar, em cerca de trinta minutos, que a plataforma
inteira funciona sobre um backend só depois que o monolito foi apagado. Não é
suíte de regressão — as 722 asserções de backend e as 161 do Flutter já rodam
em CI e cobrem unidade e integração. Este documento cobre o que teste
automatizado não alcança: um humano atravessando o produto de ponta a ponta,
alternando entre os quatro perfis, contra o stack de verdade.

**Quando rodar:** depois do runbook de corte da §5 de
[`back-end/microservices.md`](back-end/microservices.md), e de novo na véspera
de qualquer apresentação.

**Regra de leitura:** a seção [O que não funciona, e não é
bug](#o-que-não-funciona-e-não-é-bug) é obrigatória antes de começar. Metade
dos "defeitos" que aparecem num smoke test deste sistema são lacunas
conhecidas e documentadas, e confundi-las com regressão na véspera da
apresentação custa horas.

## Preparação

O runbook do corte tem que ter rodado inteiro, na ordem. Sem `make
stack-rebuild`, as imagens ainda contêm o código anterior à spec A e quatro
das correções desta entrega ficam inertes sem nenhum erro visível.

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

Antes de tocar no app, quatro conferências de trinta segundos. Elas separam
"o sistema está no ar" de "o sistema no ar é o que eu acabei de construir",
que é a distinção que o dia do corte torna cara.

| # | Conferência | Como | Esperado |
|---|---|---|---|
| 0.1 | Nenhum container de monolito | `docker compose -f back-end/docker-compose.yml ps --services` | Sete serviços mais a infra. Nada chamado `api`, `worker` ou `migrate`. |
| 0.2 | O gateway responde | `curl -s localhost:8100/health` | 200. |
| 0.3 | As filas nasceram com dead-letter | `docker exec edu-rabbitmq rabbitmqctl list_queues name arguments` | As sete filas de trabalho trazem `x-dead-letter-exchange`, e existe uma `edu.events.dead`. |
| 0.4 | O catálogo foi semeado uma vez só | `docker exec -i edu-postgres psql -U edu -d commerce_db -c "SELECT count(*), count(DISTINCT name) FROM products;"` | Os dois números iguais. Diferentes significa que a corrida do seed aconteceu — o que o lock consultivo da spec A existe para impedir. |

A 0.3 é a que pega a imagem velha: se as filas não têm `arguments`, o
`edu-common` que está rodando é anterior a esta entrega, e o rebuild não
aconteceu ou não pegou.

## Etapa 1 — aluno: catálogo, carrinho, pedido

Entre com `aluno@demo.edu`.

1. A home abre. **Meta e prazo aparecem preenchidos** — hoje são valores fixos
   na tela (`home_screen.dart`), não vêm do backend. É mock conhecido, escopo
   da spec D.
2. Abra a loja. Os seis produtos do seed aparecem, **com foto**. Foto quebrada
   aponta para o MinIO, não para o corte.
3. Adicione dois produtos ao carrinho, com quantidades diferentes.
4. Feche o pedido escolhendo PIX. **O código PIX é gerado no cliente hoje**
   (`checkout_screen.dart`) — é mock conhecido, escopo da spec B.
5. Anote os oito primeiros caracteres do id do pedido, em maiúsculas. É o
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
   (`PATCH /api/admin/inventory/{id}/adjust`). É o caminho que a spec B vai
   herdar do Java.

**Nenhuma notificação é gerada nesta etapa.** `admin.py` não publica evento
nenhum — verificado. Se você esperar um push aqui e ele não vier, não é
regressão.

## Etapa 3 — separador: a fila e a separação

Saia e entre com `separador@demo.edu`. O login roteia direto para a fila de
separação, sem passar pela home do aluno — isso é o `switch` de papel em
`login_screen.dart` e é parte do que se está testando.

1. A fila (`GET /api/picking/queue`) mostra o pedido.
2. Inicie a separação (`PATCH /api/picking/{id}/start`). O pedido vai para
   `EM_SEPARACAO`.
3. Marque os itens e finalize (`PATCH /api/picking/{id}/finish`). O pedido vai
   para `SEPARADO`.

**O passo 3 é o único do fluxo feliz que publica um evento**
(`separacao.py:111`, `order.status_changed`). É ele que a etapa 4 vai conferir.

## Etapa 4 — a notificação chegou, com o identificador certo

Volte para `aluno@demo.edu` e abra a tela de notificações.

Deve existir uma notificação cujo título é `Pedido #XXXXXXXX`, com os oito
caracteres que você anotou na etapa 1, em maiúsculas. **Esse é o teste da task
3 desta entrega**: antes, o título trazia os 36 caracteres do UUID.

Conferência de banco, se a tela deixar dúvida:

```bash
docker exec -i edu-postgres psql -U edu -d notification_db \
  -c "SELECT titulo, pedido_id FROM notificacoes ORDER BY criado_em DESC LIMIT 5;"
```

O `titulo` traz o identificador curto; a coluna `pedido_id` continua guardando
o UUID inteiro. O truncamento é de exibição, não de dado — se `pedido_id`
estiver truncado, isso sim é bug.

## Etapa 5 — entregador: coleta e entrega

Saia e entre com `entregador@demo.edu`. O login roteia direto para a fila de
entrega.

1. A fila (`GET /api/delivery/queue`) mostra o pedido separado.
2. Colete (`PATCH /api/delivery/{id}/collect`). O pedido vai para
   `EM_TRANSITO`, e o aluno passa a ver `out_for_delivery`.
3. Confira `GET /api/delivery/mine` — o pedido aparece na lista do entregador.
4. Entregue (`PATCH /api/delivery/{id}/deliver`). O pedido vai para `ENTREGUE`.

**Nenhuma das duas transições publica evento.** `entrega.py` não chama
`publish_event` — verificado. O aluno vê o status mudar no rastreio, porque o
rastreio lê o banco, mas **não recebe notificação de "saiu para entrega" nem de
"entregue"**. É lacuna conhecida e é escopo da spec C.

## Etapa 6 — ocorrência de falta de estoque

O caminho de exceção, e o segundo lugar que gera notificação.

1. Como separador, abra uma ocorrência de falta
   (`POST /api/occurrences/stock-shortage`) num pedido em separação.
2. Como aluno, a notificação `Pedido #XXXXXXXX: item em falta` aparece.
3. Ainda como aluno, resolva a ocorrência
   (`POST /api/occurrences/{id}/resolve`) — aceitando a substituição ou
   cancelando o pedido.
4. Se cancelar, o pedido vai para `CANCELADO` e o aluno vê `cancelled`, com o
   stepper fora do fluxo em vez de travado no passo 0.

O mesmo vale para atraso de entrega (`POST /api/occurrences/delivery-delay`),
que gera `Pedido #XXXXXXXX: atraso na entrega`.

## Etapa 7 — a fila morta funciona

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
| Não existe push no celular | O Firebase saiu do app na spec A, porque quem enviava era o monolito. O `notification-service` só guardava o token (`device_token.py:11-14`) e nada enviava para ele. As notificações existem **na tela do app**, lidas de `GET /notifications`. | spec C |
| "Esqueci minha senha" não manda e-mail | O OTP é gerado, hasheado e guardado, e a resposta é sempre 200 — mas não existe provedor de e-mail configurado (`auth.py:229-231`). O remetente morreu com o monolito. | não agendado |
| Sem notificação ao confirmar pagamento, coletar ou entregar | `admin.py` e `entrega.py` não publicam evento nenhum. Só `separacao.py` (fim da separação) e as rotas de ocorrência publicam. | spec C |
| `order.created` e `order.occurrence_resolved` não geram nada | São publicados, mas nenhuma fila está ligada a essas routing keys. | spec C |
| O pedido não avança sozinho | A task Celery de avanço automático do monolito não foi portada de propósito (`pedidos.py:155-158`). Todo avanço é dirigido por um perfil de staff. | spec C |
| `web-admin/` não sobe contra este backend | O painel Angular aponta para `localhost:8080/api/v1`, a API Java que a spec A eliminou. Não está no compose. | spec B |
| Não existe cadastro nem tela de transportadora | `carrier_name` é uma coluna de texto marcada como mock (`pedido.py:75`). Estoque e ocorrência, ao contrário, existem e funcionam. | spec B |
| Meta, prazo e pontuação da home e do perfil são fixos | Valores escritos na tela, sem backend por trás. | spec D |
| O código PIX é gerado no cliente | `checkout_screen.dart` monta a string localmente. | spec B |

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

## Critério de aprovação

O smoke test passa quando as etapas 0 a 6 completam sem nenhuma falha que não
esteja na tabela de lacunas conhecidas. A etapa 7 é opcional no dia a dia e
obrigatória depois de qualquer mexida no `edu-common`.
