# Plano de smoke test da spec D

**Para que serve:** decidir *o que* precisa ser exercitado à mão na spec D — o
onboarding, o percurso de estudo e a pontuação —, e por quê. É um plano, não um
roteiro: o roteiro do caminho feliz pelos quatro perfis está em
[`smoke-test.md`](smoke-test.md) e não é repetido aqui.

**A diferença entre os dois documentos importa.** O roteiro atravessa o caminho
feliz. Este plano cobre o resto: as bordas, os caminhos negativos, as costuras
entre telas e as degradações previstas. É onde os defeitos desta entrega
estavam.

A referência de comportamento é
[`back-end/study-tracker.md`](back-end/study-tracker.md): o objetivo, a regra de
distribuição do roadmap, a tabela de pontuação, as faixas de nível e o resumo
que as duas telas leem. Este plano não redefine nenhum deles; ele os provoca.

## Como este plano foi derivado

Não de imaginação. Cada bloco existe porque um defeito real apareceu ali durante
a execução. Quatro padrões se repetiram, e explicam o formato deste documento:

1. **O defeito morava na costura entre telas, não dentro de nenhuma delas.** Os
   quatro achados importantes da revisão da branch inteira estavam todos na
   ligação entre uma tela e a seguinte — uma bandeira que morria no caminho, um
   botão que perdia o contexto, um estado de erro que se disfarçava de estado
   vazio. Nenhuma revisão de tarefa individual podia vê-los, porque cada tela,
   sozinha, estava certa.
2. **O valor inventado voltou pela porta dos fundos.** A spec existe para tirar
   número fixo da tela do aluno, e durante a execução ele reapareceu duas vezes
   em lugares que ninguém estava olhando: um campo de formulário que nascia
   preenchido, e um perfil que desenhava zeros quando a rede caía. Zero exibido
   por falha é tão inventado quanto 3.120 escrito no código.
3. **O limite que o cliente pede não é o tamanho do que existe.** A tela do
   percurso pedia 50 etapas de um percurso de 107 e não dizia nada. O número
   errado não veio do backend; veio do valor padrão que o cliente não trocou.
4. **A ordem de escrita virou correção de concorrência.** Lançar os pontos na
   ordem em que o cliente mandou as respostas abria ciclo de espera entre duas
   requisições do mesmo aluno. A correção é ordenar a inserção; o teste que a
   protege é o que já existia, e quase foi enfraquecido para acomodar o defeito.

Por isso cada bloco diz o que **provocar**, não só o que conferir.

---

## Preparação

Vale a preparação do [`smoke-test.md`](smoke-test.md), inclusive a ordem
obrigatória `stack-rebuild` → `stack-up` → `services-migrate` →
`services-seed` → `services-seed-demo`. Além dela, esta spec tem três
pré-requisitos próprios, e o primeiro é um bloqueador.

### P1 — O seed do ENEM não está ligado a nenhum comando (sem ele, não há nada para testar)

`scripts/seed_enem.sql` cria a estrutura que o roadmap percorre, e **nenhum
alvo do Makefile o aplica**. `make services-seed` roda os seeds do catálogo do
commerce, não este. Sem ele, `gerar_roadmap` devolve zero, todo aluno vê um
percurso vazio, e cinco dos oito blocos abaixo falham pelo motivo errado.

```bash
docker exec -i edu-postgres psql -U edu -d learning_db \
  < back-end/learning-service/scripts/seed_enem.sql
```

Os seeds de conteúdo de Biologia têm a mesma lacuna e são igualmente
necessários — eles são a única fonte de **questão** do repositório. A ordem
entre os dois importa: o de Genética só acrescenta questões aos subtemas 7 e 8,
que o de Citologia cria, e rodado antes dele falha na chave estrangeira:

```bash
docker exec -i edu-postgres psql -U edu -d learning_db \
  < back-end/learning-service/scripts/seed_biologia_citologia.sql
docker exec -i edu-postgres psql -U edu -d learning_db \
  < back-end/learning-service/scripts/seed_biologia_genetica.sql
```

Conferir, depois dos três:

```sql
SELECT (SELECT count(*) FROM materia)  AS materias,   -- 11
       (SELECT count(*) FROM tema)     AS temas,      -- 36  (33 do ENEM + 3 de Citologia)
       (SELECT count(*) FROM subtema)  AS subtemas,   -- 107 (99 do ENEM + 8 de Citologia)
       (SELECT count(*) FROM questao)  AS questoes;   -- 34  (26 de Citologia + 8 de Genética)
```

Os três seeds são idempotentes: rodar de novo não duplica nada.

### P2 — O aluno de demonstração precisa existir

`DEMO_ACCOUNTS_PASSWORD='...' make services-seed-demo` cria `aluno@demo.edu`.
Todos os blocos abaixo são conduzidos por ele, exceto onde dito.

### P3 — Um aluno recém-criado é o instrumento de medição

Vários blocos (4.x da spec, e os blocos 1 e 6 aqui) só significam alguma coisa
contra uma conta **nova**, sem objetivo, sem progresso e sem pontos. Crie uma
pelo cadastro do app em vez de reaproveitar `aluno@demo.edu`, que acumula estado
conforme você testa.

### Tokens

Este plano usa chamadas diretas ao gateway além da interface, porque várias das
bordas não têm botão:

```bash
TOKEN=$(curl -s localhost:8100/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"aluno@demo.edu","password":"'"$DEMO_ACCOUNTS_PASSWORD"'"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["tokens"]["access_token"])')
```

As rotas desta spec ficam em `localhost:8100/api/onboarding`,
`/api/roadmap` e `/api/profile/summary`.

---

## Bloco 1 — O onboarding e as duas portas até ele

**Risco:** é o critério de pronto 2, e foi onde dois defeitos apareceram — um
campo que gravava valor que ninguém escolheu, e uma bandeira que morria no
caminho entre o cadastro e a tela inicial.

| # | Provocar | Esperado |
|---|---|---|
| 1.1 | Criar conta pelo cadastro do app | Cai no onboarding, não na tela inicial |
| 1.2 | Tocar **Começar** com o objetivo em branco | `Diga o que você quer conquistar`, e nada é salvo |
| 1.3 | Preencher o objetivo e tocar **Começar** sem abrir o calendário | `Escolha uma data-alvo`, e **nada é salvo** — o campo de data mostra `Escolha a data da prova`, nunca uma data pronta |
| 1.4 | Escolher data e confirmar | Vai para a tela inicial, e **aparece** `Conta criada com sucesso! 🎉` |
| 1.5 | Repetir 1.1 e tocar **Pular por enquanto** | Vai para a tela inicial, a saudação aparece, e `GET /api/onboarding` devolve `null` |
| 1.6 | Aluno que pulou: olhar a tela inicial | **Não existe** cartão de meta — nem vazio, nem com zeros |
| 1.7 | No perfil, tocar **Metas e objetivos** | Abre o onboarding preenchido, e o botão diz **Salvar** |
| 1.8 | `POST /api/onboarding` com data de ontem | 422 com `A data-alvo não pode estar no passado` — a frase que a tela exibe é essa |
| 1.9 | `POST /api/onboarding` uma segunda vez para o mesmo aluno | 409 `Você já tem um objetivo. Altere o que existe.` |
| 1.10 | `PUT /api/onboarding` num aluno sem objetivo | 404 `Você ainda não tem um objetivo` |

**Por que 1.3 tem linha própria.** O campo nascia com hoje + 180 dias desenhado
como se o aluno tivesse escolhido. Quem digitasse o objetivo e tocasse o botão
gravava uma data que nunca viu — na entrega cujo propósito inteiro é remover
número que ninguém escolheu.

**Por que 1.4 e 1.5 cobram a saudação.** O cadastro manda a bandeira para o
onboarding, e o onboarding tem que repassá-la adiante. Durante a execução ele
não repassava, e a mensagem de boas-vindas simplesmente deixou de existir — sem
erro, sem teste vermelho, sem ninguém notar.

---

## Bloco 2 — O percurso gerado

**Risco:** a regra de distribuição é explícita e simples de propósito, e é a
única coisa entre o objetivo do aluno e uma lista de datas.

| # | Provocar | Esperado |
|---|---|---|
| 2.1 | Fazer o onboarding com data daqui a 90 dias e olhar `GET /api/roadmap` | `total` = **107**; a primeira etapa vence **hoje**, a última **na data-alvo** |
| 2.2 | Conferir a ordem das etapas | Matérias na ordem do seed, temas e subtemas por `ordem` — nunca alfabética, nunca aleatória |
| 2.3 | Alterar **só o título** pelo perfil | Os prazos não se movem. Compare a lista antes e depois |
| 2.4 | Alterar a **data-alvo** para 180 dias | Os prazos se redistribuem, e a última etapa cai na data nova |
| 2.5 | Concluir uma etapa (bloco 5), depois alterar a data-alvo | A etapa **continua concluída** — regenerar preserva conclusão |
| 2.6 | Onboarding com data-alvo para **depois de amanhã** | 201, e o corpo traz `prazo_apertado: true`; a tela do percurso mostra `Seu prazo é apertado: várias etapas caem no mesmo dia.` |
| 2.7 | Onboarding com data-alvo **hoje** | Aceito. Todas as etapas vencem hoje — recusar impediria estudar para a prova de amanhã |

**2.5 é a propriedade inteira.** Regenerar é apagar e reinserir; as conclusões
são lidas antes do delete e reaplicadas por subtema. Se uma conclusão sumir ao
mudar a data, o aluno perde progresso que já pagou.

---

## Bloco 3 — O percurso inteiro, não a primeira página dele

**Risco:** foi um defeito real, e é do tipo que ninguém vê: a tela mostrava um
número plausível.

| # | Provocar | Esperado |
|---|---|---|
| 3.1 | Abrir a tela do percurso e rolar até o fim | **107 etapas**, não 50 |
| 3.2 | Comparar a contagem da tela com `GET /api/roadmap` → `total` | Iguais |
| 3.3 | Comparar a porcentagem do cartão da tela inicial com as etapas concluídas / 107 | Batem. As duas telas contam o mesmo percurso |
| 3.4 | `GET /api/roadmap?limit=0` e `?limit=500` | 422 nos dois |

**Por que 3.3 existe.** A porcentagem da tela inicial sempre contou as 107; era
a tela do percurso que pedia 50 e não dizia. Duas telas discordando sobre o
tamanho do percurso é pior que uma errada, porque cada uma confirma a outra pela
metade.

---

## Bloco 4 — Matéria sem questão aparece, marcada

**Risco:** é o critério de pronto 5, e a tentação de esconder o que não está
pronto é permanente.

Neste corte, **8 das 107 etapas são praticáveis** — as oito de Biologia
(Introdução à Célula, Citologia e Genética Básica), que somam 34 questões. As
outras 99 têm estrutura e nenhuma questão.

| # | Provocar | Esperado |
|---|---|---|
| 4.1 | Rolar a tela do percurso até uma etapa de Física, Química, História… | A etapa **aparece**, com `Conteúdo em preparação` |
| 4.2 | Tocar **Praticar** nessa etapa | O botão está **desabilitado** — não há nada para tocar |
| 4.3 | Encontrar uma etapa de Citologia e tocar **Praticar** | Abre o questionário **daquele tema**, não o seletor de matérias |
| 4.4 | Contar as etapas praticáveis | Oito, e todas de Biologia |
| 4.5 | `GET /api/roadmap` e contar `tem_questoes: true` | Oito |

**4.3 é o defeito que a revisão final achou.** O botão levava ao seletor de
matérias — a mesma tela para toda etapa, de todo tema. O portão que o backend
calcula com uma agregação dedicada não decidia nada: habilitado ou não, o
destino era o mesmo. Se ele voltar a abrir uma lista genérica, o
`tem_questoes` virou enfeite de novo.

---

## Bloco 5 — Pontuação

**Risco:** é extrato, não contador, e a idempotência é a propriedade que
impede o aluno de pagar duas vezes pelo mesmo fato — ou de não pagar nunca.

| # | Provocar | Esperado |
|---|---|---|
| 5.1 | Responder um questionário de Citologia acertando tudo | Cada questão correta vale 10; o perfil sobe |
| 5.2 | **Reenviar o mesmo questionário**, idêntico | O total **não muda**. Nenhuma questão pontua duas vezes |
| 5.3 | Acertar o suficiente para passar do limiar de domínio (0,7) num subtema com etapa no percurso | A etapa fica **concluída**, e entram 50 pontos |
| 5.4 | Responder de novo o mesmo subtema, ainda acima do limiar | A etapa continua concluída e **não** entram outros 50 |
| 5.5 | Acertar tudo duas vezes seguidas no mesmo subtema | Bônus de sequência de 5 e depois 10 — cresce com a sequência |
| 5.6 | Continuar acertando até a sequência passar de 10 | O bônus para em **50**. Sequência longa não vale mais que todo o resto |
| 5.7 | Deixar uma revisão vencer (`proxima_revisao` no passado) e responder aquele subtema | Entram 15 pontos de revisão no prazo |
| 5.8 | Responder o mesmo subtema de novo no mesmo dia | Não entram outros 15 — a referência carrega a data da revisão vencida |
| 5.9 | Conferir o nível no perfil contra o total | 0–99 é nível 1; 100 é nível 2; 4.500 ou mais é nível 10 |

**Por que 5.2 e 5.4 são linhas próprias.** As duas são o mesmo teste da mesma
propriedade em origens diferentes, e as duas já quase falharam: a idempotência
não vem de uma checagem em Python, vem de um índice único no banco. Se alguém
trocar o `ON CONFLICT DO NOTHING` por um `SELECT` seguido de `INSERT`, os dois
passos continuam passando num teste sequencial e falham sob concorrência.

**5.7 exige preparação pelo banco.** Não há tela que faça uma revisão vencer:

```sql
UPDATE aluno_tema_progresso
   SET proxima_revisao = now() - interval '1 day'
 WHERE aluno_id = '<uuid do aluno>' AND subtema_id = 3;
```

---

## Bloco 6 — O resumo: zero é zero, e falha não é zero

**Risco:** é o critério de pronto 4, e o segundo lugar onde o número inventado
voltou.

| # | Provocar | Esperado |
|---|---|---|
| 6.1 | Abrir o perfil de uma conta recém-criada | `0` pontos, `Nível 1`, `0` questões, `0` sequência — **zeros, não vazio** |
| 6.2 | Abrir a tela inicial da mesma conta | Sem objetivo, sem cartão de meta |
| 6.3 | Fazer o onboarding e voltar ao perfil | Os números continuam zero; só o cartão da tela inicial aparece |
| 6.4 | **Derrubar o learning-service** e abrir o perfil | Uma **mensagem de erro** — nunca zeros |
| 6.5 | Com o serviço no ar de novo, puxar para atualizar | Os números voltam |
| 6.6 | Conferir `dias_decorridos`/`dias_totais` no cartão | O par bate com a data de criação do objetivo e a data-alvo |
| 6.7 | Objetivo cuja data-alvo já passou | `dias_decorridos` = `dias_totais`; a barra não passa de 100% |

**6.4 é o bloco inteiro.** Um aluno com 3.000 pontos e a rede caída via
exatamente o que um aluno zerado vê. O modo de falha que esta spec existe para
remover tinha se mudado para o caminho de erro — o valor deixou de estar escrito
no código e passou a ser desenhado quando o dado não chegava. Para provocar sem
derrubar serviço, basta desligar a rede do aparelho antes de abrir o perfil.

---

## Bloco 7 — Concorrência

**Risco:** a correção que fizemos é de ordem de escrita, e o teste que a protege
é o que já existia. Bordas assim não aparecem na interface; provoque pela API.

| # | Provocar | Esperado |
|---|---|---|
| 7.1 | Disparar **duas** requisições simultâneas de `POST /api/diagnostic/answer` do mesmo aluno, mesmo tema, mesmas questões | As duas respondem 200. Nenhum 500, nenhum travamento |
| 7.2 | Conferir os pontos depois de 7.1 | O total é o de **uma** submissão. A segunda não pagou nada |
| 7.3 | Repetir 7.1 com as respostas na **ordem inversa** no corpo da segunda requisição | Igual: 200 nas duas, sem deadlock |
| 7.4 | Conferir `aluno_tema_progresso` depois | `total_respondidas` somou as duas; a sequência não perdeu incremento |

**7.3 é o teste do defeito.** Inserir os pontos na ordem em que o cliente mandou
as respostas fazia duas requisições adquirirem as mesmas chaves do índice único
em ordens opostas. A correção é inserir sempre em ordem crescente de questão; se
alguém reintroduzir a inserção dentro do laço de respostas, este passo é o que
pega.

---

## Bloco 8 — O seed

| # | Provocar | Esperado |
|---|---|---|
| 8.1 | Rodar `seed_enem.sql` duas vezes | Nenhuma duplicata; as contagens do P1 não mudam |
| 8.2 | Rodar `seed_biologia_citologia.sql` depois do ENEM, e `seed_biologia_genetica.sql` depois dele | Nenhuma colisão — as faixas de id não se cruzam; os subtemas 7 e 8 ficam com seis questões cada |
| 8.3 | Conferir se toda matéria tem ao menos um subtema | Sim, nas 11 |
| 8.4 | Criar um objetivo **antes** de rodar o seed | O percurso nasce vazio, e a tela diz o motivo em vez de mostrar lista vazia muda |

---

## Evidência no banco

```sql
-- 1. Um objetivo por aluno, com a data que ele escolheu
SELECT aluno_id, titulo, data_alvo, criado_em FROM objetivo_aluno;

-- 2. O percurso tem 107 etapas, a primeira hoje e a última na data-alvo
SELECT count(*) AS etapas, min(prazo) AS primeira, max(prazo) AS ultima,
       count(concluida_em) AS concluidas
FROM etapa_roadmap WHERE aluno_id = '<uuid>';

-- 3. O extrato explica de onde veio cada ponto
SELECT origem, count(*) AS lancamentos, sum(pontos) AS total
FROM lancamento_pontos WHERE aluno_id = '<uuid>'
GROUP BY origem ORDER BY total DESC;

-- 4. Nenhum fato pagou duas vezes (a constraint garante; esta consulta prova)
SELECT aluno_id, origem, referencia, count(*)
FROM lancamento_pontos GROUP BY 1,2,3 HAVING count(*) > 1;   -- zero linhas

-- 5. Quantas etapas são praticáveis
SELECT count(DISTINCT s.id) AS subtemas_com_questao FROM subtema s
JOIN questao q ON q.subtema_id = s.id;                        -- 8
```

---

## O que não é bug

- **Um aluno zerado está no nível 1, não no nível 0.** A primeira faixa começa
  em zero ponto, então 1 é o piso da escala e 0 é um nível que o backend não
  consegue produzir.
- **99 das 107 etapas não têm questão.** O seed do ENEM cria estrutura; conteúdo
  entra por matéria, na medida do tempo. É a decisão da spec, e o percurso
  funciona com qualquer quantidade.
- **O bônus de sequência não repaga um degrau já pago.** Quem chega à sequência
  3, erra, e volta à 3, não ganha de novo pelos degraus 1 a 3 daquele subtema.
  Cada degrau paga uma vez, por construção da chave de idempotência.
- **A sequência exibida no perfil é a maior do aluno**, não a do último
  questionário.
- **O nível não é gravado em lugar nenhum** — é calculado na leitura. Mudar as
  faixas não exige migrar dado, e não existe coluna "nível" para conferir.
- **Mudar só o título não regenera o percurso.** É deliberado: regenerar por
  causa de um texto apagaria e recriaria 107 linhas para um resultado idêntico.
- **A tela do percurso não pagina.** Ela pede as 107 de uma vez, que é o teto da
  rota. Um seed futuro maior que 200 subtemas vai precisar de paginação de
  verdade — hoje isso é dívida registrada, não defeito.
- **Regenerar o percurso enquanto o aluno responde é uma corrida conhecida.**
  Mudar a data-alvo no exato instante em que uma resposta conclui uma etapa pode
  descartar aquela conclusão (os pontos ficam; a marca se recupera na próxima
  regeneração), e duas regenerações simultâneas do mesmo aluno podem dar 500. As
  duas exigem duas ações do mesmo aluno no mesmo segundo. Está registrado como
  dívida na revisão da branch.
- **`flutter analyze` sai com 6 avisos `info`.** É o baseline do repositório; a
  contagem não mudou nesta entrega.

---

## Critério de aprovação

A spec D passa quando os oito blocos passam **e** as cinco consultas de
evidência batem, com os seis critérios de pronto do design cobertos assim:

| Critério | Onde é exercitado |
|---|---|
| 1. Nenhum número inventado nas telas do estudante | `grep -rn` sobre `front-end-flutter/lib` pelos quatro valores antigos — **já verificado no fechamento da branch, volta vazio** |
| 2. Aluno novo faz onboarding e vê o roadmap gerado | Blocos 1 e 2 |
| 3. Responder questão move progresso, pontos e etapa | Bloco 5 |
| 4. O perfil de um aluno zerado mostra zero | Bloco 6, passos 6.1 a 6.3 |
| 5. Matérias sem questão aparecem no roadmap, marcadas | Bloco 4 |
| 6. Suítes verdes | `uv run pytest` por serviço, `flutter test`, `flutter analyze lib/` — medidos no merge: learning 164, gateway 41, Flutter 249, analyze 6 |

Um bloco falho não invalida os outros — anote qual, com a resposta recebida, e
siga; a triagem do [`smoke-test.md`](smoke-test.md) vale aqui também.

Três resultados são bloqueadores, e não simples falhas de bloco:

- **Qualquer 500.** Esta entrega mexeu dentro de uma transação com história de
  concorrência documentada; um 500 novo é dessa família até prova em contrário.
- **Um número que o aluno não escolheu aparecendo como se ele tivesse
  escolhido** — uma data pré-preenchida, um zero de falha, uma contagem parcial
  anunciada como total. É o defeito que a spec inteira existe para remover, e ele
  já voltou duas vezes por portas diferentes durante a execução.
- **Pontos pagos duas vezes pelo mesmo fato**, ou a consulta 4 da evidência
  devolvendo qualquer linha.
