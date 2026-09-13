# Fluxo de pedido ponta a ponta — o que é real e o que é simulado

> **Escopo:** entrega da spec C (2026-09-09) — fazer um pedido percorrer
> `CRIADO` até `ENTREGUE` pelas telas dos quatro perfis (aluno, admin,
> separador, entregador), sem tocar no banco, com push no perfil certo a
> cada transição, posição do entregador andando no mapa do comprador, e o
> desvio de falta de estoque funcionando nos dois desfechos. O plano completo
> está em
> `docs/superpowers/plans/2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta.md`,
> e a execução em
> [`2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta-execution-record.md`](../superpowers/plans/2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta-execution-record.md).

Este documento descreve o sistema vivo. Onde alguma coisa é simulada — e uma
delas é, por completo — isso está escrito em texto explícito, não deixado
para inferência.

---

## 1. A máquina de estados

O pedido tem **dez** estados internos (`app/services/status_pedido.py::StatusPedido`
no `commerce-service`), que a operação de staff vê, e **seis** estados
públicos (`StatusContrato`), que é o que `GET /orders` devolve e o Flutter
lê. A tradução entre os dois vive em `STATUS_CONTRATO`, e é exaustiva por
construção — um teste (`test_the_mapping_covers_every_internal_state`)
percorre o enum inteiro, então um estado novo sem entrada nessa tabela quebra
a suíte em vez de virar `"pending"` por acidente.

```
CRIADO ──► CONFIRMADO ──► AGUARDANDO_SEPARACAO ──► EM_SEPARACAO ──┬─► SEPARADO ──► AGUARDANDO_COLETA ──► EM_TRANSITO ──► ENTREGUE
                                                                    │
                                                                    └─► AGUARDANDO_SUBSTITUICAO ──┬─► EM_SEPARACAO   (aluno aceita substituto ou remove o item)
                                                                                                    └─► CANCELADO      (aluno cancela o pedido)

(quase todo estado) ──► CANCELADO
```

`CONFIRMADO` é atravessado numa única chamada: `admin.py::confirmar_pagamento`
encadeia `CRIADO → CONFIRMADO → AGUARDANDO_SEPARACAO` porque não existe
simulador que faça essa transição sozinha, e parar em `CONFIRMADO` deixaria a
fila de separação vazia para sempre. É por isso que `CONFIRMADO` não tem
destinatário de push (seção 5) — avisar ali duplicaria a notificação de um
único clique do admin.

### O desvio de substituição

`AGUARDANDO_SUBSTITUICAO` é o estado que a spec C acrescenta. Ele existe
entre `EM_SEPARACAO` e o resto do fluxo, e só é alcançável de lá:

- `POST /occurrences/stock-shortage` (separador reporta falta de estoque)
  transiciona `EM_SEPARACAO → AGUARDANDO_SUBSTITUICAO`, guardado por
  `if pedido.status == EM_SEPARACAO` — um admin que abrir a mesma ocorrência
  sobre um pedido em qualquer outro estado nunca dispara uma transição
  inválida. Se a transição em si falhar por corrida (o pedido mudou de
  estado entre a leitura e a chamada), a ocorrência **continua gravada**: o
  guard só faz `logger.warning` e devolve 201 — a ocorrência é o registro do
  fato, e o fato já aconteceu.
- `POST /occurrences/{id}/resolve` — a mesma rota que já existia desde a
  fase 2 (não há `POST /orders/{id}/substitution` nova; a spec pedia a rota e,
  na frase seguinte, mandava resolver por aqui, que já fazia as três decisões
  — ver decisão D3 no plano) — devolve o pedido ao fluxo:
  - `substituir`/`remover_item` → `AGUARDANDO_SUBSTITUICAO → EM_SEPARACAO`.
    **Não** vai para `SEPARADO`: o separador ainda precisa pegar o item
    substituto da prateleira, e `finalizar_separacao` exige `EM_SEPARACAO`
    (ela mesma encadeia `SEPARADO → AGUARDANDO_COLETA` numa única chamada).
    Ir direto a `SEPARADO` tornaria `PATCH /picking/{id}/finish` inalcançável
    e tiraria o separador do laço. Decisão D7 do plano.
  - `cancelar_pedido` → `AGUARDANDO_SUBSTITUICAO → CANCELADO` (transição já
    existia; esta task só a tornou alcançável a partir do novo estado).

  A volta a `EM_SEPARACAO` roda **depois** do `db.commit()` que já gravou a
  decisão, e por isso tem o **mesmo guard** que a abertura da ocorrência tem
  do outro lado: um 400 do funil (o pedido saiu de
  `AGUARDANDO_SUBSTITUICAO` na janela — um cancelamento do admin, por
  exemplo) vira `logger.warning`, não a resposta da rota. Sem ele o aluno
  veria um erro sobre uma decisão que já foi gravada, e a ocorrência ficaria
  `RESOLVIDA` com o pedido preso em `AGUARDANDO_SUBSTITUICAO` — sem nenhuma
  rota capaz de movê-lo, porque o próprio `resolve` recusa ocorrência que
  não esteja `ABERTA`.

**Como o separador reencontra o pedido.** `GET /picking/queue` devolve, antes
da fila por risco, os pedidos `EM_SEPARACAO` cujo `picker_id` é o próprio
chamador — o de outro separador não aparece, e `AGUARDANDO_SUBSTITUICAO` fica
de fora porque espera o aluno. `limit`/`offset` cortam a lista já
concatenada. Sem isso, quem saía da tela de separação (trocar de perfil num
aparelho só limpa a pilha de navegação) nunca mais alcançava o pedido devolvido
pela decisão. A fila não traz itens; `GET /picking/{id}` traz, lidos do banco
na hora, e é o que o app lê ao abrir o pedido — depois de uma substituição o
item pode ter sido trocado ou removido. Mesma visibilidade da fila:
`AGUARDANDO_SEPARACAO` a qualquer separador, o resto só ao `picker_id`, admin
vê tudo. O app retoma um pedido `EM_SEPARACAO` sem chamar `/start` de novo.

**No contrato público, `AGUARDANDO_SUBSTITUICAO` resolve para `SEPARATING`** —
o mesmo valor que `EM_SEPARACAO` e `SEPARADO`. O aluno vê o pedido "em
separação"; a tela de resolução de ocorrência (já existente,
`incident_resolution_screen.dart`) é o que distingue os dois desfechos para
ele, não um passo novo no stepper.

`avancar_parados` (seção 4) exclui `AGUARDANDO_SUBSTITUICAO` de propósito: é
o único estado que espera uma decisão do aluno, e a rede de segurança nunca
pode atropelar essa decisão.

---

## 2. Carregamento e credencial

O **carregamento** (`app/models/carregamento.py::Carregamento`) é o lote de
pedidos que sai junto, de **uma** origem, por **uma** transportadora — e é
também a credencial do entregador. Rota exposta: `/shipments` (inglês, como
todo prefixo do gateway); agregado e tabela ficam em português, como
`fornecedores`/`estoque`/`ocorrencias`, porque quem tem cliente externo é a
rota, não o nome interno.

### Como o admin cria

`POST /shipments` (`requer_papel("admin")`), escolhendo uma transportadora
(`transportadora_id`). O serviço (`app/services/carregamentos.py::criar_carregamento`):

1. Sorteia um `codigo` de 8 caracteres e uma `senha` de 12, do mesmo alfabeto
   de 32 símbolos (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789` — sem `I`, `O`, `0`,
   `1`: o código é ditado por telefone e digitado por quem está com a carga
   na mão, e ambiguidade visual vira tentativa de login perdida). Com
   32⁸ (~1,1 × 10¹²) combinações, a colisão é tratada pelo índice único de
   `codigo`, não por um `SELECT` prévio — três tentativas de re-sorteio é
   folga absurda para o caso patológico.
2. Grava `senha_hash` (bcrypt, `edu_common.security.hash_password`) — a senha
   em claro nunca chega ao banco.
3. Publica `shipment.created` com a senha em claro **uma única vez**, no
   payload do evento. A resposta HTTP também devolve a senha em claro (é a
   única vez que qualquer rota o faz — `CarregamentoOut`, usado pela listagem
   e pelo detalhe, não tem o campo `senha` nem `senha_hash`; só
   `CarregamentoCriadoOut`, devolvido por este POST, o inclui).

O admin então atribui pedidos ao lote com `POST /shipments/{id}/orders`
(`app/services/carregamentos.py::atribuir_pedido`). O **primeiro** pedido
atribuído congela a origem do lote (`origem_rotulo`/`origem_lat`/`origem_lng`,
copiados de `orders.origem_*`, que a spec B já grava no checkout — inclusive
quando são nulos); um segundo pedido de origem diferente é recusado com
**409** (D10). `with_for_update()` no carregamento e no pedido torna essa
regra segura sob atribuição concorrente.

### Como a transportadora recebe

O `notification-service` consome `shipment.created`
(`app/events/consumer.py::handle_shipment_created`) e manda um e-mail para
`transportadora_email` com o código, a senha e uma frase de instrução —
usando o mesmo adapter (`app/services/email.py::enviar_email`, backends
`console`/`resend`, seção "D1" do plano) que qualquer outro envio deste
serviço usaria, se houvesse outro. **Nenhuma linha é gravada em
`notificacoes`** para este evento: a transportadora não é usuária do sistema,
e a senha não tem por que sobreviver no banco depois do envio. Nem o backend
`console` (log) nem o `resend` (na falha, nem no sucesso) jamais imprimem a
senha — os dois testes que vigiam isso (`test_the_console_backend_never_logs_the_body`,
`test_the_resend_backend_never_logs_the_provider_response_body`) usam um sink
de `loguru` de verdade, não `caplog` (que não captura `loguru`).

### Como o entregador entra

`POST /shipments/login` (rota **pública**, sem `Authorization`, como
`POST /auth/login`), com `codigo`, `senha`, `nome` e `contato`. O serviço
(`autenticar_carregamento`):

- Busca o lote pelo `codigo` exato, com `with_for_update()`.
- Compara `codigo` e verifica `senha` com `hmac.compare_digest`/bcrypt em
  tempo constante — inclusive no caminho de código **errado**: um bcrypt
  contra `DUMMY_PASSWORD_HASH` roda de qualquer forma, para que "código
  errado" e "senha errada" respondam com a mesma forma e o mesmo tempo
  (regra 9 do CLAUDE.md; é o mesmo motivo que já vale para `POST /auth/login`).
- No **primeiro** acesso (`aberto_em is None`), grava `entregador_nome`,
  `entregador_contato` e `aberto_em` — o registro de quem pegou a carga.
  Acessos seguintes não reescrevem esses campos.

O token devolvido tem `role="carregamento"` e `sub=str(carregamento.id)` —
**não** uma claim nova: `edu_common.security.create_access_token` não aceita
claims extras, então o `sub` *é* o id do lote (decisão D8). Validade fixa de
12 horas, sem refresh token (`CarregamentoLoginOut` não tem `refresh_token`)
— é uma jornada, não uma semana.

### O que o token autoriza

A dependency `app/dependencies.py::ator_de_entrega(*papeis_usuario)` classifica
quem chama uma rota de `/delivery` em dois tipos, através do dataclass
`AtorEntrega`:

- **Ator de lote** (`role == "carregamento"`): `AtorEntrega.autoriza(pedido)`
  compara `pedido.carregamento_id` com o `carregamento_id` do token. Aceito
  em qualquer uma das quatro rotas de `/delivery`, independente do conjunto
  de papéis pedido pela rota — o escopo dele é por pedido, não por papel.
- **Ator de usuário** (`role in ("entregador", "admin")`): mantém a regra que
  já existia — posse por `deliverer_id`, com claim-on-first-action na coleta.

`GET /delivery/queue` e `GET /delivery/mine` filtram por `carregamento_id`
quando o ator é de lote; `PATCH /delivery/{id}/collect` e `/deliver` recusam
com **403** ("Este pedido não pertence a este carregamento") um pedido de
outro lote. A ação de um ator de lote é registrada em
`PedidoStatusHistorico` com `user_id = NULL` — não porque algo falhou, mas
porque "quem fez" aqui não é uma pessoa com conta no sistema (a coluna é
`nullable=True` para exatamente este caso).

### O que ele **não** autoriza

- Nenhuma outra rota da frota: `requer_papel(...)` do `edu-common` rejeita
  `role="carregamento"` de saída, porque não é um papel de usuário — o token
  não abre `/admin`, `/picking`, `/occurrences`, nem nada fora de
  `/delivery/*` e o próprio `/shipments/login`.
- Nenhum pedido fora do lote — inclusive um pedido real, comprovado por
  teste (`test_the_shipment_token_sees_only_its_own_orders`), não só a forma
  do contrato.
- Identidade de pessoa: sem `user_id` de verdade, o histórico de status desse
  ator não pode ser atribuído a ninguém além do próprio lote.

**Dito sem rodeio: um token de carregamento autoriza as rotas de `/delivery`
para os pedidos do próprio lote, e nada mais.** Em particular, **reportar
atraso continua exigindo uma conta `entregador`** —
`POST /occurrences/delivery-delay` é `requer_papel("entregador", "admin")`, e
`requer_papel` recusa `role="carregamento"`. O app respeita isso do lado
certo: a tela "Entregas em Rota" **esconde** a ação "Reportar atraso" quando
a sessão ativa é de lote (`tracking_screen.dart`, `_sessaoDeLote`, lido do
claim `role` por `extrairRoleDoToken`), em vez de oferecer um botão cuja
única resposta possível é 403. Alargar o token para cobrir a rota seria dar
ao lote uma capacidade que ele não deve ter.

---

## 3. Posição — declarada como simulação

**Não há entregador real nem GPS neste sistema.** A posição que o mapa do
comprador mostra é **interpolada no backend**, por
`app/services/simulador_posicao.py`, e gravada pela **mesma função** que um
aparelho com GPS usaria: `app/services/posicao.py::registrar_posicao`. É essa
separação — uma porta de escrita única, e o simulador como só mais um
chamador dela — que faz a troca por GPS real ser **acrescentar um chamador e
desligar o job**, não reescrever a leitura, o model ou a tela. Nenhuma outra
função insere em `posicao_entrega`
(`grep -rn "PosicaoEntrega(" app/` devolve exatamente dois resultados: a
definição do model e o único `db.add(...)` dentro de `registrar_posicao`).

O relatório final de entrega desta spec lista esta simulação como simulação —
é este parágrafo.

### Como o simulador funciona

Um job periódico (`app/scheduler.py::tick_posicao`, a cada
`simulador_posicao_segundos`, default **10s** — o mesmo intervalo que o
Flutter usa para consultar `GET /orders/{id}/tracking`) chama
`avancar_carregamentos`:

- Para cada **carregamento** (não cada pedido — o lote anda junto) com algum
  pedido em `EM_TRANSITO` e coordenada de destino congelada, calcula a fração
  do percurso decorrida desde que aquele pedido entrou em `EM_TRANSITO`
  (`fracao_percorrida`, sobre um relógio de animação de
  `DURACAO_PERCURSO = 6 minutos` — curto de propósito, porque a apresentação
  inteira dura minutos, e **não** é a ETA real que `previsao_entrega`/Directions
  calcula).
- Interpola linearmente entre a origem do lote (`Carregamento.origem_lat/lng`)
  e o destino do pedido (`Order.destino_lat/lng`), quantizando o resultado nas
  seis casas decimais que a coluna `Numeric(9, 6)` guarda — gravar mais casas
  faria o valor lido de volta divergir do valor calculado.
- Grava a posição via `registrar_posicao`. Um lote com **vários** pedidos usa
  o destino do **primeiro** que tiver coordenada congelada — roteirização com
  várias paradas está fora do escopo (seção 6); com uma parada por lote, esse
  é o destino.

A coordenada de destino é congelada **uma vez**, na coleta
(`PATCH /delivery/{id}/collect` → `app/services/posicao.py::congelar_destino`),
resolvendo o endereço de entrega pela mesma fronteira que `GET /orders/{id}/route`
já usa (`app/services/directions.py`, via `_destination_query`, importada de
`rastreio.py` em vez de duplicada). Essa chamada **nunca levanta**: sem chave
de API, sem endereço, ou com o provedor fora do ar, o pedido segue sem
coordenada — o simulador o ignora, e `GET /orders/{id}/tracking` devolve
`courier_position: null`, o mesmo caminho de degradação que a spec já previa
para "consulta de posição sem posição registrada".

### O que o rastreio devolve

`GET /orders/{id}/tracking` carrega a **última** posição registrada
(`app/services/posicao.py::ultima_posicao`, ordenada por
`registrado_em DESC, id DESC`) e a embute em `courier_position` — sempre
presente na resposta (como `map_url`), `null` quando nada foi gravado ainda.
`app/services/rastreio_builder.py::build_order_tracking` continua puro: a
posição é dado que o router carrega e entrega a ele, não algo que o builder
busca. O nome da transportadora também deixou de ser a constante fixa
`"Logistics Intel Express"`: o builder devolve `order.carrier_name or
_CARRIER`, e a atribuição ao carregamento grava o nome real (decisão D12).

O Flutter consulta essa rota a cada 10 segundos
(`front-end-flutter/lib/features/order_tracking/presentation/route_provider.dart`),
desenha um terceiro marcador (`courier`) só quando `courier_position` não é
nulo, e para de consultar quando o pedido chega a `delivered`/`cancelled` —
o mesmo critério de parada que a tela já usava para o status.

---

## 4. Avanço automático

Rede de segurança da apresentação, não um simulador de pipeline
(`app/services/avanco_automatico.py::avancar_parados`). **Desligado por
padrão**: `AVANCO_AUTOMATICO_SEGUNDOS` ausente equivale a `0`, e com `0` a
função devolve lista vazia sem tocar em nada — é o critério de pronto 6 da
spec C.

### Como ligar

```bash
AVANCO_AUTOMATICO_SEGUNDOS=600   # dez minutos — não três
SIMULADOR_POSICAO_SEGUNDOS=10
```

Só quando `avanco_automatico_segundos > 0` o job correspondente
(`tick_avanco_automatico`, a cada 60s) é sequer **registrado** no
`AsyncIOScheduler` — não é um job que roda e não faz nada; ele simplesmente
não existe no processo, o que também deixa o log distinguir "ligado e nada a
fazer" de "desligado".

### Por que o prazo é longo

A apresentação é conduzida por **uma pessoa alternando entre quatro perfis**
no mesmo aparelho — trocar de sessão já leva mais que um prazo curto. Um
`AVANCO_AUTOMATICO_SEGUNDOS` de poucos segundos faria o pedido correr na
frente de quem está apresentando, avançando um estado que ninguém decidiu
mostrar ainda. Dez minutos (o valor sugerido no `.env.example`) dá folga real
sem deixar de existir como rede de segurança para quem travar numa tela.

### Por que ação manual sempre vence

`avancar_parados` compara `Order.status_updated_at` contra o prazo — e
`status_updated_at` é recarimbado **toda vez** que `transicionar_pedido`
(a mesma função que toda rota manual chama) grava uma transição, automática
ou não. Uma ação manual sobre um pedido reinicia a contagem sem precisar
cancelar timer nenhum
(`test_a_manual_action_restarts_the_clock` prova exatamente isso: chama
`transicionar_pedido` manualmente antes de rodar `avancar_parados` e espera
lista vazia).

Duas exclusões deliberadas de `PROXIMO_ESTADO`, a tabela de "para onde este
estado avança sozinho":

- **`AGUARDANDO_SUBSTITUICAO`** — é o único estado que espera uma decisão do
  aluno, e essa decisão é exatamente o que a apresentação está mostrando. A
  rede de segurança nunca pode atropelá-la (há um teste dedicado só para
  isso).
- **`SEPARADO`** — `finalizar_separacao` já encadeia
  `SEPARADO → AGUARDANDO_COLETA` numa única chamada, então um pedido nunca
  repousa nele em operação normal; não há nada para a rede de segurança
  avançar.

O avanço automático escreve **pela mesma função de transição** que as rotas
usam (`transicionar_pedido`), nunca por `UPDATE` direto — validação de
transição, carimbo de `status_updated_at`, linha de histórico e evento
`order.status_changed` acontecem de um jeito só, não de dois.

### O que a rede de segurança faz de diferente na coleta

`AGUARDANDO_COLETA → EM_TRANSITO` é o único salto que a rota equivalente
(`PATCH /delivery/{id}/collect`) acompanha de **dois** efeitos extras. O
avanço automático reproduz um e deliberadamente não reproduz o outro:

- **Congela o destino.** `congelar_destino` é chamado depois do salto, como
  na coleta manual — sem isso o pedido entraria em `EM_TRANSITO` sem
  coordenada de destino, o simulador (seção 3) o filtraria fora e o mapa do
  comprador nunca andaria para ele. A função nunca levanta, por desenho, e
  aqui vale a mesma garantia que vale na rota.
- **NÃO grava `deliverer_id`.** Não há pessoa coletando: inventar um dono
  seria gravar mentira no histórico. A consequência é concreta e vale
  conhecer antes de ligar o interruptor: **um pedido coletado pela rede de
  segurança não tem `deliverer_id`, e por isso uma conta `entregador` não
  consegue mais confirmar a entrega dele** — `PATCH /delivery/{id}/deliver`
  responde **403** ("Apenas o entregador responsável por este pedido pode
  confirmar a entrega"), porque a posse que ela checa nunca foi
  atribuída. Quem continua conseguindo entregar é o **entregador de lote**
  (token de carregamento), cuja posse é o `carregamento_id` e não o
  `deliverer_id` — e a própria rede de segurança, que levará o pedido a
  `ENTREGUE` no prazo seguinte. É a descrição honesta de uma rede que é
  desligada por padrão: quando ela age no lugar do entregador, ela também
  assume o resto do trajeto daquele pedido.

---

## 5. Push por transição

"Push" aqui é a notificação **dentro do app** (`GET /notifications`), lida
pelo sino que as telas de staff ganharam nesta spec (D13) — não um push real
de aparelho; isso continua fora (seção 6).

Quem é avisado de quê é decidido pelo `notification-service`, não pelo
`commerce-service`: o commerce publica o **fato** (`order.status_changed`,
sempre, em toda transição — inclusive antes desta spec; o que faltava não
era publicação, era destinatário, ver a medição da decisão D5 do plano), e
`app/services/destinatarios.py::PAPEIS_POR_STATUS` decide a **audiência**,
exaustiva sobre os dez estados internos:

| Estado interno | Quem é avisado |
|---|---|
| `CRIADO` | ninguém (fica para `order.created`, abaixo) |
| `CONFIRMADO` | ninguém — transitório, atravessado na mesma chamada de `confirmar_pagamento` |
| `AGUARDANDO_SEPARACAO` | aluno, separador |
| `EM_SEPARACAO` | aluno |
| `AGUARDANDO_SUBSTITUICAO` | ninguém — `order.stock_issue` já avisa o aluno, e só ele traz o `occurrence_id` |
| `SEPARADO` | aluno |
| `AGUARDANDO_COLETA` | aluno, entregador |
| `EM_TRANSITO` | aluno |
| `ENTREGUE` | aluno, admin |
| `CANCELADO` | aluno, admin |

Mais três eventos, cada um com o próprio conjunto de papéis:

| Evento | Quem é avisado |
|---|---|
| `order.created` | admin, separador (nunca o aluno — ele já sabe, acabou de pedir) |
| `order.stock_issue` | aluno |
| `order.delivery_delayed` | aluno |
| `order.occurrence_resolved` | separador (é quem estava bloqueado esperando a decisão do aluno — `finalizar_separacao` recusa terminar com ocorrência aberta) |

Um estado ou evento sem entrada nesta tabela quebra a suíte
(`test_every_internal_status_has_a_recipient_rule`) — um push endereçado a
ninguém é, em produção, indistinguível de um push que nunca foi publicado, e
a tabela existe para que essa lacuna apareça no CI, não numa apresentação.

**Por que `AGUARDANDO_SUBSTITUICAO` não avisa ninguém** — o mesmo raciocínio
de `CONFIRMADO`, com um agravante. `reportar_falta_estoque` publica **dois**
eventos para um único fato: a transição e, logo em seguida,
`order.stock_issue`. A linha escrita pela transição nasce sem
`ocorrencia_id` (a transição não carrega esse dado) e, mesmo assim, dizia
"toque para escolher um substituto" — era a única das duas que **não** abre
a tela de resolução, porque a tela navega pelo `occurrence_id`. Quem avisa o
comprador da falta é `order.stock_issue`, que traz o id. Uma falta, uma
linha, e a linha que instrui o toque é a que pode ser tocada.

### Como "separador"/"admin" viram um id de destinatário

`Notificacao` só tinha `aluno_id`; para avisar "todo separador" o
`notification-service` precisa saber quem são. A escolha (D6, depois de
descartar HTTP para o auth-users e ids soltos no payload) foi um **registro
local alimentado por evento**: o `auth-users-service` já publicava
`staff.created` (`app/routers/auth.py`) para toda conta staff nova; o
`notification-service` liga uma fila nova nessa chave e mantém
`app/models/staff.py::Staff` (id, papel, nome), escrito com
`INSERT ... ON CONFLICT DO NOTHING` — idempotente contra reentrega do
RabbitMQ. Sem chamada entre serviços, sem token de admin fabricado.

Uma conta escapava disso: `admin@demo.edu` nasce por `INSERT` direto no seed
de demonstração (`auth-users-service/app/seeds/demo_accounts.py`), então
nunca publicava `staff.created`. Esta spec faz o bootstrap publicar o evento
como as outras três contas já fazem — sem isso, o admin de demonstração não
apareceria no registro e nunca receberia push nenhum.

`app/services/destinatarios.py::resolver` sempre inclui o aluno quando
`"aluno"` está entre os papéis pedidos, **antes** de consultar `Staff` — um
registro de staff vazio (ou um evento que ainda não chegou) nunca derruba a
notificação do comprador.

---

## 6. O que continua fora

Nada disto é dívida escondida — é escopo explicitamente fora desta spec, e
nenhuma task o introduziu pela porta dos fundos:

- **GPS real.** A seção 3 descreve exatamente o ponto de extensão: um
  aparelho chamando `registrar_posicao` no lugar do simulador, com o job de
  simulação desligado. Nenhum código de recepção de GPS existe hoje.
- **WebSocket.** O mapa e o rastreio funcionam por **polling** (10s no app),
  não por push de servidor. Trocar por WebSocket mudaria o transporte, não o
  modelo de dados — `courier_position` continua vindo do mesmo
  `ultima_posicao`.
- **Expiração/revogação sofisticada do código do carregamento.** O token de
  lote expira em 12h fixas (`_EXPIRACAO_TOKEN_MINUTOS`), sem refresh e sem
  como revogar antes disso — não há denylist, não há "encerrar carregamento".
  Um código comprometido só para de funcionar quando o token expira.
- **Roteirização com várias paradas.** Um carregamento interpola para **um**
  destino (o primeiro pedido do lote com coordenada congelada), não uma rota
  que visita vários endereços em sequência.
- **Rotação/expurgo da senha do carregamento que já saiu da fila viva.** A
  senha em claro viaja num evento **persistente** sobre uma exchange
  **durável**, e o `EventConsumer` do `edu-common` mantém dead-letter
  sempre ligada. Consequência que vale saber antes de precisar dela: se o
  envio do e-mail falhar, `handle_shipment_created` levanta, o
  `async with message.process()` rejeita com `requeue=False` e a mensagem
  **para na `edu.events.dead`** — ela não desaparece junto com a tentativa
  de envio. Isso é o comportamento desejado (uma credencial perdida em
  silêncio seria pior), mas significa que **drenar essa fila é manusear
  credencial em claro**: quem for ler a `edu.events.dead` está lendo a senha
  de um carregamento, e o certo é criar um carregamento novo em vez de
  reencaminhar aquela mensagem. Não há expurgo automático, nem rotação — nem
  aqui nem no token de 12h descrito acima.
- **Cálculo de rota por serviço externo além do que já existe.**
  `GET /orders/{id}/route` e `app/services/previsao_entrega.py` são
  reaproveitados como estavam; a única coisa nova que os toca é a leitura da
  coordenada de destino na coleta (`congelar_destino`), que usa a mesma
  fronteira (`app/services/directions.py`) que já existia.
