# Percurso de estudo, pontuação e nível — o que a spec D trocou

> **Escopo:** entrega da spec D (2026-09-10) — tirar das telas do aluno os
> números fixos que existiam desde antes das specs A/B/C e substituí-los por
> um objetivo declarado pelo aluno, um percurso (roadmap) gerado a partir
> dele, e um extrato de pontos que vira nível na leitura. O plano completo
> está em
> `docs/superpowers/plans/2026-09-10-spec-d-onboarding-tracker-gamificacao.md`.

Este documento descreve o sistema como ele está no fim da Task 14, lido do
código — não do plano. Onde os dois divergem, o código venceu e é o código
que está descrito aqui.

---

## 1. O que a spec D trocou

Antes da spec D, duas telas do Flutter desenhavam cinco valores escritos no
próprio código Dart, iguais para qualquer aluno logado. Os cinco (arquivo e
linha de onde saíram, medidos no commit imediatamente anterior à remoção de
cada um):

| Valor removido | Onde estava | Campo que passou a alimentá-lo |
|---|---|---|
| Título da meta fixo no código | `front-end-flutter/lib/features/home/presentation/home_screen.dart:163` (commit `db6c88e^`) | `GET /profile/summary` → `objetivo.titulo` |
| Um par de dias fixo no código | `front-end-flutter/lib/features/home/presentation/home_screen.dart:170` (commit `db6c88e^`) | `GET /profile/summary` → `objetivo.dias_decorridos` / `objetivo.dias_totais` |
| Barra de progresso parada num valor fixo (e o texto de porcentagem que o acompanhava, na mesma tela) | `front-end-flutter/lib/features/home/presentation/home_screen.dart:183` e `:140` (commit `db6c88e^`) | `GET /profile/summary` → `roadmap.progresso` |
| Total de pontos fixo no código | `front-end-flutter/lib/features/profile/presentation/profile_screen.dart:214` (commit `5196e93^`) | `GET /profile/summary` → `pontos.total` |
| Contagem de "Testes" fixa no código | `front-end-flutter/lib/features/profile/presentation/profile_screen.dart:258` (commit `5196e93^`) | `GET /profile/summary` → `estudo.questoes_respondidas` (o rótulo também mudou, de "Testes" para "Questões", porque é isso que o campo conta) |

Os números em si não são reproduzidos aqui — o critério de pronto 1 da spec
(`grep -rn` por eles em `front-end-flutter/lib`) tem que continuar vazio, e
copiar um deles de volta para dentro de `docs/` seria abrir a porta para um
copiar-colar futuro reintroduzi-lo em `lib/`.

Um sexto valor fixo existia na mesma leva (uma contagem de horas de estudo,
na segunda linha de estatísticas do perfil) mas não foi substituído por um
campo equivalente — não existe, em lugar nenhum do backend, uma medida de
horas estudadas. A caixa que o exibia passou a mostrar a sequência de
acertos (`pontos.streak`) em vez disso; é uma troca de métrica, não um
número real ocupando o lugar de um inventado.

A tela de onboarding (`front-end-flutter/lib/features/onboarding/presentation/onboarding_screen.dart`)
e as três rotas do backend (`app/routers/onboarding.py`, `roadmap.py`,
`perfil.py`, todos em `back-end/learning-service`) são o que ficou no lugar
dos cinco valores. As seções abaixo descrevem cada peça.

---

## 2. Objetivo e onboarding

Três rotas, todas em `back-end/learning-service/app/routers/onboarding.py`,
prefixo `/onboarding` (roteado pelo gateway em `back-end/api-gateway/app/routing.py:19`):

- **`GET /onboarding`** — devolve o objetivo do aluno autenticado, ou
  `null`. `null` não é erro: é o estado de quem ainda não preencheu ou
  pulou, e um 404 aqui faria a tela tratar "não preencheu ainda" como
  falha.
- **`POST /onboarding`** — cria o objetivo (`titulo`, `data_alvo`) e, na
  mesma transação, gera o roadmap inteiro (`gerar_roadmap`, seção 3).
  Responde `201` com o objetivo salvo, quantas etapas o percurso ganhou
  (`etapas_geradas`) e se o prazo ficou apertado (`prazo_apertado`). Um
  segundo `POST` do mesmo aluno colide com `uq_objetivo_aluno` e vira `409`
  — o cliente já sabe, a partir daí, que o caminho certo é o `PUT`.
- **`PUT /onboarding`** — altera o objetivo existente (`404` se não houver
  nenhum). Regenera o roadmap **só quando a data muda**; trocar apenas o
  título não apaga e recria as etapas, porque o resultado seria idêntico.

**A regra da data no passado** está no schema Pydantic
(`app/schemas/objetivo.py`, `ObjetivoIn._data_nao_pode_estar_no_passado`),
não numa tela: `data_alvo < date.today()` é rejeitado com `422` antes de
tocar o banco. A validação mora no schema porque há duas portas de entrada
(o `POST` do onboarding e o `PUT` do perfil) e uma regra que vivesse só no
cliente Flutter não protegeria a segunda.

**O que acontece quando o aluno pula:** a tela de onboarding tem um botão
"Pular por enquanto" que não chama nenhuma rota — ele só navega para
`/home` (`onboarding_screen.dart::_pular`). Nada é gravado. Um aluno sem
objetivo é um caso previsto em todo o resto do sistema: `GET /roadmap`
devolve uma lista vazia com um motivo explicativo (seção 3), e o
`GoalCard` da tela inicial simplesmente não desenha nada nesse caso —
`GoalCard.build` (`goal_card.dart`) checa `summary.goal == null` e devolve
`SizedBox.shrink()` antes de montar qualquer texto ou barra.

A tela de onboarding é alcançada por duas portas: logo depois do cadastro
(`register_screen.dart:76`) e pelo item "Metas e objetivos" do perfil
(`profile_screen.dart:105`, rota `/onboarding`) — que antes da spec D não
levava a lugar nenhum. Com objetivo já cadastrado, a tela abre preenchida
com os dados de `GET /onboarding` e salva com `PUT` em vez de `POST`.

---

## 3. O roadmap

`GET /roadmap` (`app/routers/roadmap.py`, paginado com `limit`/`offset`)
lista as etapas do percurso do aluno autenticado, cada uma com o subtema,
o caminho até ele (matéria → tema → subtema), o prazo, se está concluída e
se tem questão semeada. Sem objetivo, a resposta vem com `items: []` e
`motivo` preenchido com o convite a fazer o onboarding.

A geração (`gerar_roadmap`, `app/services/roadmap.py`, chamada pelo `POST`
e, condicionalmente, pelo `PUT` de `/onboarding`) segue quatro passos, na
ordem em que o serviço os aplica:

1. **Matérias na ordem do seed** — pela ordem crescente de `Materia.id`.
2. **Temas e subtemas dentro de cada matéria, por `.ordem`** — com o `.id`
   como critério de desempate, porque `.ordem` tem valor padrão `0` e não é
   única (a mesma correção que já existia em `routers/materias.py`).
3. **Prazos distribuídos entre hoje e a data-alvo** — a fórmula
   (`distribuir_prazos`) espalha as `N` etapas assim: sejam `dias` o número
   de dias entre hoje e a data-alvo; a etapa de índice `i` (contando de
   zero) recebe o prazo `hoje + ⌊(i × dias) / (N − 1)⌋` dias, de modo que a
   primeira etapa (`i = 0`) vence hoje e a última (`i = N − 1`) vence
   exatamente na data-alvo. Quando `N = 1`, a única etapa recebe a própria
   data-alvo. Quando há mais etapas que dias disponíveis, vários prazos
   caem no mesmo dia — a função nunca recusa a geração por prazo curto,
   ela agrupa; recusar impediria um aluno de montar um percurso para a
   prova da semana seguinte. `prazo_apertado(quantidade, inicio, data_alvo)`
   é o sinalizador que informa esse caso à tela (verdadeiro quando não há
   um dia inteiro disponível por etapa), devolvido junto com o objetivo
   salvo e com o roadmap.
4. **Subtema já dominado nasce concluído** — um subtema cujo
   `AlunoTemaProgresso.nivel_dominio` já é `>= 0.7` (`LIMIAR_DOMINIO_SUBTEMA`,
   `app/services/decisao.py`) entra no roadmap com `concluida_em` já
   preenchido, sem exigir uma resposta nova para "destravar" o que o
   aluno já sabia antes de declarar o objetivo.

**Regeneração** (quando o `PUT` muda a data-alvo) é **apagar e recriar**,
não um `UPDATE` etapa a etapa: `gerar_roadmap` lê as conclusões
(`concluida_em`) de todas as etapas existentes do aluno, apaga a tabela
inteira para aquele `aluno_id` e reinsere, preenchendo `concluida_em` nas
etapas cujo subtema já estava concluído na leitura anterior (ou que se
tornou dominado nesse meio-tempo). Etapa a etapa teria que lidar
separadamente com "subtema sumiu do seed" e "subtema é novo" — dois
caminhos a mais para manter certos, contra um apagar-e-reinserir que trata
os dois igual. A constraint `uq_etapa_aluno_subtema` é o que torna isso
seguro: nenhuma passagem cria duas etapas do mesmo subtema para o mesmo
aluno.

**`tem_questoes`** (campo de `EtapaOut`, em `GET /roadmap`) é `false` quando
o subtema da etapa ainda não tem nenhuma linha em `questao`. A etapa
continua aparecendo no percurso — esconder a matéria mentiria sobre o
tamanho do percurso — mas o Flutter (`RoadmapStep.hasQuestions`) desabilita
o botão de praticar e mostra o motivo. A checagem é uma única consulta
agregada por página (`Questao.subtema_id IN (...)`, agrupada), não uma
consulta por etapa — com as 99 linhas de subtema que o seed do ENEM cria
(seção 6), o caminho ingênuo seria uma viagem ao banco por etapa só para
desenhar uma tela.

---

## 4. A pontuação

Toda regra de pontuação vive em
`back-end/learning-service/app/services/pontuacao.py`, e só ali. Quatro
origens lançam pontos, todas passando pela mesma função `registrar`:

| Origem (`LancamentoPontos.origem`) | Quando | Pontos | Quem lança |
|---|---|---|---|
| `questao` | Uma questão respondida corretamente em `POST /diagnostic/answer` | 10 (`PONTOS_QUESTAO_CORRETA`) | `app/routers/diagnostico.py` |
| `revisao` | Uma revisão que já estava vencida (SM-2) quando o aluno respondeu ao subtema | 15 (`PONTOS_REVISAO_NO_PRAZO`) | `app/routers/diagnostico.py` |
| `etapa` | Uma etapa do roadmap muda de "não concluída" para "concluída" (domínio do subtema cruza o limiar de 0.7) | 50 (`PONTOS_ETAPA_CONCLUIDA`) | `app/routers/diagnostico.py`, via `concluir_etapa` |
| `streak` | A sequência de acertos em um subtema cresce nesta resposta | `5 × sequência`, com teto de 50 (`bonus_streak`) | `app/routers/diagnostico.py` |

**Não existe rota que conclui uma revisão.** `GET /reviews/today`
(`app/routers/revisao.py`) só lista as revisões vencidas — não há
`POST`/`PATCH` que as marque como feitas. É responder a uma questão do
subtema, em `POST /diagnostic/answer`, o ato que fecha a revisão: o
handler lê `AlunoTemaProgresso.proxima_revisao` **antes** de sobrescrevê-la
com o novo cálculo do SM-2, e se essa data vencida já tinha passado quando
a resposta chegou, lança os 15 pontos de `revisao` ali mesmo. Quem procurar
por um endpoint de "concluir revisão" não vai achar um — a conclusão é
efeito colateral de responder, por decisão explícita registrada no
plano da spec (decisão D1).

**A chave de idempotência** é a constraint única
`uq_lancamento_idempotente` sobre `(aluno_id, origem, referencia)`, em
`LancamentoPontos`. `registrar` grava com
`INSERT ... ON CONFLICT DO NOTHING`, nunca um `SELECT` seguido de decisão
em Python — duas respostas simultâneas para a mesma questão leriam as duas
"não existe" e gravariam as duas se a decisão fosse em Python; com o
índice único dentro do banco, só uma sobrevive. A referência muda por
origem: `str(questao_id)` para `questao`, `str(subtema_id)` para `etapa`,
`f"{subtema_id}:{novo_streak}"` para `streak` (cada degrau da sequência paga
uma vez), e `f"{subtema_id}:{data_da_revisao_vencida.isoformat()}"` para
`revisao` — essa última carrega a data da revisão vencida para que a
revisão de amanhã pontue de novo e a de hoje não pontue duas vezes.

**A ordem em que os pontos de questão correta são gravados importa.** Em
`POST /diagnostic/answer`, o lançamento de `questao` acontece **depois**
do laço por subtema, em ordem **crescente de `questao_id`** — não na ordem
em que o cliente mandou as respostas. As duas coisas evitam o mesmo
problema: duas submissões concorrentes do mesmo aluno cobrindo as mesmas
questões em ordens diferentes adquiririam as chaves do índice único
`uq_lancamento_idempotente` em ordens opostas, o que é a receita de um
deadlock no Postgres. Ordenar por `questao_id` antes de gravar dá a toda
requisição a mesma ordem de aquisição, o que elimina o ciclo. O comentário
que explica isso está em `app/routers/diagnostico.py`, logo antes do laço
`for questao_id in sorted(questoes_corretas)`.

**As faixas de nível** (`FAIXAS_NIVEL` em `pontuacao.py`) são uma tupla de
dez mínimos: `(0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500)`. O
nível é o índice do maior mínimo que o total ainda alcança, mais um — 0
pontos é nível 1, 4500+ é nível 10 (o teto). `nivel_do_total` recebe o
total já somado e devolve o nível na hora.

**Nível não é gravado em lugar nenhum.** Não existe coluna `nivel` em
tabela alguma; `nivel_do_total(total)` é chamado toda vez que
`GET /profile/summary` monta a resposta, a partir da soma do extrato
(`total_de_pontos`). Mudar as faixas depois é editar uma tupla em
`pontuacao.py`, não migrar dado nenhum.

---

## 5. O resumo

`GET /profile/summary` (`app/routers/perfil.py`) é a única chamada que a
tela inicial e o perfil fazem para desenhar todos os números desta
entrega. Cada campo tem uma origem única, verificável, e nenhum é derivado
de outro campo da mesma resposta:

```json
{
  "objetivo": {
    "titulo": "string",
    "data_alvo": "AAAA-MM-DD",
    "dias_decorridos": 0,
    "dias_totais": 0
  },
  "roadmap": {
    "etapas_totais": 0,
    "etapas_concluidas": 0,
    "progresso": 0.0
  },
  "pontos": {
    "total": 0,
    "nivel": 1,
    "streak": 0
  },
  "estudo": {
    "questoes_respondidas": 0,
    "subtemas_iniciados": 0
  }
}
```

- **`objetivo`** — `null` quando o aluno não tem objetivo (a tela inicial
  não desenha o `GoalCard` nesse caso). Quando existe:
  - `titulo`, `data_alvo` — colunas de `ObjetivoAluno`, sem transformação.
  - `dias_totais` — dias entre a criação do objetivo (`criado_em.date()`)
    e `data_alvo`, nunca negativo (`max(..., 0)`).
  - `dias_decorridos` — dias entre a criação e hoje, limitado por cima a
    `dias_totais` (`min`) e por baixo a zero (`max`): um objetivo cuja
    data-alvo já passou mostra o percurso cheio, não um numerador maior
    que o denominador.
- **`roadmap`** — `etapas_totais` e `etapas_concluidas` vêm de uma única
  agregação (`func.count()` e `func.count(EtapaRoadmap.concluida_em)`)
  sobre as etapas do aluno; `progresso` é `etapas_concluidas / etapas_totais`,
  arredondado a 4 casas, e `0.0` quando `etapas_totais` é zero (sem
  objetivo, ou objetivo cujo roadmap ainda não terminou de gerar). É este
  campo que hoje alimenta a barra que antes ficava parada em um valor
  fixo, na tela inicial.
- **`pontos`** — `total` é `total_de_pontos` (soma de `LancamentoPontos`,
  seção 4); `nivel` é `nivel_do_total(total)`, calculado na resposta, não
  lido de coluna nenhuma; `streak` é o maior `AlunoTemaProgresso.streak_acertos`
  entre os subtemas do aluno (`func.max`), não o bônus de pontos em si —
  é a sequência de acertos consecutivos mais alta que o aluno tem hoje em
  qualquer subtema.
- **`estudo`** — `questoes_respondidas` é a soma de
  `AlunoTemaProgresso.total_respondidas` entre todos os subtemas
  (`func.sum`, com `coalesce` para zero); `subtemas_iniciados` é a
  contagem de linhas de `AlunoTemaProgresso` do aluno (`func.count()`) —
  um subtema só ganha linha na primeira resposta que o aluno dá nele.

Um aluno sem nenhuma atividade (zero respostas, zero objetivo) recebe
`objetivo: null`, `roadmap` com os três campos zerados, `pontos` com
`total: 0`, `nivel: 1`, `streak: 0`, e `estudo` com os dois campos
zerados — nunca um valor de exemplo. O Flutter trata a ausência de campo
da mesma forma (`_asInt`/`_asDouble` em `study_summary.dart` devolvem zero
para o que não vier, em vez de lançar exceção e deixar a tela sem
desenhar nada).

---

## 6. O que ainda não existe

**Conteúdo — matérias sem questão.** O seed que a spec D adiciona
(`back-end/learning-service/scripts/seed_enem.sql`) cria só **estrutura**:
11 matérias, 33 temas (3 por matéria), 99 subtemas (3 por tema) — cobrindo
as quatro áreas do ENEM — e **nenhuma questão**. A única fonte de questões
no repositório é `back-end/learning-service/scripts/seed_biologia_citologia.sql`,
que antecede a spec D: **26 questões**, nos subtemas de id 1 a 8, dentro
dos temas "Introdução ao Estudo da Célula", "Citologia" e "Genética
Básica" (temas 1, 2 e 3), todos sob a matéria "Biologia" (id 1) — a mesma
linha de `materia` que `seed_enem.sql` reaproveita em vez de duplicar (ver
o comentário de faixas de id no topo do arquivo). As outras dez matérias
do seed do ENEM (Física, Química, Matemática, Português, Literatura,
Inglês, História, Geografia, Filosofia, Sociologia) não têm questão
nenhuma hoje; todo subtema delas aparece no roadmap com `tem_questoes:
false`.

A lista exata de matérias com e sem questão, com a contagem por matéria,
é a query que a Task 15 não pôde rodar (o ambiente de execução deste
documento proíbe tocar bancos) — rode-a contra o banco do
learning-service para conferir o estado real:

```sql
SELECT m.nome, count(q.id)
FROM materia m
LEFT JOIN tema t ON t.materia_id = m.id
LEFT JOIN subtema s ON s.tema_id = t.id
LEFT JOIN questao q ON q.subtema_id = s.id
GROUP BY m.nome
ORDER BY 2 DESC;
```

Pelo que o seed grava, o resultado esperado é "Biologia" com 26 e as
outras dez matérias com 0 — mas isso é o que o código faz nascer no banco,
não uma medição contra um banco real.

**Fora de escopo, de propósito.** Três coisas que a spec D deliberadamente
não construiu, e que não aparecem em nenhum router, service ou model deste
módulo (conferido com busca por `ranking`, `conquista`, `achievement` e
`leaderboard` em `app/` e em `front-end-flutter/lib/features/tracker` e
`.../onboarding` — nenhuma ocorrência fora de uma mensagem de erro sem
relação, "o que você quer conquistar"):

- **Distribuição adaptativa do roadmap** — a geração de hoje é a ordem fixa
  do seed (matéria → tema → subtema) com prazos espalhados linearmente
  entre hoje e a data-alvo (seção 3). Não há nada que reordene etapas por
  desempenho, dificuldade ou tempo de estudo. O próprio código já é escrito
  para essa substituição ser local: `gerar_roadmap` é a única função que
  quem chama conhece (`app/services/roadmap.py`, docstring do módulo).
- **Ranking entre alunos** — o extrato de pontos (`LancamentoPontos`) é
  particionado por `aluno_id` em toda consulta; não existe rota, índice ou
  agregação que compare o total de um aluno ao de outro.
- **Conquistas / badges** — não há tabela, campo ou rota para marcos que não
  sejam os já descritos (etapa concluída, revisão em dia, sequência de
  acertos). O que a seção 4 lista é a pontuação inteira que existe.

---

## Critério de pronto 6 — as suítes

Os quatro comandos abaixo foram executados na árvore em
`feat/spec-d-onboarding-tracker-gamificacao`, ao final da Task 14, e o
resultado é o que segue (não estimado):

```bash
# os quatro valores fixos descritos na seção 1, procurados em front-end-flutter/lib
$ grep -rn "<padrão da seção 1>" front-end-flutter/lib
# (sem saída — nenhuma ocorrência)

$ cd back-end/learning-service && uv run pytest -q
164 passed in 2.70s

$ cd back-end/api-gateway && uv run pytest -q
41 passed in 0.10s

$ cd front-end-flutter && flutter test
00:24 +243: All tests passed!

$ flutter analyze lib/
6 issues found. (ran in 1.1s)
```

Os seis achados de `flutter analyze lib/` não têm relação com a spec D:
`lib/features/admin/presentation/widgets/admin_scaffold.dart:42` (duas
ocorrências de `unnecessary_underscores`), `lib/features/admin/presentation/widgets/admin_widgets.dart:166`
e `lib/features/logistics/data/logistics_api.dart:288`
(`use_null_aware_elements`), e duas depreciações de API do Flutter em
`lib/features/marketplace/presentation/incident_resolution_screen.dart:275-276`
(`groupValue`/`onChanged` do `Radio`, substituídos por `RadioGroup` a
partir do Flutter 3.32).

Os critérios de pronto 2 a 5 da spec (onboarding ponta a ponta, resposta
movendo o progresso, perfil zerado para conta nova, matéria sem questão
marcada na tela) exigem stack de pé e aparelho — não fazem parte deste
documento; entram no plano de smoke test.
