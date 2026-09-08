# Spec C — Fluxo de pedido ponta a ponta — Design

**Data:** 2026-09-07
**Status:** Aprovado para planejamento
**Módulos:** `back-end/commerce-service/`, `back-end/notification-service/`, `back-end/api-gateway/`, `front-end-flutter/`
**Depende de:** spec B (origem por parceiro, estoque, transportadora).

## Objetivo

Fazer um pedido percorrer os quatro perfis sem intervenção manual no banco:
estudante compra, separador separa, entregador entrega, admin acompanha — com
push em cada transição, posição do entregador visível no mapa, e o desvio de
falta de estoque funcionando de verdade.

A apresentação é conduzida por **uma pessoa alternando entre os quatro
perfis**. Isso é requisito, não detalhe: define a troca rápida de sessão e o
formato do avanço automático.

## Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Posição do entregador | Interpolada no backend. Não há entregador real nem GPS. |
| Fronteira do "sem mocks" | Nada inventado no cliente. O backend pode simular, desde que o dado exibido venha dele. |
| Avanço automático | Rede de segurança: prazo configurável, **desligado por padrão**, ação manual sempre vence. |
| Acesso do entregador | Credencial por pedido. Some a conta de entregador pré-cadastrada. |
| Troca de perfil | Várias sessões guardadas no app, troca sem redigitar senha. Recurso de demonstração, isolado. |
| Falta de estoque | Estado novo na máquina existente, ligado ao `substituicao_ia.py` que já existe. |

## Contexto do código existente

### A máquina de estados já está pronta

`commerce-service/app/services/status_pedido.py` traz nove estados internos,
seis públicos, a tabela `TRANSICOES_VALIDAS`, o mapa `STATUS_CONTRATO` (com um
teste que falha se um estado novo não for mapeado) e `FLUXO_CONTRATO`.
Histórico em `pedido_status_historico`.

```
CRIADO → CONFIRMADO → AGUARDANDO_SEPARACAO → EM_SEPARACAO → SEPARADO
       → AGUARDANDO_COLETA → EM_TRANSITO → ENTREGUE
```

`CANCELADO` é alcançável de quase todos.

### As rotas de staff já existem

- `/picking/queue`, `/picking/{id}/start`, `/picking/{id}/finish`
- `/delivery/queue`, `/delivery/mine`, `/delivery/{id}/collect`, `/delivery/{id}/deliver`
- `/orders/{id}/tracking`, `/orders/{id}/route`, `/orders/{id}/predict-eta`
- `/occurrences/stock-shortage`, `/occurrences/delivery-delay`, `/occurrences/{id}/resolve`

E as telas: `front-end-flutter/lib/features/logistics/` tem
`picking_queue_screen`, `picking_screen`, `delivery_queue_screen`,
`delivery_detail_screen` e `tracking_screen`.

### A fiação de push está incompleta

`notification-service/app/events/consumer.py:169` liga cinco chaves:
`revision.scheduled`, `diagnostic.completed`, `order.status_changed`,
`order.stock_issue`, `order.delivery_delayed`.

O commerce publica de seis lugares: `order.created` (`pedidos.py:105`),
`order.status_changed` (`separacao.py:111` e `ocorrencias.py:364`),
`order.stock_issue`, `order.delivery_delayed` e `order.occurrence_resolved`
(`ocorrencias.py`).

Três buracos medidos:

1. **`entrega.py` não publica nada.** As transições para `EM_TRANSITO` e
   `ENTREGUE` — as duas que mais importam para o comprador — passam em
   silêncio.
2. `order.created` é publicado e ninguém consome.
3. `order.occurrence_resolved` é publicado e ninguém consome.

### O que não existe

- Estado de espera por substituição.
- Vínculo entre pedido e entregador, e entre pedido e transportadora.
- Qualquer noção de posição ao longo do tempo.
- Avanço automático de etapa.
- Sessão múltipla no app.

## Arquitetura

```
commerce-service/app/
  models/
    pedido.py            # ganha entregador, transportadora, carregamento
    posicao_entrega.py   # NOVO — série temporal de posição
    carregamento.py      # NOVO — o lote que o entregador acessa
  services/
    status_pedido.py     # ganha AGUARDANDO_SUBSTITUICAO
    simulador_posicao.py # NOVO — interpolação, isolada atrás de interface
    avanco_automatico.py # NOVO — rede de segurança
  routers/
    entrega.py           # passa a publicar evento; ganha atribuição
    substituicao.py      # NOVO — decisão do comprador
    carregamento.py      # NOVO — CRUD do lote e login por código
front-end-flutter/lib/
  core/session/          # NOVO — múltiplas sessões
  features/logistics/    # tela de login do entregador por código
  features/marketplace/  # tela de decisão de substituição
```

### Estado de substituição

`AGUARDANDO_SUBSTITUICAO` entra entre `EM_SEPARACAO` e `SEPARADO`:

```
EM_SEPARACAO → SEPARADO
EM_SEPARACAO → AGUARDANDO_SUBSTITUICAO → SEPARADO
                                       → CANCELADO
```

No mapa público ele resolve para `SEPARATING`: o aluno já vê "em separação", e
a decisão pendente aparece como ação na tela, não como um sexto passo na
timeline. O teste exaustivo que já existe obriga o mapeamento — um estado sem
entrada quebra a suíte, que é o comportamento desejado.

O caminho reaproveita o que existe. `POST /occurrences/stock-shortage` já cria
a ocorrência e já publica `order.stock_issue`; o que muda é que ele também
transiciona o pedido para `AGUARDANDO_SUBSTITUICAO` e anexa as sugestões de
`substituicao_ia.py`. A decisão do comprador entra por
`POST /orders/{id}/substitution` com `aceitar` ou `cancelar_item`, e resolve a
ocorrência pelo `/occurrences/{id}/resolve` que já existe.

### Carregamento e credencial do entregador

Um **carregamento** é o lote de pedidos que sai junto, de uma origem, por uma
transportadora. É o que o entregador acessa.

```
Carregamento
  id, transportadora_id, origem (do parceiro), criado_em,
  codigo (curto, sorteado, único),
  senha_hash, entregador_nome, entregador_contato, aberto_em
```

O admin cria o carregamento e atribui pedidos a ele. O sistema gera um código
curto e uma senha, enviados por e-mail à transportadora pelo
`notification-service`, que já fala com o Resend.

O entregador entra com **nome, contato e o código do carregamento**, mais a
senha. Em troca recebe um token cujo escopo é aquele carregamento — não um
papel global. Nome e contato são gravados no carregamento no primeiro acesso:
é o registro de quem pegou a carga, que hoje não existe.

**O login mora no `commerce-service`, não no `auth-users-service`.** O
carregamento e o hash da senha são dados de comércio; validar o código no
serviço de identidade obrigaria uma chamada entre serviços em todo login, para
consultar uma tabela que o outro serviço não é dono. O token é emitido pelo
`edu_common.security`, com o mesmo segredo JWT que a frota inteira já
compartilha, então ele é aceito por qualquer serviço sem nada novo.

O gateway precisa de `shipments` em `SERVICE_MAP`, apontando para `commerce`.

O papel `entregador` continua no enum de `auth_users` porque a spec A seeda uma
conta de demonstração com ele, mas deixa de ser o caminho normal. Um token de
carregamento autoriza apenas as rotas de entrega daquele lote — o
`require_role` de `edu_common/deps.py` não serve aqui, e a verificação de
escopo é uma dependency nova, não uma exceção dentro da existente.

### Posição simulada

`posicao_entrega`: `carregamento_id`, `lat`, `lng`, `registrado_em`. Série
temporal, não campo único — o mapa desenha o caminho percorrido, e um campo
único não guarda caminho.

`simulador_posicao.py` interpola entre a origem do carregamento (que vem do
parceiro, spec B) e o endereço de entrega, avançando conforme o tempo desde
`EM_TRANSITO`. Escreve pela mesma função que uma posição vinda de um aparelho
escreveria:

```python
async def registrar_posicao(db, carregamento_id, lat, lng) -> None: ...
```

O simulador é **um** chamador dessa função. Trocar por GPS real é acrescentar
outro chamador e desligar este — não reescrever a leitura, o modelo, nem a
tela. O arquivo diz isso no topo, e o relatório final da entrega lista a
simulação como tal.

O comprador e o admin leem `GET /orders/{id}/tracking`, que já existe, agora
devolvendo também a última posição. Atualização por consulta periódica a cada
dez segundos enquanto o pedido está em trânsito. Sem WebSocket: a demonstração
tem um pedido em tela.

### Avanço automático como rede de segurança

`avanco_automatico.py` avança um pedido parado no mesmo estado há mais que um
prazo configurável.

Três decisões que vêm do formato da apresentação:

- **Desligado por padrão.** Liga por variável de ambiente
  (`AVANCO_AUTOMATICO_SEGUNDOS`, ausente significa desligado).
- **Prazo bem maior que três minutos.** Uma pessoa alternando entre quatro
  perfis leva mais que isso só para trocar de sessão. Três minutos faria o
  pedido correr na frente do apresentador — que é exatamente o acidente a
  evitar.
- **Ação manual sempre vence.** O avanço só dispara se `status_updated_at` não
  mudou; qualquer transição manual reinicia a contagem sem precisar cancelar
  nada.

Roda como tarefa periódica no mesmo padrão do `learning-service/app/scheduler.py`,
que já faz varredura por vencimento. Escreve pela mesma função de transição que
as rotas usam — nunca `UPDATE` direto — para que a validação de transição, o
histórico e o evento aconteçam de um jeito só.

### Múltiplas sessões no app

`lib/core/session/` guarda um mapa de sessões por papel sobre o
`TokenStore` existente, com uma sessão ativa. Um menu lista as sessões
guardadas e troca a ativa, reutilizando o roteamento por papel que
`login_screen.dart:91` já faz.

Fica atrás de `--dart-define=DEMO_MULTI_SESSAO=true`, no mesmo padrão do
`DEMO_ITENS_MOCK` que já existe em `logistics/data/demo_itens.dart`. Guardar
quatro sessões ativas num aparelho é conveniência de demonstração, não postura
de segurança para um app de estudante — e a compilação padrão não a inclui.

## Fluxo de dados

```
Estudante  POST /orders                        → order.created       → push admin/separador
Separador  PATCH /picking/{id}/start                                 → EM_SEPARACAO
           PATCH /picking/{id}/finish          → order.status_changed→ push entregador
     ou    POST /occurrences/stock-shortage    → order.stock_issue   → push comprador
Comprador  POST /orders/{id}/substitution                            → volta ao fluxo
Admin      POST /shipments  + atribui pedidos                        → e-mail à transportadora
Entregador POST /shipments/login (código+senha+nome+contato)         → token de escopo
           PATCH /delivery/{id}/collect        → order.status_changed→ push comprador
           (simulador grava posição a cada 10s enquanto EM_TRANSITO)
Comprador  GET /orders/{id}/tracking (a cada 10s)                    → mapa anda
Entregador PATCH /delivery/{id}/deliver        → order.status_changed→ push comprador/admin
```

O `notification-service` ganha bindings para `order.created` e
`order.occurrence_resolved`, hoje publicados sem ouvinte, e `entrega.py` passa
a publicar `order.status_changed` no `collect` e no `deliver`.

O destinatário do push depende da transição, não do evento: `order.created`
avisa staff, `deliver` avisa comprador e admin. A tabela destinatário por
transição vive no `notification-service`, junto do resto da decisão de
notificação.

## Tratamento de erros

- Transição inválida: `409`, com o estado atual na resposta. `validar_transicao`
  já existe e é o único caminho.
- Token de carregamento em pedido de outro carregamento: `403`. Testado por
  pedido real de outro lote, não por token forjado.
- Código de carregamento errado: resposta e tempo iguais aos de senha errada.
  Comparação com `hmac.compare_digest`, protegida contra `None`, conforme a
  regra 9 do `CLAUDE.md`.
- `substituicao_ia.py` indisponível: já degrada para busca por categoria. O
  fluxo de falta de estoque nunca fica bloqueado por falha do modelo.
- Consulta de posição sem posição registrada: `200` com posição nula. O mapa
  mostra origem e destino sem o marcador móvel, e não uma tela de erro.
- Push que falha: vai para a dead-letter exchange criada na spec A, e não some.

## Testes

- Máquina de estados: caminho feliz completo; desvio por substituição, nos dois
  desfechos; toda transição inválida recusada.
- Mapeamento exaustivo de `AGUARDANDO_SUBSTITUICAO` para o contrato público —
  o teste que já existe cobre isso por construção.
- Carregamento: código errado, senha errada e escopo de outro lote, todos
  negados; nome e contato gravados no primeiro acesso.
- Posição: interpolação monotônica entre origem e destino; `registrar_posicao`
  testada direto, sem passar pelo simulador, provando que a interface serve a
  GPS real.
- Avanço automático: desligado por padrão; não dispara quando houve ação
  manual; dispara depois do prazo; nunca produz transição inválida.
- Push: uma asserção por transição, afirmando chave e destinatário.
- Flutter: troca de sessão preserva as demais; tela de substituição nos dois
  desfechos; mapa com posição nula.

## Critério de pronto

1. Um pedido percorre `CRIADO` até `ENTREGUE` pela interface dos quatro
   perfis, sem tocar no banco.
2. O desvio de falta de estoque funciona nos dois desfechos.
3. Cada transição gera push no perfil certo, verificado no aparelho.
4. O mapa do comprador mostra a posição andando durante o trânsito.
5. O entregador entra sem conta pré-cadastrada, só com código, senha, nome e
   contato.
6. Com `AVANCO_AUTOMATICO_SEGUNDOS` ausente, nada avança sozinho.
7. `make services-test`, `make front-analyze` e `make front-test` verdes.

## Fora de escopo

- GPS real do aparelho. A interface está pronta para ele; o chamador não.
- WebSocket ou streaming. Consulta periódica atende um pedido em tela.
- Expiração e revogação sofisticadas do código de carregamento.
- Roteirização com múltiplas paradas por carregamento.
- Cálculo de rota por serviço externo: `previsao_entrega.py` e
  `/orders/{id}/route` já existem e são reaproveitados como estão.
