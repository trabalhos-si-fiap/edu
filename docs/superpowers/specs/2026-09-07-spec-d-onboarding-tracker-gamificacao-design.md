# Spec D — Estudante: onboarding, study tracker e gamificação — Design

**Data:** 2026-09-07
**Status:** Aprovado para planejamento
**Módulos:** `back-end/learning-service/`, `front-end-flutter/lib/features/{home,profile,quiz}/`
**Depende de:** spec A (o corte). Paralela à spec B.

## Objetivo

Remover todo dado inventado das telas do estudante e dar a elas uma fonte real.

Hoje a tela inicial anuncia "Meta: Medicina USP" e "124/200 dias" para qualquer
aluno, e o perfil mostra 3.120 pontos e 15 testes fixos no código. Esta spec
substitui os quatro por dados do backend, e para isso constrói o que ainda não
existe: onboarding com objetivo e prazo, roadmap de estudo até a data-alvo, e
uma regra de pontuação derivada do progresso real.

## Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Fronteira do "sem mocks" | Nada inventado na tela. Todo número exibido vem do backend. |
| Pontos e nível | Viram regra de verdade no `learning-service`, agora. |
| Estrutura do ENEM | Seed real de matérias, temas e subtemas. |
| Questões | Populadas onde der. Matéria sem questão é dito na tela, não escondido. |
| Distribuição do roadmap | Regra explícita e simples. Sem otimização adaptativa. |
| Onde vive o objetivo | `learning-service`. É insumo de estudo, não dado de identidade. |

## Contexto do código existente

### A base do tracker já existe

`learning-service` tem a hierarquia completa em `app/models/subtema.py`:

```python
class Materia:  id, nome
class Tema:     id, materia_id, nome, ordem
class Subtema:  id, tema_id, nome, ordem,
                videoaula_base_url, videoaula_revisao_url, descricao_ia
```

`ordem` em `Tema` e `Subtema` é exatamente o que um roadmap precisa para
sequenciar conteúdo — não é preciso inventar ordenação.

O progresso por aluno já é registrado em `app/models/progresso.py`:

```python
class AlunoTemaProgresso:
    aluno_id, subtema_id, nivel_dominio, intervalo_dias,
    streak_acertos, ultima_revisao, proxima_revisao, total_respondidas
    UniqueConstraint("aluno_id", "subtema_id")
```

Isso já responde três das quatro perguntas que as telas fazem: quantos
exercícios o aluno respondeu, qual a sequência de acertos e quanto ele domina
cada subtema. Só pontuação não tem fonte.

Rotas prontas: `/subjects`, `/subjects/{id}/topics`, `/topics/{id}/subtopics`,
`/topics/{id}/quiz`, `/subtopics/{id}/questions`, `/diagnostic/answer`,
`/recommendations`, `/reviews/today`. Serviços prontos: `sm2.py`,
`embeddings.py`, `classificacao_ia.py`, `recomendacao_semantica.py`, e o
`scheduler.py` que varre revisões vencidas e publica `revision.scheduled`.

### O que não existe

- Qualquer noção de objetivo ou data-alvo do aluno.
- Roadmap: um plano ordenado de subtemas com prazo.
- Pontuação.
- Conteúdo. `scripts/seed_biologia_citologia.sql` é o único seed: uma matéria,
  um tema, um subtema, cerca de 38 questões.

### Os mocks a remover

| Onde | O quê |
|---|---|
| `home_screen.dart:163` | `'Meta: Medicina USP'` |
| `home_screen.dart:170` | `'124/200 dias'` |
| `home_screen.dart` (barra logo abaixo) | `value: 0.68` |
| `profile_screen.dart` (~210) | `'3,120'` pontos |
| `profile_screen.dart` (~254) | `'15'` testes |
| `profile_screen.dart:76` | item "Metas e objetivos" que não navega para lugar nenhum |

## Arquitetura

Nenhum serviço novo. Tudo dentro do `learning-service`, mais as telas.

```
learning-service/app/
  models/
    objetivo.py        # NOVO — objetivo e data-alvo do aluno
    roadmap.py         # NOVO — etapas geradas, com prazo e conclusão
    pontuacao.py       # NOVO — extrato de pontos
  services/
    roadmap.py         # NOVO — distribuição por matéria até a data-alvo
    pontuacao.py       # NOVO — a regra, num lugar só
  routers/
    onboarding.py      # NOVO
    roadmap.py         # NOVO
    perfil.py          # NOVO — o resumo que as telas leem
  scripts/
    seed_enem.sql      # NOVO — matérias, temas, subtemas
front-end-flutter/lib/features/
  onboarding/          # NOVO
  tracker/             # NOVO
  home/, profile/      # passam a ler dados reais
```

### Objetivo

```
ObjetivoAluno
  aluno_id (único), titulo, data_alvo, criado_em, atualizado_em
```

Um objetivo ativo por aluno. `titulo` é texto livre com `max_length` no modelo
e no schema, conforme a regra 4 do `CLAUDE.md`.

O onboarding é um formulário só: objetivo e data. Aparece depois do cadastro e
pode ser reaberto pelo item "Metas e objetivos" do perfil, que hoje não leva a
lugar nenhum. Pode ser pulado — um aluno sem objetivo vê a tela inicial sem o
cartão de meta, e não um cartão com valores de exemplo.

### Roadmap

```
EtapaRoadmap
  aluno_id, subtema_id, ordem, prazo, concluida_em
  UniqueConstraint("aluno_id", "subtema_id")
```

A geração é uma regra explícita, escrita para ser lida:

1. Tomar as matérias do ENEM na ordem do seed.
2. Expandir cada uma nos seus temas e subtemas, respeitando `Tema.ordem` e
   `Subtema.ordem`.
3. Distribuir as etapas uniformemente entre hoje e a data-alvo.
4. Marcar como concluída toda etapa cujo subtema já tenha
   `nivel_dominio` acima do limiar em `AlunoTemaProgresso` — quem já estudou
   não recomeça do zero.

A regra vive em `services/roadmap.py`, isolada de rota e de modelo, e o teste
chama a função direto. Trocá-la por distribuição adaptativa depois é
substituir uma função, não desmontar a tela.

O roadmap é regerado quando a data-alvo muda, preservando as conclusões.

**Matéria sem questão.** O seed cria a estrutura completa do ENEM, mas as
questões só existem onde houver. A etapa aparece no roadmap com a marca de que
o conteúdo ainda não está disponível, e o botão de praticar fica desabilitado
com esse motivo. É a alternativa honesta a esconder a matéria — o aluno vê o
plano inteiro e sabe onde ainda não dá para praticar.

### Pontuação

```
LancamentoPontos
  aluno_id, origem, referencia, pontos, criado_em
```

Extrato, não contador. Um contador incrementado a cada acerto é leitura seguida
de escrita num recurso compartilhado, exatamente o que a regra 3 do `CLAUDE.md`
proíbe; e não permite explicar de onde vieram os pontos.

Regra inicial, em `services/pontuacao.py` e em nenhum outro lugar:

| Origem | Pontos |
|---|---|
| Questão correta | 10 |
| Revisão concluída no prazo | 15 |
| Etapa do roadmap concluída | 50 |
| Bônus por sequência | 5 × `streak_acertos`, limitado a 50 |

Nível é derivado do total, por faixas fixas. Nada é gravado como "nível": ele é
calculado na leitura, então mudar as faixas não exige migrar dado.

O lançamento acontece na mesma transação que registra a resposta, e é
idempotente por `(aluno_id, origem, referencia)` — responder a mesma questão
duas vezes não pontua duas vezes.

### O resumo que as telas leem

`GET /profile/summary` devolve, numa chamada, o que a tela inicial e o perfil
precisam:

```json
{
  "objetivo": { "titulo": "...", "data_alvo": "...",
                "dias_decorridos": 0, "dias_totais": 0 },
  "roadmap":  { "etapas_totais": 0, "etapas_concluidas": 0, "progresso": 0.0 },
  "pontos":   { "total": 0, "nivel": 1, "streak": 0 },
  "estudo":   { "questoes_respondidas": 0, "subtemas_iniciados": 0 }
}
```

Um endpoint agregador para duas telas evita quatro chamadas em série na
abertura do app. Cada campo tem origem única e verificável: `dias_decorridos` e
`dias_totais` vêm do objetivo, `progresso` da contagem de etapas concluídas,
`streak` do maior `streak_acertos` do aluno, `questoes_respondidas` da soma de
`total_respondidas`.

O `0.68` fixo da barra da tela inicial passa a ser `roadmap.progresso`. Sem
objetivo, o cartão inteiro não é desenhado.

### Seed do ENEM

`scripts/seed_enem.sql` cria as matérias, temas e subtemas das quatro áreas do
ENEM, com `ordem` preenchido. Idempotente, no mesmo padrão exigido do seed do
catálogo na spec A.

As questões entram por matéria, em arquivos separados, seguindo o formato do
`seed_biologia_citologia.sql` que já existe. Cada arquivo é uma unidade
independente: a entrega leva as que ficarem prontas, e o roadmap funciona com
qualquer quantidade delas.

## Fluxo de dados

```
Cadastro → onboarding (objetivo + data)
             POST /onboarding
               grava ObjetivoAluno
               gera EtapaRoadmap para todo o período
Tela inicial → GET /profile/summary       (meta, dias, progresso)
Tracker      → GET /roadmap               (etapas, prazos, conclusão)
Praticar     → /topics/{id}/quiz          (rota que já existe)
Responder    → POST /diagnostic/answer
                 atualiza AlunoTemaProgresso  (já faz)
                 lança pontos                 (novo, mesma transação)
                 conclui etapa se o domínio passar do limiar
Perfil       → GET /profile/summary       (pontos, nível, testes)
```

## Tratamento de erros

- Data-alvo no passado: `422`, com mensagem exibível. Validado no schema, não
  na tela.
- Aluno sem objetivo: `200` com `objetivo: null`. Não é erro; a tela desenha
  menos.
- Roadmap pedido sem objetivo: lista vazia, com o motivo no corpo. A tela
  convida a fazer o onboarding.
- Data-alvo tão próxima que a distribuição fica com menos de um dia por etapa:
  aceita, agrupa as etapas restantes no último dia e sinaliza que o prazo é
  apertado. Recusar seria impedir um aluno de estudar para uma prova da semana
  que vem.
- Falha de lançamento de pontos nunca invalida a resposta do aluno: os dois
  estão na mesma transação, então ou ambos gravam ou nenhum grava, e a resposta
  é reenviável sem pontuar duas vezes.

## Testes

- Objetivo: criação, atualização, data no passado recusada, um por aluno.
- Roadmap: cobre todos os subtemas do seed; ordenado por `Tema.ordem` e
  `Subtema.ordem`; distribuído até a data-alvo; regeneração preserva
  conclusões; subtema já dominado nasce concluído.
- Prazo curto: agrupa em vez de falhar.
- Pontuação: cada origem pontua o previsto; teto do bônus respeitado;
  idempotente por referência; nível derivado nas faixas de fronteira.
- Resumo: cada campo afirmado contra dado semeado, não contra outro cálculo.
- Aluno sem objetivo: resumo e roadmap respondem sem erro.
- Seed do ENEM: idempotente em duas passadas; toda matéria tem ao menos um
  subtema.
- Flutter: tela inicial sem objetivo; com objetivo; tracker com etapa sem
  questão; perfil com aluno zerado.

O último é o que fecha o objetivo desta spec: um aluno recém-criado tem que
mostrar zero, não 3.120.

## Critério de pronto

1. Nenhum número inventado nas telas de estudante. Confirmado por
   `grep -rn "3,120\|124/200\|Medicina USP\|0.68" front-end-flutter/lib`
   sem resultado.
2. Aluno novo faz onboarding e vê o roadmap gerado.
3. Responder questão move progresso, pontos e etapa do roadmap.
4. O perfil de um aluno zerado mostra zero.
5. Matérias sem questão aparecem no roadmap, marcadas.
6. `make services-test`, `make front-analyze` e `make front-test` verdes.

## Fora de escopo

- Distribuição adaptativa por desempenho. A regra é explícita e simples, por
  decisão.
- Comunidades, ranking entre alunos, conquistas e recompensas. Pontos, nível e
  sequência são o piso desta entrega; o resto é evolução futura.
- Redução de churn. Depende de volume acumulado que ainda não existe.
- Cobrir todas as matérias do ENEM com questões. A estrutura é completa; o
  conteúdo entra por matéria, na medida do tempo.
