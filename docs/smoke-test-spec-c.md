# Plano de smoke test da spec C

**Para que serve:** decidir *o que* precisa ser exercitado à mão na spec C — o
fluxo de pedido ponta a ponta —, e por quê. É um plano, não um roteiro: o
roteiro do caminho feliz pelos quatro perfis está em
[`smoke-test.md`](smoke-test.md) e não é repetido aqui.

**A diferença entre os dois documentos importa.** O roteiro atravessa o caminho
feliz: aluno compra, admin confirma e despacha, separador separa, entregador
entra pelo código e entrega. Este plano cobre o resto — as bordas, os caminhos
negativos, as costuras entre funcionalidades e as degradações previstas. É onde
os defeitos desta entrega estavam.

A referência de comportamento é [`back-end/order-flow.md`](back-end/order-flow.md):
a máquina de estados, o carregamento e sua credencial, a posição **simulada**, o
avanço automático e a tabela de destinatário por transição. Este plano não
redefine nenhum deles; ele os provoca.

## Como este plano foi derivado

Não de imaginação. Cada bloco existe porque um defeito real apareceu ali durante
a execução — em nove das quinze tarefas a revisão pediu correção, e a revisão da
branch inteira ainda encontrou um defeito **crítico** e cinco importantes que
nenhuma revisão de tarefa individual podia ver. O registro completo está em
[`superpowers/plans/2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta-execution-record.md`](superpowers/plans/2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta-execution-record.md).

Quatro padrões se repetiram, e explicam o formato deste documento:

1. **A funcionalidade existia e não era alcançável.** A tela onde o aluno aceita
   um substituto estava pronta desde a fase anterior — e nenhuma notificação
   conseguia abri-la, porque a API serializa `occurrence_id` e a tela lia
   `ocorrencia_id`. Medir que "a tela existe" não é medir que alguém chega nela.
2. **O estado nasceu vazio em produção e cheio nos testes.** O registro de staff
   do notification-service é alimentado por evento; a suíte inseria as linhas à
   mão. Numa instalação onde as contas de demonstração já existiam, a tabela
   ficava vazia e **todo push de staff sumia calado**.
3. **A rede de segurança tirava alguém do fluxo.** O avanço automático pulava os
   efeitos colaterais da coleta: sem coordenada de destino congelada, o mapa não
   andava mais — e o pedido não ficava com dono.
4. **Um token que não é de usuário atravessava a frota.** O `sub` do
   carregamento é um inteiro; vinte e duas rotas do commerce e as quatro do
   notification-service o convertiam para UUID sem guarda, virando 500.

Por isso cada bloco diz o que **provocar**, não só o que conferir.

---

## Preparação

Vale a preparação do [`smoke-test.md`](smoke-test.md), inclusive a ordem
obrigatória `stack-rebuild` → `stack-up` → `services-migrate` → `services-seed`
→ `npm run build`. Além dela, esta spec tem quatro pré-requisitos próprios.

### P1 — O registro de staff precisa ser populado (senão o bloco 7 inteiro falha)

```bash
DEMO_ACCOUNTS_PASSWORD='...' make services-seed-demo
```

Rodar isto **depois** que a frota está de pé não é opcional e não é só para
criar contas. O `notification-service` mantém uma tabela `staff` local,
alimentada pelo evento `staff.created`; sem ela, `order.created` não avisa
ninguém, `AGUARDANDO_COLETA` não chega ao entregador e `ENTREGUE` não chega ao
admin — em silêncio, com o sino mostrando lista vazia.

O seed é idempotente: numa base onde as quatro contas já existem ele cria zero
contas **e ainda assim reanuncia** as três de staff, que é exatamente o caso da
sua máquina. Conferir:

```bash
docker exec -i edu-postgres psql -U edu -d notification_db \
  -c "select papel, nome from staff order by papel;"
```

Esperado: três linhas — `admin`, `entregador`, `separador`. Zero linhas
significa que o seed não rodou ou o RabbitMQ estava fora; nada do bloco 7 vai
funcionar antes de consertar isso.

### P2 — O avanço automático fica desligado

`AVANCO_AUTOMATICO_SEGUNDOS` **ausente** do `back-end/.env` é o estado padrão e
o critério de pronto 6. O bloco 6 liga e desliga de propósito; todos os outros
blocos assumem desligado. No log do commerce, na subida:

```
scheduler: avanço automático desligado (padrão)
```

### P3 — A chave do Maps decide se o mapa anda

`GOOGLE_MAPS_API_PLATAFORM` no `back-end/.env` (o compose a repassa como
`GOOGLE_MAPS_API_KEY`). Sem ela, a coleta continua funcionando e o pedido fica
**sem coordenada de destino** — o simulador o ignora e o marcador nunca aparece.
Isso é degradação prevista, não defeito; o bloco 5 exercita os dois lados.

### P4 — O e-mail sai em modo console por padrão

`EMAIL_BACKEND` ausente ou `console` escreve no log e não fala com a rede.
Para exercitar o envio real (bloco 8), `EMAIL_BACKEND=resend` mais
`RESEND_API_KEY`; o remetente é `no-reply@svemlab.com`, domínio já verificado.

### Tokens

Este plano usa chamadas diretas ao gateway além da interface, porque várias das
bordas não têm botão:

```bash
TOKEN=$(curl -s localhost:8100/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"aluno@demo.edu","password":"'"$DEMO_ACCOUNTS_PASSWORD"'"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["tokens"]["access_token"])')
```

Troque o e-mail para `admin@demo.edu`, `separador@demo.edu` ou
`entregador@demo.edu`. O token de **carregamento** sai por outra porta, sem
credencial prévia:

```bash
LOTE=$(curl -s localhost:8100/api/shipments/login \
  -H 'content-type: application/json' \
  -d '{"codigo":"ABCD2345","senha":"...","nome":"Maria","contato":"11999990000"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

Todas as rotas ficam sob `localhost:8100/api/`.

---

## Bloco 1 — O desvio de substituição, nos dois desfechos

**Risco:** é o critério de pronto 2, e foi o defeito **crítico** da entrega — a
tela existia e ninguém chegava nela.

| # | Provocar | Esperado |
|---|---|---|
| 1.1 | Como separador, `POST /occurrences/stock-shortage` num pedido em `EM_SEPARACAO` | 201; o pedido vai para `AGUARDANDO_SUBSTITUICAO` |
| 1.2 | Como aluno, olhar o rastreio do mesmo pedido | Continua `separating` — o estado novo não é um sexto passo na timeline |
| 1.3 | Como aluno, contar as notificações geradas pelo passo 1.1 | **Uma**, não duas: `Pedido #XXXXXXXX: item em falta` |
| 1.4 | **No aparelho**, tocar nessa notificação | Abre a tela de resolução com o produto e as sugestões |
| 1.5 | Escolher um substituto e confirmar | 200; o pedido volta para `EM_SEPARACAO`; o separador é notificado |
| 1.6 | Repetir 1.1 e resolver com `remover_item` | Mesmo retorno a `EM_SEPARACAO`, item fora, total menor |
| 1.7 | Repetir 1.1 e resolver com `cancelar_pedido` | Pedido `CANCELADO`; o aluno vê `cancelled`; aluno e admin notificados |
| 1.8 | Como separador, tentar `PATCH /picking/{id}/finish` com a ocorrência ainda aberta | 400 com a frase sobre decisão do aluno |
| 1.9 | Como admin, `POST /occurrences/stock-shortage` num pedido em `AGUARDANDO_COLETA` | 201, e o status **não muda** — a ocorrência é registro de fato |

**Por que 1.3 e 1.4 são linhas próprias.** O passo 1.1 publica dois eventos: a
transição e `order.stock_issue`. Se a tabela de destinatário voltar a endereçar
a transição ao aluno, ele recebe duas notificações para um evento — e a que
manda "tocar" é a que **não** carrega `ocorrencia_id`, portanto inerte. O par
1.3/1.4 é o teste de fumaça dessa regressão específica.

**Por que 1.9 existe.** `transicionar_pedido` recusa transição inválida com 400,
e a ocorrência já está commitada quando ele roda. Se a guarda que engole esse
400 sumir, o admin recebe erro por um pedido cujo efeito principal deu certo.

---

## Bloco 2 — A credencial do carregamento

**Risco:** é senha de verdade, circulando por e-mail, para alguém que não tem
conta na frota.

| # | Provocar | Esperado |
|---|---|---|
| 2.1 | Como admin, `POST /shipments` com uma transportadora | 201; `codigo` com 8 caracteres, `senha` com 12 |
| 2.2 | `GET /shipments` e `GET /shipments/{id}` | Trazem `codigo`, **nunca** `senha` nem `senha_hash` |
| 2.3 | `POST /shipments/login` com código e senha corretos | 200; o `sub` do token é o id do lote e o `role` é `carregamento` |
| 2.4 | Login com o código certo e senha errada | 401 `Código ou senha inválidos` |
| 2.5 | Login com um código que não existe | **Mesma** resposta, **mesma** mensagem, e tempo comparável ao de 2.4 |
| 2.6 | Conferir o lote depois do primeiro login | `entregador_nome`, `entregador_contato` e `aberto_em` gravados |
| 2.7 | Logar de novo com nome e contato diferentes | Os valores do **primeiro** acesso permanecem |
| 2.8 | Procurar a senha em qualquer lugar depois de 2.1 | Não existe: nem em rota, nem em `notificacoes`, nem em log |

**Por que 2.5 tem uma linha só para o tempo.** O caminho do código inexistente
gasta um bcrypt contra um hash descartável de propósito. Se alguém "otimizar"
esse retorno antecipado, a rota vira um oráculo de quais lotes existem — e a
diferença aparece como resposta em microssegundos contra ~100 ms.

---

## Bloco 3 — O que o token de lote pode, e o que ele não pode

**Risco:** o token não representa um usuário. Antes da correção final, ele
atravessava a frota inteira produzindo 500.

| # | Provocar | Esperado |
|---|---|---|
| 3.1 | Com `$LOTE`, `GET /delivery/queue` | Só os pedidos **daquele** lote |
| 3.2 | Com `$LOTE`, `PATCH /delivery/{id}/collect` e `/deliver` num pedido do lote | 200 nos dois |
| 3.3 | Com `$LOTE`, `/collect` num pedido **real** de outro lote | 403 |
| 3.4 | Com `$LOTE`, `GET /picking/queue` | 403 — `requer_papel` recusa; não é papel de frota |
| 3.5 | Com `$LOTE`, `GET /orders` (rota de aluno) | **403, não 500** |
| 3.6 | Com `$LOTE`, `GET /notifications` | **403, não 500** |
| 3.7 | No aparelho, na sessão aberta por código, tocar o sino | Estado de erro na tela, sem queda |
| 3.8 | Na mesma sessão, abrir o rastreio de um pedido em rota | **Não** existe o botão "Reportar atraso" |
| 3.9 | Repetir 3.8 logado como `entregador@demo.edu` | O botão **existe** e funciona |

**Por que 3.3 usa um pedido real de outro lote.** Um id inventado prova
validação de entrada, não autorização. Só um pedido que existe, pertence a
outro carregamento e está no estado certo prova que a recusa veio do escopo.

**Por que 3.8 e 3.9 andam juntas.** `POST /occurrences/delivery-delay` continua
exigindo papel `entregador` — o token de lote não foi alargado. O cliente
esconde o botão que o servidor recusaria; se ele reaparecer numa sessão de lote,
alguém devolveu uma ação impossível para a tela.

---

## Bloco 4 — Um carregamento, uma origem

**Risco:** a origem do lote é o ponto de partida da interpolação de posição. Um
lote de duas origens não tem de onde sair — e o sentinela original furava
exatamente no caso que o seed torna possível.

| # | Provocar | Esperado |
|---|---|---|
| 4.1 | Atribuir o primeiro pedido a um lote novo | 200; o lote congela `origem_rotulo`/`origem_lat`/`origem_lng` do pedido |
| 4.2 | Atribuir um pedido de **outra** origem ao mesmo lote | 409 `Este carregamento sai de outra origem. Crie um carregamento separado para os pedidos desta origem.` |
| 4.3 | Conferir o pedido recusado em 4.2 | `carregamento_id` continua nulo — nada foi gravado pela metade |
| 4.4 | Atribuir ao lote um pedido que já está em **outro** lote | 409 `Este pedido já está em outro carregamento` |
| 4.5 | Reatribuir ao **mesmo** lote um pedido que já está nele | 200 — idempotente, o duplo-clique do admin não é erro |
| 4.6 | Criar um lote e atribuir primeiro um pedido **sem** origem, depois um com origem real | O primeiro entra (200), o segundo é recusado (409) |

**Por que 4.6 existe.** `orders.origem_*` é anulável — um checkout sem
fornecedor resolvido deixa os três campos nulos, e nada os preenche depois. A
versão original do sentinela ("o rótulo está vazio?") nunca congelava nesse
caso, e o segundo pedido sobrescrevia a origem sem 409 nenhum.

---

## Bloco 5 — A posição, e as duas maneiras de ela não aparecer

**Risco:** critério de pronto 4. E **a posição é simulada**: não há entregador
real nem GPS neste sistema (ver [`back-end/order-flow.md`](back-end/order-flow.md) §3).

| # | Provocar | Esperado |
|---|---|---|
| 5.1 | `GET /orders/{id}/tracking` antes da coleta | 200 com `courier_position: null`; o mapa desenha origem e destino, sem marcador móvel |
| 5.2 | Coletar com a chave do Maps configurada | `orders.destino_lat`/`destino_lng` preenchidos uma vez |
| 5.3 | Acompanhar o rastreio por ~1 minuto | `courier_position` muda a cada ~10 s, sempre entre origem e destino |
| 5.4 | Deixar o pedido em trânsito por mais de 6 minutos | A posição para no destino e não passa dele |
| 5.5 | **Sem** a chave do Maps, repetir 5.2 e 5.3 | A coleta responde 200 do mesmo jeito; `courier_position` fica nulo para sempre nesse pedido |
| 5.6 | Olhar o campo `carrier` do rastreio depois de atribuir o pedido a um lote | O nome real da transportadora, não a constante `Logistics Intel Express` |

**Por que 5.5 é um passo e não um acidente.** A coleta nunca pode falhar porque
a Google não respondeu — a operação para, e o mapa é o item menos importante da
tela nesse momento. Se a coleta devolver 500 sem chave, a garantia foi perdida.

---

## Bloco 6 — O avanço automático como rede de segurança

**Risco:** ele existe para salvar o apresentador preso numa tela, e a maneira de
ele estragar a apresentação é correr na frente dela.

| # | Provocar | Esperado |
|---|---|---|
| 6.1 | Com `AVANCO_AUTOMATICO_SEGUNDOS` ausente, deixar um pedido parado 15 minutos | Nada avança. Critério de pronto 6 |
| 6.2 | Definir `AVANCO_AUTOMATICO_SEGUNDOS=600`, subir de novo o commerce, deixar um pedido parado | No log, `avanço automático LIGADO, prazo de 600s`; depois de 10 minutos o pedido avança um passo |
| 6.3 | Com o avanço ligado, tocar o pedido à mão antes do prazo | A contagem reinicia; nada dispara |
| 6.4 | Com o avanço ligado, deixar um pedido em `AGUARDANDO_SUBSTITUICAO` | **Nunca** avança sozinho — a decisão é do aluno |
| 6.5 | Com o avanço ligado, deixar um pedido parado em `AGUARDANDO_COLETA` | Vai para `EM_TRANSITO` **e o destino é congelado** — o mapa continua andando |
| 6.6 | Depois de 6.5, tentar entregar como `entregador@demo.edu` | 403 — a coleta automática não deixou dono. O próprio avanço leva o pedido a `ENTREGUE` |

**6.6 não é defeito, é consequência declarada.** Está escrita em
[`back-end/order-flow.md`](back-end/order-flow.md) §4: quando a rede de
segurança faz a coleta, o pedido fica sem `deliverer_id`, então o entregador com
**conta** não confirma mais a entrega dele — o entregador com token de **lote**
não é afetado, porque a posse dele é o carregamento. Desligue a rede se quiser
demonstrar a entrega pela conta.

---

## Bloco 7 — Push no perfil certo

**Risco:** critério de pronto 3, e o modo de falha é o silêncio. Requer o
pré-requisito **P1** — sem o registro de staff, tudo abaixo passa a ser "nenhuma
notificação" sem nenhum erro.

| # | Provocar | Esperado |
|---|---|---|
| 7.1 | Aluno cria um pedido | Admin e separador recebem; **o aluno não** |
| 7.2 | Admin confirma o pagamento | Aluno e separador recebem (`AGUARDANDO_SEPARACAO`) |
| 7.3 | Conferir se alguém recebeu algo por `CONFIRMADO` | Ninguém — é estado de passagem na mesma chamada |
| 7.4 | Separador finaliza a separação | Aluno recebe; o entregador **conta** recebe o aviso de coleta |
| 7.5 | Entrega confirmada | Aluno **e admin** recebem |
| 7.6 | Aluno resolve a ocorrência aceitando a substituição | O **separador** recebe — é ele que estava bloqueado |
| 7.7 | Esvaziar a tabela `staff` e repetir 7.2 | O **aluno ainda recebe** — a notificação do comprador nunca depende de evento de staff |

**Por que 7.7 vale o incômodo de esvaziar a tabela.** É a única maneira de
provar que a resolução de destinatário não engole o comprador quando o registro
está frio — o caso real de uma frota recém-subida.

```sql
-- para 7.7, e para repovoar depois: rode o seed de novo (P1)
DELETE FROM staff;
```

---

## Bloco 8 — O e-mail da credencial

**Risco:** é o primeiro envio de e-mail do backend desde a spec A, e o corpo
carrega uma senha.

| # | Provocar | Esperado |
|---|---|---|
| 8.1 | Com `EMAIL_BACKEND` em `console`, criar um carregamento | O log mostra destinatário e assunto; **não** mostra o corpo nem a senha |
| 8.2 | Com `EMAIL_BACKEND=resend` e chave válida, criar um carregamento | O e-mail chega ao endereço da transportadora, com código e senha |
| 8.3 | Com `EMAIL_BACKEND=resend` e chave vazia ou inválida | O envio falha alto; a mensagem vai para a fila morta `edu.events.dead` |
| 8.4 | Conferir `notificacoes` depois de qualquer criação de carregamento | **Nenhuma** linha para `shipment.created` |

**8.3 tem uma consequência que precisa ser dita.** A mensagem parada na fila
morta contém a senha em claro. Drenar essa fila é manusear credencial — está em
[`back-end/order-flow.md`](back-end/order-flow.md) §6.

---

## Bloco 9 — Múltiplas sessões (só na compilação de demonstração)

| # | Provocar | Esperado |
|---|---|---|
| 9.1 | Rodar o app pelo `make front` normal | Nenhum seletor de sessão em lugar nenhum |
| 9.2 | Rodar por `make front-demo` e entrar com dois perfis | Os dois aparecem no seletor |
| 9.3 | Trocar de perfil pelo seletor | Entra sem redigitar senha e cai na tela do papel |
| 9.4 | Depois de trocar, conferir o perfil de origem | Continua guardado — trocar não apaga o outro |

---

## Bloco 10 — O admin, nas duas telas

A mesma API vista do aparelho (aba nova no app) e do painel Angular
(`/carregamentos`).

| # | Provocar | Esperado |
|---|---|---|
| 10.1 | Criar um carregamento pela tela | Código e senha aparecem **uma vez**, copiáveis, com o aviso de que a senha não é consultável depois |
| 10.2 | Fechar o modal e procurar a senha de novo | Não há caminho de volta — nem na lista, nem no detalhe |
| 10.3 | Atribuir um pedido de outra origem pela tela | A tela mostra **a frase do servidor**, não uma reescrita |
| 10.4 | No app: expandir "Ver pedidos" de um lote, criar outro lote, e olhar o card expandido | Continua mostrando os pedidos **dele** — a lista vem do mais novo primeiro, e os cards não podem trocar de conteúdo ao reordenar |
| 10.5 | Repetir 10.1 a 10.3 no painel Angular | Mesmo comportamento |

---

## Evidência no banco

Cinco consultas que provam o que a tela não mostra:

```sql
-- 1. As duas revisions desta spec estão aplicadas
SELECT version_num FROM alembic_version;   -- commerce_db:     c1d2e3f4a5b6
                                           -- notification_db: d4c5b6a7e8f9

-- 2. O lote guarda só o hash, nunca a senha
SELECT id, codigo, left(senha_hash, 7) AS hash_prefixo,
       entregador_nome, aberto_em
FROM carregamentos ORDER BY criado_em DESC LIMIT 5;   -- hash_prefixo: $2b$12$

-- 3. A posição é série temporal, não campo único
SELECT carregamento_id, count(*) AS pontos,
       min(registrado_em), max(registrado_em)
FROM posicao_entrega GROUP BY carregamento_id;

-- 4. O pedido carrega o lote e o destino congelado
SELECT id, status, carregamento_id, destino_lat, destino_lng, carrier_name
FROM orders WHERE carregamento_id IS NOT NULL ORDER BY created_at DESC LIMIT 5;

-- 5. O registro de staff do notification-service (pré-requisito P1)
SELECT papel, nome FROM staff ORDER BY papel;   -- três linhas
```

---

## O que não é bug

- **A posição do entregador é simulada.** Não há aparelho, não há GPS. O
  backend interpola entre a origem do lote e o destino do pedido e grava pela
  mesma função que um aparelho usaria. Isto é declarado, não escondido:
  [`back-end/order-flow.md`](back-end/order-flow.md) §3.
- **"Push" é notificação dentro do app.** O envio real por FCM saiu na spec A;
  o sino lê `GET /notifications`.
- **O sino na sessão aberta por código responde 403.** O token de lote não é
  usuário do notification-service. É a recusa correta, não uma queda — e a
  conferência de push do entregador se faz pela conta `entregador@demo.edu`.
- **A sessão de lote não vê "Reportar atraso".** A rota exige papel
  `entregador`; o cliente não oferece o que o servidor recusaria.
- **Coleta feita pela rede de segurança impede a entrega pela conta** (6.6).
- **Sem chave do Maps o marcador nunca aparece** (5.5).
- **`flutter analyze` sai com 6 avisos `info`.** É o baseline do repositório;
  a contagem não mudou nesta entrega, e parte deles está em arquivos que ela
  tocou.
- **O registro de execução ainda lista três itens como dívida aberta** —
  imports do `alembic/env.py`, a prosa "nove valores" e o teste espelho do
  resolve — que a onda final de correção fechou. Divergência conhecida do
  documento, não do código.

---

## Critério de aprovação

A spec C passa quando os dez blocos passam **e** as cinco consultas de evidência
batem, com os sete critérios de pronto do design cobertos assim:

| Critério | Onde é exercitado |
|---|---|
| 1. Pedido de `CRIADO` a `ENTREGUE` pelos quatro perfis | [`smoke-test.md`](smoke-test.md), etapas 1 a 5 |
| 2. Desvio de falta de estoque nos dois desfechos | Bloco 1 |
| 3. Push no perfil certo, verificado no aparelho | Bloco 7 (+ P1) |
| 4. Mapa mostrando a posição andar | Bloco 5 |
| 5. Entregador entra só com código, senha, nome e contato | Blocos 2 e 3 |
| 6. Nada avança sozinho com a variável ausente | Bloco 6, passo 6.1 |
| 7. Suítes verdes | `uv run pytest -q` por serviço, `flutter test`, `npm run build` |

Um bloco falho não invalida os outros — anote qual, com a resposta recebida, e
siga; a triagem do [`smoke-test.md`](smoke-test.md) vale aqui também.

Três resultados são bloqueadores, e não simples falhas de bloco:

- **Qualquer 500.** Esta entrega já teve um token que produzia 500 em vinte e
  duas rotas; um 500 novo é dessa família até prova em contrário.
- **A senha do carregamento aparecendo em log, em listagem ou em notificação.**
- **Divergência no bloco 4.** Origem que se move depois de o lote existir
  corrompe o ponto de partida da rota, e é o mesmo defeito de registro histórico
  que bloqueava a spec B.
