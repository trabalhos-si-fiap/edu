# Registro de execução do smoke test — spec D

**Data:** 2026-09-10. **Árvore medida:** `main` em `a49a019` (merge da spec D
mais o plano de smoke).

**O que este documento é:** o resultado medido de rodar
[`smoke-test-spec-d.md`](smoke-test-spec-d.md) até onde ele pode ser rodado sem
aparelho e sem operador humano. Não substitui o plano: substitui a frase "ainda
não rodamos" por uma lista do que passou, do que só roda na mão, e do que
apareceu no caminho.

**Placar:** 187 conferências — 161 automatizadas contra a API e o banco, 26
medidas à mão (contagens de seed, consultas de evidência, suítes, grep do
critério 1 e as costuras de tela lidas no código). Todas passaram. **Nenhum 500
em nenhuma rota, em nenhum momento**, incluindo 50 requisições concorrentes nas
duas corridas registradas como dívida. Nenhum fato pagou pontos duas vezes: a
consulta 4 da evidência devolve zero linhas no banco inteiro, depois de tudo.

Os três resultados bloqueadores do plano não apareceram. O bloqueador de
**preparação** (P1) está confirmado e continua aberto — é a única coisa neste
documento que exige ação antes da apresentação.

---

## 1. Por que isto não rodou contra o stack em execução

O stack do desenvolvedor estava de pé durante a medição e **não** serve para
este smoke test. Quatro fatos medidos, não inferidos:

| Fato | Como foi medido | Consequência |
|---|---|---|
| A imagem do learning-service é anterior à spec D | `curl localhost:8102/openapi.json` lista 11 paths e **nenhum** `/onboarding`, `/roadmap` ou `/profile` | Os blocos 1, 2, 3, 4 e 6 responderiam 404 inteiros |
| `learning_db` está uma revision atrás do head | `select version_num from alembic_version` devolve `b9e63fa43f39`; o head é `e1f2a3b4c5d6` | Nenhuma das três tabelas da spec existe — confirmado: `objetivo_aluno`, `etapa_roadmap` e `lancamento_pontos` somam 0 em `information_schema.tables` |
| O `learning_db` tem só o conteúdo de Biologia | 1 matéria, 3 temas, 8 subtemas, 26 questões | Um percurso gerado ali teria **8** etapas, não 107 — é o P1 já visível no banco do próprio desenvolvedor |
| Nenhum alvo do Makefile aplica os dois seeds | `grep -n seed Makefile` só encontra os seeds do catálogo do commerce | P1, abaixo |

Nada disso foi corrigido aqui: mexer nas imagens e nos bancos de
desenvolvimento do usuário está fora do que este agente pode fazer. Para rodar
a parte manual, o runbook é o de sempre, na ordem, **mais os dois seeds**:

```bash
make stack-rebuild && make stack-up && make services-migrate && make services-seed
DEMO_ACCOUNTS_PASSWORD='...' make services-seed-demo
docker exec -i edu-postgres psql -U edu -d learning_db < back-end/learning-service/scripts/seed_enem.sql
docker exec -i edu-postgres psql -U edu -d learning_db < back-end/learning-service/scripts/seed_biologia_citologia.sql
```

## 2. O ambiente em que rodou

Ambiente descartável, montado ao lado do stack do usuário sem tocá-lo, e
removido no fim:

- **Bancos:** `smoke_learning`, `smoke_auth` e `smoke_learning_test`, num
  Postgres próprio (contêiner `smoke-specd-postgres`, porta 5434). `alembic
  upgrade head` nos dois a partir do zero — as duas cadeias sobem limpas,
  incluindo `e1f2a3b4c5d6`.
- **Infra:** RabbitMQ próprio (`smoke-specd-rabbitmq`, porta 5676). A spec D
  não usa Redis.
- **Serviços:** `api-gateway` (8300), `auth-users-service` (8301) e
  `learning-service` (8302), rodando o código de `main` via `uv run granian`.
  Os quatro serviços que a spec D não toca ficaram fora, apontados para uma
  porta morta — o que também serviu para medir o §6.4 do plano.
- **Seed:** os dois arquivos de `learning-service/scripts/`, aplicados na
  ordem. **11 matérias, 36 temas, 107 subtemas, 26 questões** — exatamente os
  números que o plano prevê.
- **Chave do Groq:** ausente de propósito. A mensagem do tutor caiu no
  fallback determinístico em todas as respostas, que é o caminho padrão.

Consequência para a leitura: tudo abaixo mede o **backend** e os contratos que
o aplicativo consome. O que depende de tela, de aparelho ou de olho humano está
na §5.

---

## 3. Resultado por bloco

| Bloco | Conferências executadas | Resultado |
|---|---|---|
| 1. Onboarding e as duas portas | 1.2, 1.5, 1.7, 1.8, 1.9, 1.10 pelo servidor + 3 de autorização | Passa. As três frases do plano voltam **byte a byte**: `A data-alvo não pode estar no passado`, `Você já tem um objetivo. Altere o que existe.`, `Você ainda não tem um objetivo`. Data no passado e título em branco não gravam nada — conferido com um GET depois de cada recusa |
| 2. O percurso gerado | 2.1 a 2.7, todas | Passa. 107 etapas, a primeira **hoje** e a última **na data-alvo**, em todas as durações testadas (hoje, 2 dias, 90, 180, 200). Mudar só o título não move um único prazo; mudar a data redistribui os 107 e **preserva as conclusões com o carimbo original**, não recarimbado |
| 3. O percurso inteiro | 3.1, 3.2, 3.3, 3.4 | Passa. O servidor ainda tem default 50 e teto 200 — o cliente **precisa** pedir mais, e pede: `tracker_provider.dart:43` chama `fetchRoadmap(limit: 200)`. `limit=0` e `limit=500` dão 422; `offset=-1` também |
| 4. Matéria sem questão | 4.1, 4.4, 4.5 pelo servidor; 4.2 e 4.3 no código | Passa. **8 de 107** com `tem_questoes: true`, todas de Biologia; as outras 99 aparecem no percurso. O botão é `onPressed: null` sem questão, e com questão vai para `/questions` com `materiaNome`, `temaId` e `temaNome` — não para o seletor de matérias |
| 5. Pontuação | 5.1 a 5.9, mais o caminho abaixo do limiar | Passa. 32 conferências. Os degraus de sequência saíram 5, 10, 15 … 45, **50, 50, 50** — o teto segura em 50 nos degraus 10, 11 e 12. A revisão vencida paga 15 uma vez e a mesma data não paga de novo. Reenviar o questionário não repete nenhuma questão nem nenhuma etapa |
| 6. Zero é zero, falha não é zero | 6.1, 6.2, 6.3, 6.6, 6.7 pelo servidor; 6.4 nos dois lados | Passa. Conta nova: `0` pontos, nível `1`, `0` questões, `0` sequência — zeros, não nulos. Com o serviço fora do ar o gateway devolve **503 com mensagem**, e `ProfileSummarySection` desenha essa mensagem no estado de erro, não zeros. Objetivo vencido: `dias_decorridos == dias_totais`, a barra não passa de 100% |
| 7. Concorrência | 7.1, 7.2, 7.3, 7.4 | Passa. Duas requisições simultâneas: as duas 200, 18 lançamentos de questão (não 36), 4 de etapa (não 8), `total_respondidas` somou as duas e a sequência manteve **os dois incrementos**. Com o corpo em **ordem inversa**, 10 requisições cruzadas: 10× 200, nenhum deadlock |
| 8. O seed | 8.1, 8.2, 8.3, 8.4 | Passa. Rodar o seed do ENEM três vezes não muda nenhuma das quatro contagens; o de Biologia depois dele não colide; as 11 matérias têm subtema. Objetivo criado **antes** do seed nasce com 0 etapas e a tela tem frase para isso (`Seu percurso ainda está vazio.`) |

### Caça ao 500

Treze entradas fora de faixa, porque "qualquer 500" é bloqueador nesta spec:
título de 121 caracteres, data em formato brasileiro, ano 9999, campo ausente,
corpo vazio, `tema_id` inexistente e negativo, lista de respostas vazia, 51
respostas, questão de outro tema, alternativa de 2 caracteres, offset além do
fim. **Todas devolvem 4xx com mensagem** — nenhuma 500.

### Autorização

Quatro conferências à parte, pela regra 2 do CLAUDE.md: um aluno não vê o
objetivo, o percurso nem os pontos de outro; as três rotas novas recusam
requisição sem token (403) e com token adulterado.

---

## 4. As cinco consultas de evidência

| # | Resultado |
|---|---|
| 1. Um objetivo por aluno | 8 objetivos, 8 alunos distintos |
| 2. O percurso tem 107 etapas | 107, primeira `2026-09-10`, última na data-alvo, 3 concluídas |
| 3. O extrato explica cada ponto | `streak` 27 lançamentos/780, `etapa` 3/150, `questao` 10/100, `revisao` 1/15 |
| 4. Nenhum fato pagou duas vezes | **Zero linhas**, no banco inteiro, depois de 10 alunos e ~60 submissões |
| 5. Quantas etapas são praticáveis | **8** |

---

## 5. O que não roda sem aparelho

Onze passos do plano dependem de tela, dedo e olho. Para cada um, o que foi
possível verificar sem o aparelho está dito — e **nada disso substitui rodar**:

| Passo | O que foi verificado no código | O que falta no aparelho |
|---|---|---|
| 1.1 | `register_screen.dart:76` faz `pushReplacementNamed('/onboarding', arguments: {'justRegistered': true})` | Ver que cai mesmo no onboarding |
| 1.3 | `DateTime? _dataAlvo` nasce nulo; o campo mostra `Escolha a data da prova`; o erro é `Escolha uma data-alvo` | Ver que o campo está vazio, não com uma data pronta |
| 1.4 / 1.5 | As duas saídas (`_salvar` e `_pular`) repassam `ModalRoute.of(context)?.settings.arguments`; a home lê `justRegistered` e mostra `Conta criada com sucesso! 🎉` | Ver a saudação aparecer nos dois caminhos |
| 1.6 | `GoalCard` devolve `SizedBox.shrink()` quando `summary.goal == null` | Ver que não há cartão nenhum |
| 1.7 | Perfil → `Metas e objetivos` → `/onboarding`; o botão vira `Salvar` no modo edição | Ver o formulário preenchido |
| 3.1 | O cliente pede `limit: 200` | Rolar até o fim e contar 107 |
| 4.2 / 4.3 | Botão desabilitado sem questão; com questão, `/questions` com o tema | Tocar e ver abrir o questionário certo |
| 6.4 / 6.5 | O estado de erro desenha a mensagem | Desligar a rede, abrir o perfil, religar |

Os 249 testes de widget do repositório cobrem cada uma dessas costuras
isoladamente — e passam. O que eles não cobrem é a costura entre duas telas
reais, que é onde estavam os quatro defeitos da revisão final.

---

## 6. O que apareceu e não é falha de bloco

Cinco observações. Nenhuma bloqueia; três valem correção.

1. **`profile/summary` mistura data em UTC com data local do servidor.**
   `perfil.py` calcula `inicio = objetivo.criado_em.date()` (UTC, porque a
   coluna é `timestamptz`) e compara com `date.today()` (fuso do processo).
   Num servidor em UTC−3, um objetivo criado depois das 21h nasce com
   `criado_em` no dia seguinte em UTC, e `dias_totais` sai **um dia curto**:
   medido, um objetivo de 100 dias mostrou `dias_totais: 99`. **Na imagem
   entregue o processo roda em UTC e o efeito é zero** — mas os testes
   revelam o mesmo: `uv run pytest` do learning-service dá **164/164 com
   `TZ=UTC`** e **162/164** num host em UTC−3 depois das 21h, nos dois testes
   que montam `datetime.now(UTC)` contra `date.today()`. A suíte, hoje, mede o
   fuso da máquina junto com o código.
2. **Nenhuma das duas telas tem "puxar para atualizar".** `SummaryProvider.load()`
   só é chamado no `initState`. No perfil isso se resolve sozinho (ele é
   empurrado como rota nova a cada visita, então reabrir recarrega); **na tela
   inicial, não**: voltar do questionário por `pop` mantém o `State` vivo, e a
   porcentagem do cartão de meta fica parada no valor de quando a home montou.
   O passo 6.5 do plano ("puxar para atualizar") não é executável como está
   escrito — o substituto é sair da tela e voltar.
3. **A linha 5.2 do plano está imprecisa, e o comportamento está certo.**
   "O total não muda" ao reenviar o mesmo questionário: o total **muda**, e
   deve mudar — pelo bônus de sequência, que é o que a própria linha 5.5 do
   plano descreve. O que não se repete é o pagamento por questão, por etapa e
   por revisão. Medido: reenvio idêntico com dois subtemas rendeu exatamente
   +20 (degrau 2 de cada), e nada além.
4. **A dívida 2 da revisão de branch se reproduz; a dívida 1 não.** Responder
   enquanto o percurso é regenerado descartou a marca de conclusão em **8 de 10
   rodadas** — e em todas elas **os pontos ficaram**, que é o que a dívida diz.
   Já a dívida 1 (duas regenerações simultâneas podendo dar 500) **não
   apareceu**: 30 PUTs concorrentes do mesmo aluno, todos 200, sem etapa
   duplicada e com o percurso íntegro em 107.
5. **`points_card.dart:6` ainda escreve o número antigo num comentário**
   ("Formata 3120 como …", exemplo de separador de milhar). O grep exato do
   critério 1 continua vazio — ele procura `3,120`, com vírgula — e nada disso
   é renderizado. É prosa, não número na tela; vale trocar o exemplo mesmo
   assim, porque é o tipo de linha que faz uma busca futura parecer um achado.

E uma que é só informação: `subtemas_iniciados` volta **107** para um aluno
recém-criado que nunca respondeu nada, porque o consumer de `student.created`
cria uma linha de progresso zerada em todo subtema. Nenhuma tela mostra esse
campo hoje. Se alguma passar a mostrar, ele vai ler como "107 iniciados" para
quem não iniciou nenhum.

---

## 7. Os critérios de pronto

| Critério | Como ficou |
|---|---|
| 1. Nenhum número inventado nas telas | **Passa.** `grep -rn "3,120\|124/200\|Medicina USP\|0.68" front-end-flutter/lib` volta vazio |
| 2. Aluno novo faz onboarding e vê o roadmap | **Passa** pelo servidor (blocos 1 e 2); falta o dedo no aparelho |
| 3. Responder move progresso, pontos e etapa | **Passa** (bloco 5, 32 conferências) |
| 4. O perfil de um aluno zerado mostra zero | **Passa** (bloco 6) |
| 5. Matéria sem questão aparece, marcada | **Passa** (bloco 4) |
| 6. Suítes verdes | **Passa.** learning-service **164**, api-gateway **41**, Flutter **249**, `flutter analyze lib/` com os mesmos **6** avisos `info` do baseline |

**Bloqueadores:** nenhum dos três do plano. O que continua aberto é o P1 da
preparação — os dois seeds não estão ligados a alvo nenhum do Makefile, e o
`learning_db` da máquina do desenvolvedor prova o efeito: ele tem 8 subtemas,
não 107.
