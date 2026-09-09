# Spec C — Fluxo de pedido ponta a ponta — Registro de execução

**Data:** 2026-09-09
**Plano:** [`2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta.md`](2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta.md)
**Spec:** [`../specs/2026-09-07-spec-c-fluxo-de-pedido-ponta-a-ponta-design.md`](../specs/2026-09-07-spec-c-fluxo-de-pedido-ponta-a-ponta-design.md)
**Registro anterior:** [`2026-09-08-spec-b-parceiros-estoque-transportadora-execution-record.md`](2026-09-08-spec-b-parceiros-estoque-transportadora-execution-record.md)
**Branch:** `feat/spec-c-fluxo-de-pedido-ponta-a-ponta`, 23 commits de
implementação sobre `a50aa7d` (o commit do plano), mais o commit desta task

Este documento registra o que aconteceu quando o plano foi executado: onde
ele estava errado, o que foi decidido no lugar, e o que ficou por fazer. O
plano descreve a intenção; este arquivo descreve a execução. Segue o formato
do registro da spec B — ver o documento anterior para o vocabulário
("ruling", "achado adiado", "dívida registrada").

Cada task foi implementada por um agente com contexto limpo, a partir de um
briefing extraído do plano, e revisada por um segundo agente contra o diff.
**Nove das quatorze tasks de código passaram por rodada de correção.** Em
sete delas (1, 3, 4, 5, 6, 12, 13) o achado era um Important de verdade
sobre o código, e como na spec B a maioria não era erro do implementador:
era defeito do **plano**, encontrado por reprodução contra o banco de teste,
não por leitura. Nas outras duas (2 e 9) o único achado era o trailer do
commit (`Claude Haiku 4.5`/`Claude Sonnet 5` em vez de `Claude Opus 5`), e o
controlador pulou o re-review dispatchado nas duas — `git diff --stat` entre
o commit original e o amendado não imprime nada. As tasks 7, 8, 10, 11 e 14
fecharam sem nenhum achado Important — a 7 e a 9 porque o dispatch já
citava, nomeados, os defeitos de classe que tinham mordido tasks anteriores
(o mesmo padrão que a spec B registrou para suas próprias tasks 4, 6, 7 e
9).

Esta spec não teve, ao contrário da B, uma "revisão de branch inteira" —
esse passo é dispatchado pelo controlador depois deste relatório, não faz
parte da task 15. O que este documento cobre é o que as quinze tasks, cada
uma revisada isoladamente, produziram.

---

## O que foi entregue

| Task | Entrega | Commits |
|---|---|---|
| 1 | Schema da spec C: `Carregamento`, `PosicaoEntrega`, `orders.carregamento_id`/`destino_lat`/`destino_lng`. Revision `c1d2e3f4a5b6` | `7f68929`, `2a893cf` |
| 2 | `AGUARDANDO_SUBSTITUICAO` na máquina de dez estados, resolvendo para `SEPARATING` no contrato público | `753b439` |
| 3 | Falta de estoque transiciona para o desvio; a resolução da ocorrência devolve ao fluxo | `9943a8b`, `7e97630` |
| 4 | Carregamento — serviço, rotas admin (`/shipments`), roteamento no gateway | `4fdfbca`, `2edbb6a`, `4a1bb81` |
| 5 | Login do entregador por código (`/shipments/login`), escopo de token que não é papel de usuário | `031297d`, `f4687fe` |
| 6 | Posição: porta de escrita única, simulador, rastreio com `courier_position` e transportadora real | `290d25c`, `2cdb3c0` |
| 7 | Scheduler (`AsyncIOScheduler`): simulador de posição e avanço automático desligado por padrão | `a3e9a99` |
| 8 | Push endereçado por transição: registro de staff, tabela de destinatário, três bindings novos | `1eebabb`, `9068b10` |
| 9 | E-mail da credencial à transportadora — primeiro envio real desde a spec A | `392983f` |
| 10 | Flutter: múltiplas sessões guardadas atrás de `DEMO_MULTI_SESSAO` | `b7af1db` |
| 11 | Flutter: login do entregador por código, sino de notificação nas telas de staff | `06c374b` |
| 12 | Flutter: posição do entregador andando no mapa do comprador | `7453a14`, `588448e` |
| 13 | Flutter: aba "Carregamentos" do admin | `ca4759d`, `1485f6c` |
| 14 | `web-admin`: página de carregamentos | `453903a` |
| 15 | Documentação, costura e verificação final | este documento |

---

## Medição final

Medida do zero em 2026-09-09, serviço a serviço, na árvore no commit
`453903a` (HEAD ao iniciar a task 15) mais as mudanças desta própria task
(só documentação — nenhum arquivo de código foi tocado).

### 1. Backend inteiro

```
for s in packages/edu-common api-gateway auth-users-service learning-service \
         commerce-service chatbot-service notification-service analytics-service; do
  echo "→ $s"; (cd back-end/$s && uv run pytest -q | tail -1) || exit 1
done
```

```
→ packages/edu-common
62 passed in 2.43s
→ api-gateway
39 passed in 0.09s
→ auth-users-service
73 passed in 16.74s
→ learning-service
78 passed in 1.17s
→ commerce-service
592 passed, 1 warning in 22.60s
→ chatbot-service
37 passed in 0.26s
→ notification-service
53 passed in 0.63s
→ analytics-service
34 passed in 0.62s
```

### 2. Lint de tudo que a spec tocou

```
for s in commerce-service notification-service api-gateway auth-users-service; do
  (cd back-end/$s && uv run ruff check . && uv run ruff format --check .) || exit 1
done
```

```
=== commerce-service ===
All checks passed!
146 files already formatted
=== notification-service ===
All checks passed!
30 files already formatted
=== api-gateway ===
All checks passed!
9 files already formatted
=== auth-users-service ===
All checks passed!
39 files already formatted
```

### 3. Flutter

```
cd front-end-flutter && flutter test
```
```
00:19 +201: All tests passed!
```

```
cd front-end-flutter && flutter analyze lib/
```
```
   info • Unnecessary use of multiple underscores • lib/features/admin/presentation/widgets/admin_scaffold.dart:42:26 • unnecessary_underscores
   info • Unnecessary use of multiple underscores • lib/features/admin/presentation/widgets/admin_scaffold.dart:42:30 • unnecessary_underscores
   info • Use the null-aware marker '?' rather than a null check via an 'if' • lib/features/admin/presentation/widgets/admin_widgets.dart:166:15 • use_null_aware_elements
   info • Use the null-aware marker '?' rather than a null check via an 'if' • lib/features/logistics/data/logistics_api.dart:288:9 • use_null_aware_elements
   info • 'groupValue' is deprecated ... incident_resolution_screen.dart:275:19 • deprecated_member_use
   info • 'onChanged' is deprecated ... incident_resolution_screen.dart:276:19 • deprecated_member_use

6 issues found. (ran in 1.1s)
```

Mesmos seis avisos, nos mesmos arquivos e nas mesmas regras que a baseline
medida antes da task 1 — a CONTAGEM não mudou, que é o critério do plano.

O que a frase original desta seção dizia a mais ("nenhum arquivo tocado por
esta spec está entre eles") era **falso**, e a revisão final o pegou: dois
dos seis avisos estão em `admin_scaffold.dart:42`, uma linha que a task 13
reescreveu (o `pageBuilder` deixou de ser um ternário e virou um `switch`
sobre `AdminTab` para acomodar a aba de carregamentos) — os dois
`unnecessary_underscores` de `(_, __, ___)` vieram junto com a linha nova.
Um terceiro, em `logistics_api.dart`, está num arquivo que a task 11 editou,
ainda que não na linha editada. O correto é: a contagem ficou em seis, e
parte dos seis vive em arquivos que esta spec tocou.

### 4. `web-admin`

```
cd web-admin && npm run build
```

Exit code **0**. Três avisos de budget SCSS, os mesmos três pré-existentes
(`dashboard.component.scss`, `products-stock.component.scss`,
`carriers.component.scss`) — nenhum quarto para `shipments.component.scss`
(o relatório da task 14 registra o trabalho de consolidação de seletores
que manteve esse arquivo abaixo do teto de 4 kB).

### 5. `docker compose config`

```
docker compose -f back-end/docker-compose.yml config --quiet
```

Exit code **0**.

### Tabela comparativa

| Alvo | Baseline (antes da task 1) | Esperado pelo plano | Medido agora |
|---|---|---|---|
| commerce-service | 526 | 580 | **592** |
| notification-service | 36 | 51 | **53** |
| api-gateway | 37 | 39 | **39** |
| auth-users-service | 72 | 73 | **73** |
| analytics-service | 34 | 34 (intocado) | **34** |
| edu-common | 62 | 62 (intocado) | **62** |
| learning-service | 78 | intocado | **78** |
| chatbot-service | 37 | intocado | **37** |
| **Total Python** | 882¹ | — | **968** |
| Flutter (`flutter test`) | 179 | 197 | **201** |
| Flutter (`flutter analyze lib/`) | 6 `info` | 6 `info` | **6 `info`** |
| `web-admin` (`npm run build`) | exit 0, 3 avisos SCSS | — | **exit 0, 3 avisos SCSS** |

¹ O total Python "882" é o número que o `smoke-test.md` já citava, herdado
do fechamento da spec B (526+37+72+78+367→491→526 ...; ver o registro
anterior). Não é um número desta spec — está aqui só para a aritmética do
delta: 968 − 882 = 86 testes de backend a mais, batendo com a soma dos
deltas por serviço (66 no commerce, 17 no notification, 2 no gateway, 1 no
auth).

Nenhum alvo caiu abaixo do baseline. Toda divergência é para cima, e nenhuma
é "sobrou sem explicação" — mas a explicação não é um decomposição limpa em
poucos números: como em todo relatório desta execução (e como a spec B já
registrou como lição), **o número "esperado" do plano para cada task
individual já estava obsoleto antes de a task começar**, na maioria das
vezes porque a task anterior tinha adicionado mais testes do que o plano
previa e o plano não foi remedido entre uma task e a próxima. Os relatórios
das tasks 3, 5 e 7 documentam isso explicitamente: a task 5, por exemplo,
recebeu a baseline "550" do plano quando a árvore já estava em 555 (a task 4
tinha fechado 2 acima do previsto), e reportou 564 em vez do "559" que a
aritmética do brief sugeria — nenhum dos dois números do plano estava
certo, e o implementador mediu em vez de forçar o resultado a bater.

Cada incremento **real** (task sobre a task anterior, medido, não
comparado a um "esperado" que já tinha apodrecido) está documentado no
relatório da própria task:

- **commerce-service:** 526 → 530 (task 1) → 536 (task 2, +2 de
  parametrização sobre o enum) → 543 (task 3, +1 da rodada de fix — teste da
  corrida em `reportar_falta_estoque`) → 555 (task 4, +2 da rodada de fix —
  origem nula) → 567 (task 5, +3 da rodada de fix — papéis restritos de
  admin) → 583 (task 6, +1 da rodada de fix — `congelar_destino` nunca
  levanta) → **592** (task 7). Todo incremento tem teste novo associado, não
  reformulação de teste existente.
- **notification-service:** 36 → 46 (task 8) → **53** (task 9 — o brief
  previa 51/+5; o implementador entregou +7, dois deles testes de segurança
  que as global constraints exigiam e o brief não tinha escrito
  explicitamente: nunca logar o corpo do e-mail nem a resposta de erro do
  Resend).
- **Flutter:** 179 → 184 (task 10) → 188 (task 11) → 193 (task 12) → 195
  (task 12, rodada de fix — timer órfão e parsing intolerante, +2) → 199
  (task 13) → **201** (task 13, rodada de fix — `Key` por posição e sino do
  admin, +2).

---

## Decisões tomadas durante a execução

Rulings do controlador, extraídas de
`.superpowers/sdd/2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta/progress.md`
(arquivo de rascunho, apagado quando este plano fechar — é por isso que
sobrevivem aqui). Cada uma com o que decidiu e o custo se estivesse errada.

### Antes de despachar qualquer task

**Trabalhar no checkout primário, não em worktree.** Cada serviço lê um
`.env` git-ignored que só existe neste checkout; um worktree novo faria toda
suíte falhar no import por `ValidationError` do pydantic. Custo se errado: o
stack Docker vivo do usuário aponta para este diretório, então uma task que
quebrasse o código deixaria o stack quebrado até o próximo build — mitigado
por nunca rodar `docker compose` (proibição global).

### Ruling 1 (task 9, defeito do plano) — `caplog` não captura `loguru`

O teste `test_the_console_backend_never_logs_the_body`, como o plano o
escreveu, usava `caplog` do pytest — que não captura `loguru` (não propaga
para o `logging` da stdlib). **Decisão:** capturar com um sink próprio
(`logger.add(registros.append, level="INFO")`, `logger.remove(...)` no
fim). A asserção continua a mesma: destinatário aparece, senha não. **Custo
se errado:** nenhum sobre o código — o teste como escrito no plano passaria
vazio e não travaria nada, que era o próprio defeito.

### Ruling 2 (task 7) — `avancar_parados` não checa ocorrência aberta

`avancar_parados` avança `EM_SEPARACAO → SEPARADO` sem checar se há uma
ocorrência aberta pelo admin sobre o pedido (o caminho de falta de estoque
já estaciona em `AGUARDANDO_SUBSTITUICAO`, fora de `PROXIMO_ESTADO` — só
sobra a ocorrência aberta por admin). **Decisão:** não acrescentar a
checagem — o avanço é desligado por padrão, e a regra viva de
`finalizar_separacao` continua valendo para a rota manual. **Custo se
errado:** com a rede de segurança LIGADA, uma ocorrência aberta por admin
pode ser ultrapassada pelo avanço automático.

### Ruling 3 (task 6) — `_destination_query` fica em `rastreio.py`

`posicao.py` importa a função privada de `rastreio.py` em vez de duplicá-la
ou de mover a função. **Decisão:** tomada antes do dispatch, para o
implementador não escolher — mover obrigaria editar `rastreio.py` numa task
que não o lista. **Custo se errado:** `posicao.py` importa um nome privado
de outro módulo do mesmo pacote — legível, mas um acoplamento a mais.

### Task 1 — o `UUID` do dialeto precisa de import explícito

`sa.dialects.postgresql.UUID(...)` na revision funcionava só porque
`alembic/env.py` já tinha importado os models (efeito colateral de processo,
não contrato do arquivo). **Decisão:** importar explicitamente, como as
outras duas revisions do repo que usam o tipo. O plano escreveu a forma
frágil; a correção é contra o texto do plano, não contra o implementador.
**Custo se errado:** nenhum — o import explícito é estritamente mais
robusto.

### Task 2 — trailer de commit errado, corrigido sem re-review

O commit inicial (`9c123be`) trazia `Claude Haiku 4.5` em vez de
`Claude Opus 5` (convenção do projeto para todo commit desta branch,
independente de qual modelo escreveu o código). **Decisão:** amend
(`753b439`), e **pular o re-review dispatchado** — o achado era de metadado,
e `git diff --stat 9c123be 753b439` não imprime nada (árvores idênticas),
conferido pelo próprio controlador. **Custo se errado:** uma rodada de fix
sem segunda leitura — mitigado por o diff da task inteira entrar na revisão
final da branch. O mesmo padrão se repetiu na task 9 (`b5ea56d` → `392983f`,
trailer `Claude Sonnet 5` → `Claude Opus 5`).

### Task 3 — a ocorrência não pode depender da transição ter dado certo

`reportar_falta_estoque` lia `pedido.status` sem lock antes de chamar
`transicionar_pedido`; se o status real tivesse mudado na janela, a
transição levantava **400 depois** de a `Ocorrencia` já estar commitada — o
cliente via erro por uma requisição cujo efeito principal (o registro do
fato) tinha dado certo. **Decisão:** envolver só a chamada de transição num
`except HTTPException` 400, com `logger.warning`, mantendo 201 e a
ocorrência gravada. Rejeitado `with_for_update()` na leitura inicial: o lock
cairia no commit da própria rota, deixando a janela entre commit e transição
aberta do mesmo jeito, e ainda seguraria lock de linha durante a chamada de
embeddings. **Custo se errado:** uma transição de fato inválida vira log em
vez de 400 para o separador — aceitável, porque a ocorrência é registro de
fato e a ação seguinte do separador revalida o estado.

### Task 4 — o sentinel de "origem já congelada" tinha que ser existência, não rótulo não-vazio

`if not carregamento.origem_rotulo` falhava quando o **primeiro** pedido
atribuído tinha origem nula (checkout sem fornecedor resolvido) — o segundo
pedido, de origem real, entrava no mesmo ramo e sobrescrevia a origem sem
409. **Decisão:** sentinel vira "o lote já tem pedido atribuído" (`EXISTS`
sobre `orders.carregamento_id`), congelando inclusive origem nula.
Rejeitado recusar pedido sem origem: pedidos anteriores à spec B, e
carrinhos sem linha de fornecedor, ficariam para sempre sem carregamento.
**Custo se errado:** um lote de origem nula aceita só outros de origem nula
— o simulador o ignora e o rastreio devolve posição nula, caminho de
degradação já previsto.

### Task 5 — `ator_entrega` alargava demais quem podia mutar `/delivery`

A primeira versão aceitava `papel in ("entregador", "admin")` nas
**quatro** rotas; antes desta task só `GET /delivery/queue` aceitava admin
— `/mine`, `/collect` e `/deliver` eram só entregador. Um admin passaria a
poder reivindicar e marcar como entregue um pedido sem dono, direto. **A
falha era maior do que o implementador tinha reportado** (ele só tinha
notado o alargamento em `/mine`, de leitura). **Decisão:** transformar a
dependency em fábrica `ator_de_entrega(*papeis_usuario)`, no idioma do
`require_role`, devolvendo cada rota ao conjunto de papéis que tinha antes,
com o token de lote aceito por cima de qualquer conjunto. **Custo se
errado:** um admin deixa de operar entrega direto pela rota — e essa era
exatamente a postura anterior, ainda alcançável por
`/admin/orders/{id}/assign-deliverer`.

**Achado resolvido sem mudança de código:** `PedidoStatusHistorico.user_id`
é `nullable=True` de propósito — `transicionar_pedido(..., user_id=None)`
no ator de lote grava linha com `NULL`, que é a forma pretendida para "não
foi uma pessoa".

### Task 6 — `congelar_destino` não protegia a conversão nem o commit

O `try/except` cobria só a chamada ao provedor Google; as duas conversões
`Decimal` e o `commit()` ficavam fora. Um valor malformado (`status: OK`
mas coordenada não numérica) ou uma falha pontual de commit viraria 500
numa coleta cuja transição de status já tinha sido commitada com sucesso.
**Decisão:** estender o `try` para dentro da própria função — a garantia
"nunca levanta" é dela, não de quem a chama; proteger no call site deixaria
um segundo chamador futuro desprotegido. **Custo se errado:** um erro de
programação dentro do bloco vira log em vez de 500 — mitigado por o log
nomear o pedido, sem detalhe do provedor (regra 5 do CLAUDE.md).

**Achado resolvido sem mudança de código:** o docstring de
`simulador_posicao.py` aponta para `docs/back-end/order-flow.md`, que só
esta task 15 cria. Referência correta desde o início — verificado que o
arquivo existe agora.

### Task 7 — nota de ambiente para o resto da spec

**A task 7 foi a única autorizada a rodar `uv sync`, só em
`back-end/commerce-service`:** `apscheduler` entra nas dependências e
`app/main.py` passa a importar `app/scheduler.py` — sem instalar a
dependência, a suíte inteira quebra no import do `conftest`. `uv.lock` do
commerce mudou e foi para o commit. A mesma autorização, pelo mesmo motivo,
valeu para a task 9 e `notification-service`/`httpx` (sai do grupo dev,
vira dependência de produção — o adapter de e-mail o usa em runtime).
**Custo se errado, nos dois casos:** o lock de um único serviço é
reescrito — é o que a task pede, nenhum outro serviço é tocado.

**Nota de dispatch corrigida ao vivo:** a nota que acompanhou o dispatch da
task 7 afirmava que `_campos_obrigatorios` já existia em `tests/test_config.py`
— não existia (o plano tinha inventado essa premissa, e a nota de dispatch
repetiu o erro). O implementador criou o helper; a nota foi corrigida no
ledger para não repetir o engano nas próximas dispatches.

### Task 8 — sem findings Important; um achado de metadado adiado

Review limpa (0 Critical/Important). Quatro Minor deferidos — ver a tabela
de triagem abaixo.

### Task 9 — mesma correção de trailer que a task 2

Ver "Task 2" acima. `b5ea56d` → `392983f`, mesma decisão de pular o
re-review dispatchado, pelo mesmo motivo (diff de árvore vazio, conferido
pelo controlador).

### Task 10 — nenhum achado que exigisse mudança de código

Um ⚠️ do revisor resolvido pelo controlador sem gap: `AuthApi.currentDisplayName()`
já existia antes desta task e trata falha de rede; a borda estreita restante
(200 com corpo não-JSON) só é alcançável com a flag de demonstração ligada —
ficou como minor, não gap.

### Task 12 — dois achados Important reais, ambos em código pré-existente que a task tocou de leve

1. `RouteProvider.load()` não checava `_disposed` depois do `await` —
   fechar a tela durante o fetch inicial criava um `Timer.periodic` que
   ninguém cancelava, rodando para sempre com chamada de rede real.
2. `CourierPosition.fromJson` usava `as num?`, que tolera `null` mas
   estoura `TypeError` para um valor de outro tipo — contra a regra
   "malformado vira null, nunca exceção".

**Decisão:** guardas de `_disposed` em `load()` (sucesso e os dois `catch`),
e parse tolerante (`is num`/`is String` em vez de `as`), mais dois testes.
**Custo se errado:** nenhum — as duas mudanças só estreitam caminhos de
falha, sem alterar comportamento no caminho feliz.

**Achado resolvido sem mudança de código:** os critérios de parada do
polling (`isDelivered`/`isCancelled`) e o swallow-and-retry do `_poll` de
`order_provider.dart` são exatamente como o relatório da task afirmava — o
controlador leu o arquivo antes de aceitar a alegação.

### Task 13 — a reordenação da lista misturava o estado de dois carregamentos

`_CarregamentoCard` não tinha `Key`; com a listagem vindo do mais novo para
o mais velho, criar um carregamento empurrava os índices e o `State`
reaproveitado por **posição** (não por identidade) mantinha o `Future`
memoizado do lote anterior — um card podia mostrar os pedidos de outro
carregamento sob o cabeçalho errado. **Decisão:** `ValueKey(carregamento.id)`
mais `didUpdateWidget` como defesa em profundidade, e um teste de
reordenação. Uma correção companheira, não pedida explicitamente, foi
necessária para o teste sequer alcançar o bug: o `FutureBuilder` da tela
escondia a lista inteira atrás de um spinner a cada refresh
(`connectionState == waiting`, sem checar `hasData`), destruindo **todo**
card, não só o que mudou de posição — sem essa correção o achado da `Key`
era correto em princípio e inalcançável na prática.

**Segundo achado, sobre escopo, não sobre bug:** o revisor marcou o sino no
`AdminScaffold` como fora de escopo. **Não procedeu** — o controlador tinha
autorizado na dispatch, e a decisão D13 do plano exige exatamente isso (a
tabela de destinatário da task 8 manda push de admin em `order.created`,
`ENTREGUE` e `CANCELADO`). O que faltava era só o teste, que foi
acrescentado.

**Achado resolvido sem mudança de código:** `TransportadoraOut` serializa
`rating`/`sla_percentage` como string (`field_serializer`), então o
`as String` do cliente Flutter estava certo.

### Task 14 — sem findings Important

Um Minor: o relatório chamava `backendDetail` de "função testada" quando
não há nenhum `.spec.ts` no módulo (decisão D11, herdada da spec B — o
`web-admin` continua sem suíte). O código está certo; a frase exagerava.

---

## Achados adiados (Minor) — triagem

Nenhum bloqueou o fechamento de task nenhuma. Agrupados por área, com uma
recomendação de ação para quem revisitar.

### Schema e migrations (task 1)

| Achado | Ação sugerida |
|---|---|
| `alembic/env.py` não importa `carregamento`/`estoque_ajuste`/`transportadora` — dívida pré-existente às duas primeiras spec, não introduzida agora | Corrigir numa faxina de `env.py`; baixo risco, autogenerate futuro poderia propor drop espúrio |
| Docstring de `test_spec_c_schema.py` cita "passo 6" em vez de "Passo 8" (defeito transcrito do plano) | Cosmético — corrigir na próxima vez que o arquivo for tocado |
| Testes não afirmam `senha_hash` 255 nem `entregador_contato` 120 (lacuna do código de teste do plano; os models estão corretos) | Acrescentar as duas asserções junto de qualquer mudança futura no schema de carregamento |

### Máquina de estados e ocorrências (tasks 2, 3)

| Achado | Ação sugerida |
|---|---|
| Prosa "nove valores" obsoleta em `app/models/pedido.py:40` e `tests/test_tracking_builders.py:10` (agora dez) | Uma linha — corrigir junto de qualquer PR que toque esses arquivos |
| RED da task 3 trouxe 2 testes já verdes por motivo trivial (nenhum código tocava `pedido.status` ainda) | Nenhuma ação — comportamento correto de TDD, registrado só para não confundir quem reler o relatório |
| Falta o teste espelho do guard no lado do `resolve` (`substituir`/`remover_item` com pedido fora de `AGUARDANDO_SUBSTITUICAO`) | Escrever antes de qualquer mudança futura nessas duas transições — é exatamente o tipo de guard que uma "costura entre pares de tasks" (padrão do registro da spec B) poderia esconder |

### Carregamento e login (tasks 4, 5)

| Achado | Ação sugerida |
|---|---|
| `db.get(Carrier, ...)` refeito na rota de criação depois de o serviço já ter buscado a mesma linha | Otimização, não correção — baixa prioridade |
| Teste de idempotência de atribuição afirma só `(200, 200)`, não o estado persistido depois da segunda chamada | Fortalecer se `atribuir_pedido` for tocado de novo |
| `RuntimeError` inalcançável no fim do laço de retry de `criar_carregamento` | Código morto de baixo risco — considerar remover numa faxina |
| Nenhum teste afirma as strings de 403 do ator usuário em `/delivery` | Escrever se a mensagem de erro virar contrato para o cliente |
| Lock de linha do login sem commit explícito no caminho de acesso posterior (sem risco de deadlock — mesma ordem de lock de `atribuir_pedido`) | Revisitar se um terceiro caminho de lock for introduzido nesta área |
| Asserção de tempo de parede (`min(t) > 0.5 * max(t)`) sensível a máquina carregada | Trocar por uma comparação menos sensível a jitter se ficar flaky em CI |

### Posição e scheduler (tasks 6, 7)

| Achado | Ação sugerida |
|---|---|
| `registrar_posicao` não quantiza a própria entrada (confia no chamador) | Quantizar na porta de escrita fecharia a garantia para QUALQUER chamador futuro (inclusive um GPS real) — vale a pena antes de trocar a fonte |
| `Decimal("0.000001")` duplicado em `posicao.py` e `simulador_posicao.py` | Extrair para uma constante compartilhada se um terceiro lugar precisar do mesmo valor |
| `avancar_parados` sem `.limit()` no SELECT (decisão consciente: job desligado por padrão, escala de demonstração) | Reavaliar só se o avanço automático virar recurso de produção, não de apresentação |
| `Settings(**_campos_obrigatorios())` em `test_config.py` ainda lê o `.env` local — um dev com `AVANCO_AUTOMATICO_SEGUNDOS` setado localmente quebra esse teste (fragilidade pré-existente ao arquivo) | Isolar com `monkeypatch.delenv` se voltar a incomodar |

### Push e e-mail (tasks 8, 9)

| Achado | Ação sugerida |
|---|---|
| Comentário sobre a supressão de push cobre `CRIADO` e `CONFIRMADO` mas só explica o `CONFIRMADO` | Uma linha — estender o comentário |
| Nada registra explicitamente que `Notificacao.aluno_id` agora também carrega id de **staff**, não só de aluno | Vale uma nota no docstring do model — o nome da coluna hoje é enganoso |
| `PAPEIS_STOCK_ISSUE` e `PAPEIS_DELIVERY_DELAYED` nascem sem consumidor além do já existente (código que o plano mandou escrever mas cujo caminho de leitura já era servido por outro lugar) | Confirmar se são redundantes com o handler existente e remover, ou documentar por que coexistem |
| Handler de `order.status_changed` abre sessão e comita mesmo para `CRIADO`/`CONFIRMADO` (onde a lista de destinatários é vazia) | Baixo custo (uma sessão vazia); otimizar só se o volume justificar |
| Os dois testes novos de `test_shipment_created_*` remendam `consumer_module.async_session` mesmo o handler nunca abrindo sessão (setup morto copiado de testes irmãos) | Cosmético — remover o remendo desnecessário na próxima vez que o arquivo for tocado |

### Flutter (tasks 10-13)

| Achado | Ação sugerida |
|---|---|
| `currentDisplayName()` roda dentro de um try que só captura `AuthException` | Ampliar o catch se um novo tipo de falha de rede aparecer |
| `SessionSwitcher.manager` é costura de injeção sem teste dedicado | Cobrir se o widget ganhar lógica própria além de delegar ao `SessionManager` |
| `SessionManager.limpar()` sem teste e sem chamador | Ou remover (YAGNI) ou usar — hoje é código morto de baixo risco |
| Comentário em `shipment_login_screen.dart` cita `app/routers/shipments.py`, arquivo que não existe (o router é `app/routers/carregamentos.py`) | Uma linha — corrigir o nome do arquivo no comentário |
| `_ShipmentLoginCard.build()` passa de ~50 linhas (guideline do CLAUDE.md) | Extrair um subwidget na próxima vez que o arquivo for tocado |
| Validador da senha usa `.isEmpty` enquanto os outros três campos usam `.trim().isEmpty` | Padronizar — inconsistência cosmética, sem risco de segurança (senha com espaço nas pontas seria rejeitada por senha errada no backend de qualquer forma) |
| Marcador do entregador no mapa só aparece depois do primeiro tick do polling (10s) | Comportamento aceitável — nenhuma ação necessária a menos que a demonstração precise do marcador imediato |
| `fetchCarregamentos`/`fetchPedidosDoCarregamento`/`fetchTransportadoras` (Flutter) hardcodeiam `limit` sem paginação exposta | YAGNI por enquanto — expor parâmetros se algum dia houver mais de 50 carregamentos numa demonstração |
| `ShipmentCriado.fromJson` (Flutter) constrói um `Shipment` descartável | Refatoração de baixo risco |
| Segunda variante do 409 de atribuição (pedido já em outro carregamento) sem teste próprio no Flutter | Escrever se a UI de erro para esse caso for revisitada |

### Achado desta própria task (15), não de nenhuma anterior

| Achado | Ação sugerida |
|---|---|
| **`GET /notifications` com um token de carregamento (`role="carregamento"`, `sub` = id do lote, não UUID) provavelmente estoura 500.** `notification-service/app/dependencies.py::get_current_user_id` devolve `sub` cru, sem checar `role`; `app/routers/notificacoes.py::listar_notificacoes` (e as outras três rotas do arquivo) fazem `Notificacao.aluno_id == aluno_id` sem try/except, e `aluno_id` é `UUID(as_uuid=True)` — um `sub` que não é UUID (o token de lote é `str(carregamento.id)`, um inteiro) tende a estourar na camada do driver ao tentar bindar o parâmetro. **Não verificado ao vivo** — esta task não sobe o stack. É o motivo pelo qual `docs/smoke-test.md` instrui explicitamente a **não** conferir o sino de notificação numa sessão aberta só pelo código do carregamento. | Confirmar contra o stack; se confirmado, a correção mais barata é `requer_papel`/checagem de `role` nas quatro rotas de `notificacoes.py` (nenhuma delas aceita hoje um token de lote de propósito — não é um recurso a preservar) |

---

## O que ficou registrado como dívida

Nenhum destes é bug a corrigir; todos foram medidos e deixados de propósito,
ou herdados de specs anteriores e não agravados por esta.

**Backend**

- Expiração/revogação do token de carregamento é só o prazo fixo de 12
  horas — sem refresh, sem denylist, sem "encerrar carregamento" antes
  disso. Fora de escopo por decisão da spec (seção 6 de `order-flow.md`).
- Um carregamento interpola para **um** destino (o primeiro pedido do lote
  com coordenada congelada) — roteirização com várias paradas está fora de
  escopo.
- `avancar_parados` faz `SELECT` sem `.limit()` — decisão consciente dado
  que o job é desligado por padrão e a escala é de demonstração.
- O achado de `GET /notifications` com token de carregamento, acima.

**Flutter**

- `SessionManager.limpar()` sem chamador.
- Múltiplas sessões (`DEMO_MULTI_SESSAO`) continuam atrás de uma flag de
  compilação — não é o caminho de produção, é o caminho de uma pessoa
  demonstrando os quatro perfis num único aparelho.

**`web-admin`**

- Continua sem suíte de teste (decisão D11, herdada da spec B). A
  verificação é `npm run build`.
- `fetchCarregamentos`/`fetchTransportadoras` sem paginação exposta na UI
  (hardcoded `limit=50`/`100`).

**Toda a dívida já registrada em `docs/back-end/partners-inventory-carriers.md`
§10 e em `docs/smoke-test.md`, herdada das specs A e B, continua valendo e
não foi revisitada por esta spec.**

---

## Os sete critérios de pronto, conferidos à mão

**Este documento verifica só o sétimo item.** Os outros seis exigem o
stack do usuário no ar e um dispositivo em mãos — nenhum dos dois esta task
tem autorização para providenciar (proibição global: nunca `docker compose
up/down/build`, nunca `make stack-*`). Cada linha abaixo é um item para o
usuário andar manualmente, com o resultado observado registrado aqui quando
andado — **hoje, nenhum foi exercitado**, e a coluna "Resultado" reflete
isso com honestidade em vez de presumir sucesso.

| # | Critério | Resultado |
|---|---|---|
| 1 | Um pedido de `CRIADO` a `ENTREGUE` pelas quatro telas, sem tocar no banco | **Não exercitado.** Roteiro em `docs/smoke-test.md`, Etapas 1-5. |
| 2 | O desvio de falta de estoque nos dois desfechos (substituição e cancelamento) | **Não exercitado.** Roteiro em `docs/smoke-test.md`, Etapa 6. |
| 3 | Push no perfil certo em cada transição, visto no aparelho | **Não exercitado.** Roteiro em `docs/smoke-test.md`, seção "Conferência do push, perfil por perfil" — nota: evitar conferir pela sessão de código de carregamento, ver o achado desta task acima. |
| 4 | O mapa do comprador com a posição andando durante o trânsito | **Não exercitado.** Roteiro em `docs/smoke-test.md`, Etapa 5, passo 2. |
| 5 | O entregador entrando só com código, senha, nome e contato | **Não exercitado.** Roteiro em `docs/smoke-test.md`, Etapa 5. |
| 6 | Com `AVANCO_AUTOMATICO_SEGUNDOS` ausente, nada avança sozinho | **Não exercitado contra o stack real** — verificado por teste automatizado (`test_it_is_off_by_default`, `test_the_automatic_advance_is_off_unless_configured`, ambos verdes na suíte medida acima), o que cobre a lógica mas não o comportamento observável do processo vivo. |
| 7 | As três suítes verdes (backend, Flutter, painel) | **Verificado nesta task.** Ver "Medição final" acima — todos os alvos passam, nenhum abaixo do baseline. |

O usuário deve andar os itens 1-6 usando `docs/smoke-test.md` como roteiro
(as Etapas 0-8 mais a seção de push), de preferência antes de qualquer
apresentação, e registrar o resultado observado — não a expectativa — como
o próprio brief desta task pede.

---

## O que este plano ensinou

Duas lições, mais curtas que as da spec B porque a execução foi mais limpa
— sem achados de PAR de tasks, sem revisão de branch ainda feita, sem
concorrência falsificada que passasse com o lock removido.

**Um plano pode estar certo sobre a arquitetura e errado sobre o
comportamento vizinho — a spec C errou duas vezes sobre o que já existia
(D5, D7), não sobre o que faltava construir.** A spec original afirmava que
`entrega.py` não publicava evento (falso — já publicava, pela mesma função
de transição que toda rota usa) e desenhava `AGUARDANDO_SUBSTITUICAO →
SEPARADO` (o que quebraria `finalizar_separacao`). As duas foram
descobertas por medição, antes de qualquer task ser escrita, e ficaram
registradas como D5 e D7 no plano — o padrão de "medir antes de escrever a
task" que a spec B também usou, aqui aplicado duas vezes de propósito, não
uma.

**Uma dependency que aceita "usuário OU token de escopo" tende a alargar o
papel de usuário em silêncio.** É o que aconteceu na task 5: escrever
`ator_entrega` para aceitar o token de lote em cima do conjunto de papéis já
existente é fácil de fazer certo para o caso novo e errado para o caso
velho, porque o caso velho tinha **quatro** conjuntos diferentes de papéis
espalhados pelas quatro rotas, e a versão nova colapsou os quatro num só.
Nenhum teste tinha o formato "admin é recusado aqui" para nenhuma das
quatro rotas antes desta spec — só "admin é aceito" onde já era aceito —,
então não havia rede que pegasse o alargamento até o revisor ler a rota
antiga ao lado da nova. A lição prática, que devia entrar no próximo brief
que tocar autorização compartilhada entre dois atores: **quando uma
dependency nova vai substituir quatro chamadas de `requer_papel` com
conjuntos diferentes, o teste que prova "o conjunto continua o mesmo de
antes" tem que existir para as quatro, não só para a que mudou de
comportamento visivelmente.**
