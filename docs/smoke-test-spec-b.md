# Plano de smoke test da spec B

**Para que serve:** decidir *o que* precisa ser exercitado à mão na spec B, e
por quê. É um plano, não um roteiro: o roteiro de ponta a ponta pelos quatro
perfis está em [`smoke-test.md`](smoke-test.md) e não é repetido aqui.

**A diferença entre os dois documentos importa.** O roteiro atravessa o caminho
feliz — aluno compra, admin confirma, separador separa, entregador entrega.
Este plano cobre o resto: as bordas, os caminhos negativos e as costuras entre
funcionalidades. É onde os defeitos desta entrega estavam.

## Como este plano foi derivado

Não de imaginação. Cada bloco abaixo existe porque um defeito real apareceu ali
durante a execução, e a maioria só apareceu na revisão da branch inteira — não
na revisão de cada tarefa. O registro completo está em
[`superpowers/plans/2026-09-08-spec-b-parceiros-estoque-transportadora-execution-record.md`](superpowers/plans/2026-09-08-spec-b-parceiros-estoque-transportadora-execution-record.md).

Três padrões se repetiram, e eles explicam o formato deste documento:

1. **O defeito morava na costura, não na funcionalidade.** Duas funcionalidades
   corretas isoladamente produziam comportamento errado juntas. Nenhuma revisão
   de tarefa individual podia ver isso.
2. **O arquivo culpado costumava ter diff vazio.** Código que ninguém editou
   mudou de comportamento porque dois modelos passaram a dividir uma tabela, ou
   porque um serviço compartilhado ganhou um modo de falha novo.
3. **O caminho negativo não tinha teste.** A suíte herdada monta carrinho e
   pedido com produto **sem linha de estoque** — estado que o seed torna
   impossível em produção. Regras novas simplesmente não disparavam nela.

Por isso cada bloco diz o que provocar, não só o que conferir.

## Preparação

Vale a preparação do [`smoke-test.md`](smoke-test.md), inclusive a ordem
obrigatória `stack-rebuild` → `stack-up` → `services-migrate` → `services-seed`
→ `npm run build`. As conferências 0.5 e 0.6 daquele documento são
pré-requisito deste: sem a migration e o seed da spec B, tudo abaixo falha por
motivo errado.

Este plano usa chamadas diretas ao gateway além da interface, porque várias das
bordas não têm botão. Um token sai assim:

```bash
TOKEN=$(curl -s localhost:8100/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"aluno@demo.edu","password":"'"$DEMO_ACCOUNTS_PASSWORD"'"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["tokens"]["access_token"])')
```

Troque o e-mail para `admin@demo.edu`, `separador@demo.edu` ou
`entregador@demo.edu` conforme o bloco. Todas as rotas ficam sob
`localhost:8100/api/`.

---

## Bloco 1 — Origem única do carrinho

**Risco:** pedido misto é proibido por decisão da spec B, não adiado. A regra
vive no serviço, sob o lock de linha do carrinho — se vivesse na tela, duas
adições simultâneas montariam um carrinho misto sem erro nenhum.

| # | Provocar | Esperado |
|---|---|---|
| 1.1 | No app, adicionar um produto da seção do parceiro e depois um da grade própria | 409, e a tela mostra a frase do servidor |
| 1.2 | Conferir a frase exibida | Exatamente `Seu carrinho já tem itens de outro parceiro. Finalize ou esvazie o carrinho antes de misturar.` |
| 1.3 | Esvaziar o carrinho e repetir na ordem inversa | Mesmo 409, mesma frase |
| 1.4 | Adicionar dois itens do **mesmo** parceiro | 201 nos dois |

**Por que 1.2 é uma linha própria:** a frase tem um dono só, o backend. Se o
texto na tela divergir do texto acima, alguém guardou uma cópia no cliente — e
a próxima mudança de texto vai sair pela metade. O grep que prova isso é
`grep -rn "outro parceiro" front-end-flutter/lib/`, que tem que voltar vazio.

## Bloco 2 — Estoque auditado

**Risco:** antes desta entrega o ajuste de estoque gravava um valor absoluto e
não deixava rastro. Agora as duas portas — a rota absoluta do admin e a rota de
delta — passam pelo mesmo núcleo, sob lock, gravando a linha de auditoria na
mesma transação.

| # | Provocar | Esperado |
|---|---|---|
| 2.1 | No painel, ajustar o estoque de um produto sem escolher o motivo | O botão CONFIRMAR não habilita |
| 2.2 | Ajustar com motivo escolhido | 200, e a quantidade muda na tela |
| 2.3 | Conferir a trilha: `GET /api/products/{id}/stock-adjustments` como admin | Uma linha por ajuste, com `quantidade_anterior`, `quantidade_nova`, `motivo` e `autor_id` |
| 2.4 | Ajustar para um valor que deixaria o estoque negativo | 422, e **nada** gravado — nem estoque nem auditoria |
| 2.5 | `PATCH /api/admin/inventory/{id}/adjust?quantidade=1&motivo=%20%20%20` | 422: motivo só de espaço é motivo nenhum |

**2.1 é o ponto inteiro do bloco.** O painel já teve um motivo pré-selecionado
por padrão, o que satisfazia a obrigatoriedade no instante em que o modal
abria e gravava sempre a mesma string. Auditoria preenchida pelo cliente não é
auditoria.

## Bloco 3 — Produto inativo

**Risco:** `active` foi escrito, exibido e lido por nada durante boa parte da
execução. O painel tinha um botão que não fazia efeito. Hoje a regra tem quatro
portas, e a última é a que grava em **pedido**, não em carrinho.

| # | Provocar | Esperado |
|---|---|---|
| 3.1 | No painel, desativar um produto | Some do catálogo do app (puxe para atualizar) |
| 3.2 | Como aluno, `POST /api/cart/items` com o id do produto desativado | 404 — não some da vista e continua comprável |
| 3.3 | Recomprar um pedido antigo que continha esse produto (`POST /api/orders/{id}/rebuy`) | 200, com o resto do pedido no carrinho e o inativo **pulado** |
| 3.4 | Abrir uma ocorrência de falta de estoque cujo substituto candidato esteja desativado | O produto desativado **não** aparece entre os sugeridos |
| 3.5 | Carrinho montado **antes** da desativação | Continua fechando pedido normalmente |
| 3.6 | Painel: o produto desativado continua listado para administração | Sim — é como se reativa |

**3.4 é a porta perigosa.** A substituição grava o produto escolhido direto no
pedido, sem passar pelo carrinho, e o caminho de fallback roda justamente
quando o modelo de embedding falha. Se puder, force o caso degradado
desligando o serviço de embedding e repita 3.4.

**3.5 é a guarda.** A regra vale para adicionar, não retroativamente. Se um
carrinho antigo parar de fechar, isso é regressão.

## Bloco 4 — Origem congelada no pedido

**Risco:** a origem de expedição é resolvida na criação e **congelada**. A spec C
lê essas colunas para simular a rota e não recalcula.

| # | Provocar | Esperado |
|---|---|---|
| 4.1 | Fechar um pedido e conferir no banco | `origem_rotulo`, `origem_lat`, `origem_lng` preenchidos em `orders` |
| 4.2 | Conferir `order_items.supplier_id` do mesmo pedido | Preenchido — coluna que existia desde a fase 2 e nunca era escrita |
| 4.3 | Editar a origem do parceiro no painel e reabrir o pedido antigo | O pedido **continua** com a origem antiga |

```sql
SELECT o.id, o.origem_rotulo, o.origem_lat, o.origem_lng,
       count(oi.supplier_id) AS itens_com_fornecedor
FROM orders o JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id ORDER BY o.created_at DESC LIMIT 3;
```

**4.3 é a propriedade inteira.** Se a origem mudar junto com o cadastro do
parceiro, ela é referência e não retrato — e todo pedido já despachado passa a
mentir sobre de onde saiu.

## Bloco 5 — Ocorrência de transportadora × separação

**Risco:** o Java tinha uma ocorrência ancorada na transportadora; aqui ela é
uma **dimensão** da ocorrência de pedido. Duas funcionalidades corretas
isoladamente travavam o pedido quando juntas.

| # | Provocar | Esperado |
|---|---|---|
| 5.1 | Admin abre `POST /api/occurrences/carrier` num pedido em separação; separador chama `PATCH /api/picking/{id}/finish` | **200** — ocorrência de transportadora é assunto da administração e não segura a fila |
| 5.2 | Aluno tenta resolver essa ocorrência (`POST /api/occurrences/{id}/resolve`) | 400 — só admin fecha, por `POST /api/occurrences/{id}/close` |
| 5.3 | Ocorrência de falta de estoque aberta pelo separador; `finish` no mesmo pedido | 400 com a mensagem pedindo a decisão do aluno |
| 5.4 | **Duas** ocorrências abertas no mesmo pedido, depois `finish` | 400 — nunca 500 |

**5.1 e 5.4 são os dois defeitos que a revisão final achou.** No 5.1 o pedido
ficava preso atrás de uma mensagem mandando o separador aguardar uma decisão
do aluno que o próprio sistema tornara impossível. No 5.4 estourava
`MultipleResultsFound` sem tratamento — 500 na cara do separador — e o roteiro
de ponta a ponta chega nesse estado sozinho, porque a etapa 6 abre uma
ocorrência e a etapa 7 abre outra no mesmo pedido.

## Bloco 6 — Recompra entre parceiros

| # | Provocar | Esperado |
|---|---|---|
| 6.1 | Pôr no carrinho um item do parceiro A; recomprar um pedido antigo só do parceiro B | 409 com a frase do bloco 1 — nunca 500 |

**Por que tem bloco próprio:** a recompra é o **segundo** chamador do serviço de
carrinho. Quando a regra de origem única nasceu, só o primeiro chamador
aprendeu a tratá-la. Nenhum cliente hoje chama essa rota, o que é exatamente o
motivo de ela precisar de conferência manual.

## Bloco 7 — Códigos de pagamento emitidos pelo backend

**Risco:** o app inventava o código PIX e a linha do boleto com `Random()`. Agora
o backend emite, derivando do id do pedido.

| # | Provocar | Esperado |
|---|---|---|
| 7.1 | Fechar pedido em PIX e conferir o código na tela | Código exibido, vindo do backend |
| 7.2 | `POST /api/orders/{id}/confirm-payment` duas vezes no mesmo pedido | **Mesmo código** nas duas — é determinístico, logo seguro de repetir |
| 7.3 | Mesmo teste com boleto | Linha digitável no formato `00000.00000 00000.000000 00000.000000 0 00000000000000` |
| 7.4 | Pedido em cartão | `payment_code` nulo, sem erro |
| 7.5 | Pedir o código de um pedido de **outro** aluno | 404 |
| 7.6 | `grep -rn "_generatePixCode\|_generateBoletoCode\|BR.GOV.BCB.PIX" front-end-flutter/lib/` | Vazio |

**7.5 é controle de acesso, não formatação.** A rota autentica *e* filtra pelo
dono; autenticar e servir qualquer id digitado é o buraco que a regra existe
para fechar.

## Bloco 8 — Catálogo por parceiro

| # | Provocar | Esperado |
|---|---|---|
| 8.1 | Abrir o marketplace no app | A seção de parceiros mostra **um** bloco, o parceiro externo |
| 8.2 | Desativar esse parceiro no painel e recarregar o app | A seção some inteira — sem tela de erro |
| 8.3 | `GET /api/products?partner_id=<id de parceiro inativo>` | 200 com lista **vazia**, nunca 404 |
| 8.4 | `GET /api/products?partner_id=999999999999` | 422, nunca 500 |

**8.2 e 8.3 são a mesma regra vista de dois lados:** um parceiro desativado
enquanto o aluno navega não pode virar tela de erro. E o filtro é sempre por
id — se algum comportamento depender do **nome** do parceiro, é violação
direta da spec, testada por
`back-end/commerce-service/tests/test_partners_seed.py`.

## Bloco 9 — O painel no gateway

O painel nunca tinha rodado contra este backend. Não há suíte de teste nele: o
build AOT é o único portão automatizado, e ele só pega forma de tipo declarado.
Por isso este bloco é mais longo que os outros.

| # | Provocar | Esperado |
|---|---|---|
| 9.1 | Login no painel | Entra — a resposta é `{user, tokens:{access_token}}`, não a forma do Spring |
| 9.2 | Listar produtos, estoque, transportadoras e ocorrências | Todas populam; nenhuma tela vazia com console limpo |
| 9.3 | Criar produto | Exige escolher um parceiro; sem parceiro não envia |
| 9.4 | Provocar um erro real (sku repetido) | A mensagem exibida é a **do servidor**, não uma genérica |
| 9.5 | Conferir os contadores da tela de estoque contra o banco | `SELECT count(*) FROM estoque;` bate com o rodapé |
| 9.6 | Transportadoras: criar, editar, mudar status | Os três funcionam; `rating` e `sla_percentage` aparecem certos |
| 9.7 | Ocorrências: filtrar por transportadora e fechar uma | Fecha; não há botão de reabrir, porque fechar é definitivo |
| 9.8 | `grep -rn "8080\|/api/v1" web-admin/src web-admin/proxy.conf.json` | Vazio |

**9.5 existe porque os contadores já mentiram.** A tela buscava uma página e
anunciava o número dessa página como se fosse o total: com 500 linhas de
estoque ela dizia "de 100 resultados", e o card de ESTOQUE BAIXO contava só
dentro das 100 — o que um operador lê como "não falta nada".

**9.4 é a mesma regra do bloco 1, do outro lado.** A frase tem um dono, e o
painel chegou a substituir "o ajuste deixaria o estoque negativo" por "confira
a quantidade e o motivo", que manda o operador procurar no lugar errado.

## Bloco 10 — Identificadores fora de faixa

| # | Provocar | Esperado |
|---|---|---|
| 10.1 | `GET /api/partners/3000000000` | 422 |
| 10.2 | `GET /api/carriers/3000000000` | 422 |
| 10.3 | `POST /api/occurrences/{id}/close` com id fora de faixa | 422 |

**Por que vale um bloco:** todo id inteiro deste serviço é `int32` no Postgres.
Um valor acima disso chegava ao driver e virava 500 sem tratamento. A correção
foi tipada num alias único, e no primeiro dia ele revelou um nono ponto que a
revisão não tinha listado.

---

## Evidência no banco

Três consultas que provam o que a tela não mostra:

```sql
-- A trilha de auditoria existe e tem autor
SELECT ea.criado_em, ea.quantidade_anterior, ea.quantidade_nova, ea.motivo
FROM estoque_ajustes ea ORDER BY ea.criado_em DESC LIMIT 5;

-- Nenhum produto ficou órfão de fornecedor
SELECT count(*) FROM estoque WHERE fornecedor_id IS NULL;   -- 0

-- A revision da spec B está aplicada
SELECT version_num FROM alembic_version;                    -- b1a2c3d4e5f6
```

## Repetir o plano

O seed é idempotente em duas passadas: rodar `make services-seed` de novo não
duplica parceiro, produto nem linha de estoque, e a segunda passada relata zero
inserções. Para uma passada limpa de verdade, derrube os volumes e refaça o
runbook — mas note que isso apaga os pedidos criados na passada anterior, e os
blocos 4 e 6 dependem de pedido antigo existir.

## O que não é bug

A lista completa está na §10 de
[`back-end/partners-inventory-carriers.md`](back-end/partners-inventory-carriers.md).
As que mais aparecem num smoke test:

- **O fornecedor `Edu` aparece como inativo no banco.** É intencional: `Edu` é o
  fornecedor da própria loja, não uma vitrine. Ele continua ancorando a origem
  dos pedidos; a seção de parceiros do app deve listar **um** elemento.
- **A grade principal do app mostra também os produtos do parceiro.** A listagem
  sem filtro não separa origem; a separação é a seção de parceiros.
- **`GET /api/products/{id}` devolve 200 para produto inativo.** O painel lê essa
  rota para reativar — 404 quebraria o único jeito de desfazer uma desativação.
  O botão de adicionar é que recusa.
- **As contagens de categoria incluem produto inativo.** Imprecisão de exibição
  numa tela onde ninguém compra.
- **As listagens têm teto de 100 no servidor.** Acima disso, a exportação CSV de
  transportadoras e o filtro de transportadora nas ocorrências truncam.
- **O painel de "PARCEIROS ATIVOS" mostra 1.** Conta vitrines, e uma é a
  resposta certa.
- **`flutter analyze` sai com código 1 e sete avisos `info`.** É o baseline medido
  do repositório, nenhum deles em arquivo tocado por esta entrega.

## Critério de aprovação

A spec B passa quando os dez blocos passam **e** as três consultas de evidência
batem. Um bloco falho não invalida os outros — anote qual, com a resposta
recebida, e siga; a triagem do [`smoke-test.md`](smoke-test.md) vale aqui
também.

Dois resultados são bloqueadores, e não simples falhas de bloco: qualquer **500**
em qualquer passo, e qualquer divergência no bloco 4 — origem que se move
depois do pedido criado corrompe registro histórico, e a spec C será construída
em cima dele.
