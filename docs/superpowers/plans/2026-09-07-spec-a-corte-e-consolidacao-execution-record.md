# Spec A — O corte e a consolidação — Registro de execução

**Data:** 2026-09-07 e 2026-09-08
**Plano:** [`2026-09-07-spec-a-corte-e-consolidacao.md`](2026-09-07-spec-a-corte-e-consolidacao.md)
**Spec:** [`../specs/2026-09-07-spec-a-corte-e-consolidacao-design.md`](../specs/2026-09-07-spec-a-corte-e-consolidacao-design.md)
**Branch:** `feat/spec-a-corte`, 28 commits de implementação sobre `1c463ee`

Este documento registra o que aconteceu quando o plano foi executado: onde ele
estava errado, o que foi decidido no lugar, e o que ficou por fazer. O plano
descreve a intenção; este arquivo descreve a execução.

Cada task foi implementada por um agente com contexto limpo, a partir de um
briefing extraído do plano, e revisada por um segundo agente contra o diff.
Duas tasks precisaram de uma rodada de correção. A revisão final do branch
inteiro encontrou cinco problemas nas costuras entre tasks, corrigidos numa
onda única.

## O que foi entregue

| Task | Entrega | Commits |
|---|---|---|
| 1 | Lock consultivo de transação no seed do catálogo | `54b0a44` |
| 2 | Dead-letter exchange no `EventConsumer` do `edu-common` | `8a0b816` |
| 3 | Identificador curto de pedido nos títulos de push | `0b1917b` |
| 4 | Seed das quatro contas de demonstração | `1eee80f`, `4a9d07f`, `dc500fb`, `90bfef0` |
| 5 | Monolito fora do compose e do Makefile | `c055582`, `7fcc3b6` |
| 6 | `back-end/legacy/` apagado, script do initdb realocado | `7559590`, `6d11022` |
| 7 | Documentação reconciliada | `e58da02`, `52d3944`, `8291c0e` |
| 8 | Painel Angular trazido por `git subtree` | `34427ba`, `88b259f` |
| 9 | README de arquivamento do repositório 2 | `6886e2d` (no clone do repo 2, não empurrado) |
| — | Onda de correção da revisão final | `3e13b6d`..`3055f0a` |

Testes de backend: 706 antes, **722** depois, rodados serviço a serviço.
A suíte do monolito (56 testes) deixou de existir junto com o diretório.

| Serviço | Antes | Depois |
|---|---|---|
| api-gateway | 36 | 36 |
| auth-users-service | 65 | 72 |
| learning-service | 78 | 78 |
| commerce-service | 366 | 367 |
| chatbot-service | 37 | 37 |
| notification-service | 31 | 36 |
| analytics-service | 34 | 34 |
| packages/edu-common | 59 | 62 |

Flutter: 161 testes verdes. `flutter analyze` devolve os mesmos seis avisos de
nível `info` que já devolvia no ponto de partida — nenhum achado novo.

## Decisões tomadas durante a execução

O plano foi escrito antes de a árvore ser medida em detalhe, e dezoito pontos
precisaram de decisão. Cada uma está registrada com o motivo e com o que
custaria se estivesse errada.

### 1. A task 2 emenda dois testes que já existiam

A declaração da DLX quebrava `test_events.py:114` e `:143` de três formas: o
`declare_queue` passa a ser chamado duas vezes, o `bind()` passa a receber
`arguments`, e a fixture `fake_aio_pika` devolve um único mock de fila, então
o `dead_queue.bind(dlx)` entra na lista de chamadas sem a kwarg `routing_key`
e as compreensões levantam `KeyError`. Emendar os dois testes é a mesma
mudança de comportamento, não escopo novo.

### 2. Os alvos `front-*` do Makefile passam a apontar para o gateway

`Makefile:42` derivava `API_PORT` de `API_PORT_EXTERNAL` (8001, a porta do
monolito) e alimentava `--dart-define=API_BASE_URL`. Depois do corte, `make
front` sobrescreveria o default correto do `api_config.dart` (8100) por uma
porta sem nada atrás. O plano mandava não tocar nesses alvos.

### 3. O branch sai de `docs/mvp-delivery-specs`, não de `main`

O plano mandava sair de `main`, mas a spec e o próprio plano só existem na
branch de documentação. Sair de `main` deixaria todo executor sem o documento
de origem.

### 4. As contagens de teste do plano são descartadas

O plano afirmava 539 testes no total; a base real era 706. Um número velho num
passo do plano transforma suíte verde em falso sinal de falha, e um
implementador que "conserta" até bater o número errado faz estrago. Passou a
valer a regra: nenhum teste que passava antes da task falha depois, medido
serviço a serviço.

### 5. O teste da task 3 é reescrito

O plano escrevia `titulo = f"Pedido #{_id_curto(...)}"` seguido de
`assert titulo == "Pedido #0198F3A1"` — o teste constrói a string e depois a
asserta, e passaria intacto com os três handlers ainda emitindo o UUID. Além
disso o punha em `test_notifications_routes.py`, que cobre rotas HTTP e nunca
toca no consumer. Foi para `test_consumer.py`, com uma asserção por handler
sobre o `titulo` da notificação realmente gravada.

### 6. O seed da task 4 passa pelas rotas reais

O plano criava as quatro contas com `session.add(User(...))`. A spec proíbe em
texto explícito ("nunca por `INSERT` direto — um seed que contorna a rota
deixa de testar a rota"), e o próprio preâmbulo da task 4 prometia o
contrário do que seu código fazia. Duas consequências medidas: `/auth/register`
publica `student.created` e `/auth/register-staff` publica `staff.created`,
eventos que o learning-service e o analytics-service consomem, e `RegisterIn`
exige `phone`, `birth_date` e `education_level`, que o insert direto deixaria
nulos. O admin continua nascendo por insert direto — é o bootstrap
documentado, já que a rota pública só cria `student` e a de staff exige um
admin autenticado.

### 7. O alvo de seed precisa de `docker compose exec -e`

`docker compose exec` não repassa o ambiente de quem chama. A receita do plano
passava na guarda `test -n` do host e morria dentro do container dizendo que a
variável não estava definida.

### 8. O script do initdb é realocado antes da exclusão

O serviço `postgres`, que sobrevive, montava
`./legacy/postgres/initdb.d/init_test_db.sh`. Apagar o diretório deixaria a
origem do mount ausente, e o Docker criaria um diretório vazio onde deveria
haver um arquivo — sem erro visível num volume existente, quebrando só num
volume novo. Foi para `back-end/postgres/initdb.d/00-init_test_db.sh`.

### 9. As referências em prosa a "legacy" ficam

O passo 1 da task 6 esperava zero ocorrências de `legacy` na árvore. São cerca
de duzentas, quase todas docstrings registrando proveniência do porte ("Porte
de `legacy/tests/modules/orders/test_routes.py`"). Apagar o diretório não
quebra nenhuma, e limpá-las destruiria a trilha de evidência em que os
documentos de paridade da fase 2 se apoiam. O que precisava dar zero era a
referência funcional — mount, build context, `env_file`, import.

### 10. O escopo de documentação da task 7 dobra

O plano listava quatro arquivos. Outros cinco davam instruções que quebravam:
`README.md`, `front-end-flutter/README.md` (a tabela inteira de URL por
plataforma na porta 8001), `docs/front-end/running_ios.md`,
`docs/back-end/admin-panel.md`, e trechos do `microservices.md` fora da §9.
`start-here.md` é a exceção deliberada: ganha tarja de documento histórico e
mantém o corpo.

### 11. Dois minors da revisão da task 7 entram na correção

A frase de relatividade de caminhos que a nova tarja do `start-here.md`
descartou (três referências `app/...` daquele documento colidem com arquivos
reais dos serviços vivos), e duas passagens do `microservices.md` que
descreviam o monolito apagado no presente. Um terceiro minor ficou como
escrito: a frase acrescentada ao `phase-2-debt.md` sobre o inventário
consolidado seguir órfão é verdadeira, e o documento de dívida é onde ela
pertence.

### 12. O único arquivo Dart sem par é ausência deliberada

`mobile-flutter/lib` tinha 25 arquivos `.dart`; 24 têm caminho idêntico no
`front-end-flutter`. O único sem par é `features/admin/domain/dashboard.dart`,
e seu próprio docstring resolve: espelha os DTOs da API Spring Boot e
substituiu o `analytics.dart` no fork. Aqui o backend é o analytics-service
Python, então `analytics.dart` é o arquivo certo e o `dashboard.dart` modela
um backend que esta spec elimina.

### 13. A task 9 commita no clone do repo 2 e para

Escrever o README de arquivamento numa branch nova de outro clone não é merge,
push nem publicação. O que é do usuário — empurrar, abrir o PR, avisar os
colegas, arquivar — continua sendo.

### 14. O README de arquivamento é corrigido duas vezes

O texto do plano afirmava que as regras Java de estoque, transportadora e
ocorrência "foram portadas" para o commerce-service. Não foram. A primeira
correção trocou por "ainda não foram portadas", o que erra na direção oposta:
transportadora realmente não existe (só o campo `carrier_name` marcado como
mock em `pedido.py:75`), mas estoque e ocorrência têm implementações próprias
e funcionando — `admin.py:138,155` e os cinco endpoints de `ocorrencias.py` —
vindas da fase 2, não portadas do Java. A versão final separa os três estados.

### 15. Dois critérios de pronto do plano estão escritos errado

`grep -c "legacy" back-end/docker-compose.yml` devia devolver 0 e devolve 7 —
todas prosa de comentário, todas no passado correto. A intenção real do
critério, nenhum bloco de serviço construindo de `./legacy`, está satisfeita.
E `test ! -e back-end/legacy` falha: o git não tem nenhum arquivo lá, mas
sobrou no disco um `postgres/` vazio do `git mv` mais `.pytest_cache/` e
`secrets/`, ambos root, de execuções em container de agosto.

### 16. A triagem dos minors adiados

Quinze achados menores ficaram registrados como dívida deliberada. Um achado
anterior foi **retirado**, não adiado: a revisão da task 2 apontou que a linha
de log da fila morta interpolava o objeto `AbstractQueue` cru, mas
`aio_pika.Queue.__str__` devolve o nome da fila, então a linha já imprime o que
deveria. O achado estava errado.

### 17. `password-reset.md` vira documento histórico

Não é menção solta a Celery: o documento descreve um OTP entregue por task
Celery através de adapter Resend/console, com `tasks.py` na árvore de arquivos,
diagrama de sequência do envio, variáveis `EMAIL_SEND_*` e testes no layout de
diretórios do legacy. Tudo isso morreu com o monolito. O que sobrou no
auth-users-service não tem provedor de e-mail nenhum, e o docstring da própria
rota diz isso. Um documento vivo, indexado pelo `CLAUDE.md`, prometia um e-mail
que não pode chegar.

### 18. O runbook do corte é reordenado

O runbook escrito pela onda de correção falhava no passo 4, um passo antes da
falha que ele existia para evitar. `DB_SERVICES` (`Makefile:86`) lista
`learning-service` em segundo lugar e o laço de `services-migrate` tem
`|| exit 1`; com os três consumidores em loop de restart depois do `stack-up`,
o `docker compose exec` cai num container reiniciando e aborta o alvo inteiro
antes de commerce, notification, analytics e chatbot serem migrados. Apagar as
filas e reiniciar os consumidores passaram para antes do `services-migrate`.

## O que ficou registrado como dívida

Quinze achados menores foram adiados de propósito. Os que valem uma linha:

- `demo_accounts.py` tem uma tupla `("separador", "entregador")` que duplica a
  informação já presente em `DEMO_ACCOUNTS`.
- O teste de idempotência do seed cobre execução completa seguida de completa,
  não a parcial (admin criado, staff não).
- A fila morta da DLX não tem TTL, teto de tamanho, consumidor nem alarme — é
  um ralo que ninguém esvazia. Registrado na §11 do `microservices.md`.
- `docs/superpowers/plans/*.md` anteriores carregam cerca de quarenta
  referências a `back-*` e à porta 8001. São artefatos datados de planejamento;
  reescrevê-los destruiria o registro do que foi planejado contra o que foi
  entregue.

Os quatro itens de dívida da fase 2 que a spec adiou continuam abertos e estão
marcados como tal na nota de triagem do `phase-2-debt.md`.

## O que o plano ensinou sobre planos

Três padrões apareceram mais de uma vez e valem para os planos das specs B, C
e D:

**Números medidos envelhecem.** Toda contagem de teste do plano estava errada,
porque foi copiada de um documento anterior em vez de medida na hora. O critério
que sobreviveu foi relativo, não absoluto.

**Um plano pode contradizer a si mesmo entre a prosa e o código.** A task 4
prometia num parágrafo o que seu bloco de código não fazia. A prosa estava
certa e o código errado — mas só a leitura das duas coisas juntas revelou isso.

**A revisão por task não vê as costuras.** Os cinco achados da revisão final
eram todos coisas que nenhuma task possuía: a task 1 corrigiu a corrida do seed
e a task 7 reescreveu o documento que a descrevia como aberta, sem que nenhuma
das duas revisões pudesse ver a contradição. A fronteira do cache de imagem —
que cada task provou seu trabalho com `pytest` no host, enquanto o artefato que
o usuário opera é uma imagem construída — não pertencia a task nenhuma.
