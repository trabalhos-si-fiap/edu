# Registro de execução do smoke test — specs B e C

**Data:** 2026-09-10. **Árvore medida:** `main` em `23dacb9` (merge da spec C).

**O que este documento é:** o resultado medido de rodar os planos
[`smoke-test-spec-b.md`](smoke-test-spec-b.md) e
[`smoke-test-spec-c.md`](smoke-test-spec-c.md) até onde eles podem ser rodados
sem aparelho e sem operador humano. Não substitui nenhum dos dois: substitui a
frase "ainda não rodamos o smoke" por uma lista de o que passou, o que não foi
exercitado, e por quê.

**Placar:** 123 conferências executadas — 50 da spec B, 73 da spec C —, todas
passaram. Nenhum 500 em nenhuma rota, em nenhum momento. Nenhuma senha de carregamento em log, em rota ou em
notificação. Os três resultados bloqueadores da spec C e os dois da spec B não
apareceram.

---

## 1. Por que isto não rodou contra o stack em execução

O stack do desenvolvedor estava de pé durante a medição, e **não** serve para
este smoke test. Três fatos medidos, não inferidos:

| Fato | Como foi medido | Consequência |
|---|---|---|
| As imagens são anteriores à spec C | `curl localhost:8103/openapi.json` não lista **nenhuma** rota `/shipments` | Todo o bloco 2, 3, 4 e 10 da spec C responderia 404 |
| `commerce_db` está duas revisions atrás do head | `select version_num from alembic_version` devolve `c90210e9965c`; o head é `c1d2e3f4a5b6` | Nem a spec B (`b1a2c3d4e5f6`) nem a spec C estão aplicadas: sem `carregamentos`, sem `posicao_entrega`, sem trilha de estoque |
| `notification_db` não tem a tabela `staff` | `\dt` lista só `alembic_version`, `device_tokens`, `notificacoes` | Todo push de staff sumiria calado — o modo de falha que o bloco 7 existe para pegar |

Nada disso foi corrigido aqui: mexer nas imagens e nos bancos de
desenvolvimento do usuário está fora do que este agente pode fazer. Para rodar
a parte manual (aparelho e painel), o runbook é o de sempre, na ordem:

```bash
make stack-rebuild && make stack-up && make services-migrate && make services-seed
DEMO_ACCOUNTS_PASSWORD='...' make services-seed-demo    # P1 da spec C: popula `staff`
```

## 2. O ambiente em que rodou

Ambiente descartável, montado ao lado do stack do usuário sem tocá-lo:

- **Bancos:** `smoke_auth`, `smoke_commerce`, `smoke_notification`, criados no
  Postgres existente e apagados no fim. `alembic upgrade head` nos três, a
  partir do zero — as três cadeias sobem limpas, incluindo `b1a2c3d4e5f6`,
  `c1d2e3f4a5b6` e `d4c5b6a7e8f9`.
- **Infra:** RabbitMQ e Redis próprios, em contêineres nomeados
  `smoke-specbc-*`, em portas livres (5674, 6381).
- **Serviços:** `api-gateway` (8200), `auth-users-service` (8201),
  `commerce-service` (8203), `notification-service` (8205), rodando o código
  de `main` via `uv run granian`, com as variáveis de ambiente apontando para a
  infra descartável.
- **Seed:** catálogo e parceiros (6 produtos próprios, 2 parceiros, 4 produtos
  de parceiro, 10 linhas de estoque) e as quatro contas de demonstração.
- **Chave do Maps:** ausente de propósito — é o estado padrão, e é o lado
  degradado do bloco 5.

Consequência para a leitura: tudo abaixo mede o **backend** e os contratos que
o aplicativo consome. O que depende de tela, de aparelho ou de olho humano está
na §5.

## 3. Spec B — resultado por bloco

| Bloco | Conferências executadas | Resultado |
|---|---|---|
| 1. Origem única do carrinho | 1.1, 1.2, 1.3, 1.4 | Passa. A frase do 409 é byte a byte a do plano, nas duas ordens de adição |
| 2. Estoque auditado | 2.2 (as duas portas), 2.3, 2.4, 2.5 | Passa. A porta absoluta e a de delta gravam a mesma trilha; estoque negativo recusado nas duas sem gravar linha de auditoria |
| 3. Produto inativo | 3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 | Passa. Inclui 3.4: produto desativado sai da lista de substitutos sugeridos |
| 4. Origem congelada no pedido | 4.1, 4.2, 4.3 | Passa. Editar a origem do parceiro **não** move a origem do pedido já criado |
| 5. Ocorrência de transportadora × separação | 5.1, 5.2, 5.2b, 5.3, 5.4 | Passa. Os dois defeitos que a revisão final da spec B achou continuam corrigidos: `finish` com ocorrência de transportadora dá 200, e duas ocorrências abertas dão 400, não 500 |
| 6. Recompra entre parceiros | 6.1 | Passa. 409 com a frase do bloco 1 |
| 7. Códigos de pagamento | 7.2, 7.3, 7.4, 7.5, 7.6 | Passa. PIX determinístico, boleto no formato da linha digitável, cartão sem código, pedido alheio 404, cliente sem gerador próprio |
| 8. Catálogo por parceiro | 8.1, 8.3, 8.4 | Passa. Parceiro inativo devolve lista vazia; id fora de faixa devolve 422 |
| 9. O painel no gateway | 9.2, 9.4, 9.5 (com volume), 9.6, 9.7, 9.8 — pelo lado do servidor | Parcial — a tela em si está na §5. As seis listagens do painel populam; sku repetido devolve a mensagem do servidor; transportadora criar/editar/status preserva `rating` e `sla_percentage`; não existe rota de reabrir ocorrência. **9.5 com volume:** com 110 linhas de estoque o servidor entrega no máximo 100 por página e a segunda página completa o total — que é o que o painel soma para não repetir o defeito do contador que mentia |
| 10. Identificadores fora de faixa | 10.1, 10.2, 10.3 | Passa. 422 nos três, nunca 500 |

**Evidência no banco (as três consultas do plano):** `estoque_ajustes` tem
linha com autor; `select count(*) from estoque where fornecedor_id is null`
devolve 0; `alembic_version` está em `c1d2e3f4a5b6` (spec B aplicada e
ultrapassada pela spec C).

## 4. Spec C — resultado por bloco

| Bloco | Conferências executadas | Resultado |
|---|---|---|
| 1. Desvio de substituição | 1.1, 1.2, 1.3, 1.5, 1.6, 1.7, 1.8, 1.9 | Passa. **1.3 é o teste do defeito crítico da entrega:** uma notificação por falta de estoque, não duas, e ela carrega `occurrence_id` — a chave que a tela do aluno lê |
| 2. Credencial do carregamento | 2.1 a 2.8 | Passa. Código de 8, senha de 12, listagem e detalhe sem senha nem hash, `sub` do token igual ao id do lote, primeiro acesso congelado. **O passo 2.5 tem número:** mediana de 5 tentativas, 240 ms para o código que existe contra 238 ms para o que não existe — o bcrypt descartável está sendo gasto, e a rota não é oráculo de quais lotes existem |
| 3. Escopo do token de lote | 3.1 a 3.6, 3.9 (servidor), mais uma varredura | Passa. Fila só do lote, coleta e entrega 200, pedido de outro lote 403, `/picking/queue` 403, `/orders` 403, `/notifications` 403. Além dos passos do plano, o token de lote foi jogado contra **as 28 rotas GET do commerce-service** e contra **as quatro do notification-service**: nenhum 500 em nenhuma — é a prova de que a correção do `sub` não-UUID vale para a frota, não só para as seis rotas que o plano lista |
| 4. Um carregamento, uma origem | 4.1 a 4.6 | Passa. Inclui 4.6, o caso do pedido sem origem que o sentinela original não pegava |
| 5. Posição | 5.1, 5.3, 5.4, 5.5, 5.6 | Passa. Sem chave: coleta 200 e posição nula para sempre. Com destino congelado: 4 pontos gravados em 30 s, sempre entre origem e destino, e o percurso para no destino depois dos 6 minutos |
| 6. Avanço automático | 6.1, 6.2, 6.3, 6.4, 6.5, 6.5b, 6.6 | Passa. Ver detalhe abaixo |
| 7. Push no perfil certo | 7.1 a 7.7 | Passa. Inclui 7.3 (`CONFIRMADO` não notifica ninguém) e 7.7 (com `staff` vazia o aluno **ainda** recebe) |
| 8. E-mail da credencial | 8.1, 8.3, 8.4 | Passa. Ver detalhe abaixo. 8.2 (envio real) não foi executado — §5 |
| 9. Múltiplas sessões | — | Não executável sem aparelho — §5 |
| 10. Admin nas duas telas | Contratos de 10.1–10.3 pelo lado do servidor | Parcial — §5 |

**Bloco 6, detalhe.** Com `AVANCO_AUTOMATICO_SEGUNDOS` ausente, o log anuncia
`scheduler: avanço automático desligado (padrão)`. Vinte e um pedidos em cinco
estados diferentes — `CRIADO`, `AGUARDANDO_SEPARACAO`, `EM_SEPARACAO`,
`AGUARDANDO_SUBSTITUICAO`, `AGUARDANDO_COLETA` — ficaram parados 16 minutos e
**nenhum** mudou de estado sozinho, nem saiu da lista. (A comparação bruta
acusa cinco linhas novas: são pedidos criados pelas conferências da spec B que
rodaram durante a janela, não avanços.) É o critério de pronto 6, medido, não
argumentado. Ligando com prazo
de 180 s, o log anuncia `avanço automático LIGADO, prazo de 180s`, os pedidos
parados avançam um passo, o pedido tocado à mão logo antes **não** avança (a
contagem reinicia), e nenhum pedido em `AGUARDANDO_SUBSTITUICAO` se move. Um
pedido em `AGUARDANDO_COLETA` foi para `EM_TRANSITO` pela rede de segurança, e
o log prova que ela chamou o congelamento de destino
(`posicao: sem chave da Google, pedido ... fica sem destino` — a linha só sai
de dentro de `congelar_destino`). Depois disso, o entregador com conta recebeu
403 ao tentar entregar, com `deliverer_id` nulo: a consequência declarada na
§4 do [`back-end/order-flow.md`](back-end/order-flow.md), reproduzida.

**Bloco 8, detalhe.** Em `console`, o log traz exatamente
`email[console]: para=<destinatário> assunto=Carregamento #N — código de
acesso` — destinatário e assunto, nunca corpo nem senha. Com
`EMAIL_BACKEND=resend` e chave inválida, o envio falha alto
(`EmailNaoEnviadoError: provedor recusou o envio (401)`, sem o corpo da
resposta do provedor no log) e a mensagem para na fila
`edu.events.dead` — confirmado com `rabbitmqctl list_queues`: 1 mensagem. A
criação do carregamento continua respondendo 201: o e-mail é consequência, não
pré-requisito. E `notificacoes` não ganha **nenhuma** linha por
`shipment.created`.

**Evidência no banco (as cinco consultas do plano):** `alembic_version` em
`c1d2e3f4a5b6` (commerce) e `d4c5b6a7e8f9` (notification); `carregamentos`
guarda `$2b$12$…` e o nome do primeiro acesso; `posicao_entrega` é série
temporal (4 pontos para um carregamento); `orders` carrega `carregamento_id`,
`carrier_name` real e o destino congelado quando há chave; `staff` tem as três
linhas.

## 5. O que não foi exercitado, e por quê

Nada disto é falha: é a parte do plano que exige um humano, um aparelho ou uma
credencial de terceiro.

| Item | Por que ficou de fora |
|---|---|
| Spec C 1.4, 3.7, 3.8, 9.1–9.4, 10.1–10.2, 10.4 | Exigem o aplicativo rodando num aparelho. O que dava para verificar do lado do código foi verificado: a tela de notificações lê `occurrence_id` (não `ocorrencia_id`), e o botão "Reportar atraso" está atrás de `if (!_sessaoDeLote)` |
| Spec C 3.9 pelo aparelho | O lado do servidor foi medido: token de lote 403, conta do entregador responsável 201 |
| Spec C 5.2, 5.3 com chave real do Maps | Usar a chave do usuário faria chamada externa e gastaria cota dele. O congelamento de destino foi simulado gravando a coordenada que o geocode gravaria, e o simulador foi exercitado a partir dela |
| Spec C 8.2 (e-mail real pelo Resend) | Enviaria e-mail de verdade com a chave do usuário. O caminho de sucesso não foi exercitado; o de falha e o de console foram |
| Spec B blocos 1, 2.1, 3.1, 8.1, 8.2, 9.1–9.4, 9.6, 9.7 | São conferências de tela (aplicativo e painel Angular). O painel compila: `npm run build` sai com código 0 |
| Spec B 4.3 pela tela, 6.1 pela tela | Os contratos foram medidos por HTTP |

Do que depende de tela, o que dava para conferir no código foi conferido e
está de pé: os cards de carregamento têm `key: ValueKey(c.id)` mais a
invalidação em `didUpdateWidget` (o passo 10.4), o seletor de sessão só existe
sob `bool.fromEnvironment('DEMO_MULTI_SESSAO')` e o alvo `make front-demo` que
o liga (o bloco 9), a tela de notificações lê `occurrence_id` (o passo 1.4) e
"Reportar atraso" está atrás de `if (!_sessaoDeLote)` (o passo 3.8). Isso
prova que o código certo está lá; não prova que a tela se comporta como se
espera com um dedo humano nela.

O `flutter test` (205) e as oito suítes de backend (600 no commerce, 58 no
notification, 62/39/74/78/37/34 nas demais) já haviam sido rodados sobre este
mesmo commit no fechamento da branch — é o critério de pronto 7.

## 6. Observações da rodada (nenhuma é defeito)

- **Os seis produtos semeados do catálogo próprio têm `sku` vazio, e
  `PUT /products/{id}` exige `sku` com pelo menos um caractere.** Está
  documentado no `ProductIn` ("o banco tolera o vazio herdado, o validador
  impede um vazio novo"), mas a consequência prática merece ser dita: para
  desativar um desses seis pelo painel, o operador precisa digitar um sku
  primeiro. Produtos de parceiro e produtos criados pelo painel não têm esse
  atrito.
- **A primeira ocorrência de falta de estoque de um processo novo demora ~30 s.**
  O motor de sugestão carrega o modelo de embedding sob demanda. Da segunda em
  diante é instantâneo. Num stack recém-subido, o primeiro separador a reportar
  falta vai esperar; não é travamento.
- **O fornecedor `Edu` aparece inativo**, como a §10 do
  [`partners-inventory-carriers.md`](back-end/partners-inventory-carriers.md)
  descreve. Ele continua ancorando a origem dos pedidos próprios.
- **O seed de demonstração numa base onde as contas já existem cria 0 contas e
  reanuncia as três de staff** — medido: `staff` foi esvaziada de propósito
  para o passo 7.7 e voltou às três linhas com uma segunda passada do seed. É a
  correção que a revisão final da spec C fez, funcionando.

## 7. Blockers

Nenhum. Os cinco resultados que os dois planos classificam como bloqueadores
foram procurados explicitamente e não apareceram:

- **Qualquer 500** — varredura nos logs dos quatro serviços: zero. Os únicos
  dois tracebacks da rodada são os do teste deliberado do bloco 8.3.
- **Senha de carregamento em log, listagem ou notificação** — procurada nos
  logs, nas rotas de listagem e detalhe, e na tabela `notificacoes`: ausente
  nas três.
- **Divergência no bloco 4 da spec B** (origem que se move depois do pedido) —
  não ocorre.
- **Divergência no bloco 4 da spec C** (origem do lote que se move) — não
  ocorre, inclusive no caso do pedido sem origem.

## 8. Como refazer

Os scripts da rodada ficaram no diretório de trabalho da sessão, não no
repositório: são um andaime, não um artefato. Refazer é montar o mesmo
ambiente descartável (§2) e repetir as chamadas descritas nos dois planos. Para
a parte que falta — aparelho, painel, Maps, Resend — o caminho é o runbook da
§1 seguido dos dois planos, na mão.
