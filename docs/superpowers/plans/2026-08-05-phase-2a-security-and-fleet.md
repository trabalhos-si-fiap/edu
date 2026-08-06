# Fase 2 — Bloco A: falhas vendorizadas e limpeza de frota

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as falhas de segurança que a fase 1 mediu e congelou, e convergir os sete serviços para a mesma receita de tooling — sem tocar em nenhuma rota que o app Flutter consome.

**Architecture:** Cada correção vive no serviço dono do defeito. Nada aqui muda contrato público do app: o Flutter continua falando com `back-end/legacy/` na porta 8001, e os serviços novos continuam publicados em 8101–8106. As correções de segurança vêm primeiro porque uma delas (auto-autorização do gabarito) foi reproduzida ponta a ponta; a limpeza de frota vem depois porque é mecânica e não bloqueia nada.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, pytest + pytest-asyncio, ruff, uv, PostgreSQL, RabbitMQ (aio-pika), Docker Compose.

**Spec:** [`docs/superpowers/specs/2026-08-04-microservices-migration-phase-2-design.md`](../specs/2026-08-04-microservices-migration-phase-2-design.md) — bloco A.
**Backlog de origem:** [`docs/superpowers/specs/2026-08-04-migration-backlog.md`](../specs/2026-08-04-migration-backlog.md) — seções "Falhas vendorizadas", "Divergência interna de contrato" e "Limpeza de frota" da fase 2.

---

## Global Constraints

Valem em **todas** as tasks abaixo. Elas são o `CLAUDE.md` do projeto mais as sete armadilhas que a fase 1 pagou para aprender.

**Do `CLAUDE.md` (sobrepõem qualquer default):**

1. Nunca concatenar input do usuário em SQL. Sempre ORM com bind params. Proibido `text(f"...")` com dado de request. `text()` estático dentro de uma migration é permitido.
2. Todo endpoint tem controle de acesso explícito (`Depends(...)`) **e** filtro de ownership.
3. Read→write em recurso compartilhado é atômico: `with_for_update()` ou expressão SQL atômica. Nunca `obj.value += x; commit()`.
4. Todo input tem limite: `max_length` no model **e** no schema Pydantic; listagem paginada; task Celery com `time_limit` e `soft_time_limit`.
5. Nenhum segredo no código. Nunca logar CPF, token ou senha. `loguru.logger`, nunca `print()`.
6. Schemas Pydantic com campos explícitos — sem `from_attributes` global expondo model sensível.
7. Comparação de segredo em tempo constante com `hmac.compare_digest()`, protegida contra `None`.
8. TDD sem exceção: Red → Green → Refactor. Teste antes da implementação.
9. Conventional Commits. Um commit por unidade lógica. Rodar `git diff --staged` antes de cada commit. Nunca commitar arquivo alheio à task.
10. Formatação e lint via `ruff` — `uv run ruff check .` e `uv run ruff format .` limpos antes de commitar.

**Do backlog da fase 1 (constraints de processo):**

11. **Todo teste de regressão precisa ser provado quebrando o que ele trava.** Não basta ver o teste passar depois do fix: reverta o fix, veja o teste falhar, reaplique. Isso apareceu em 5 tasks da fase 1.
12. **Nunca alimentar o teste com a própria constante da implementação.** Se o código diz `MAX_BODY_BYTES`, o teste escreve o número.
13. **Desconfie do instrumento antes de concluir que o código está limpo.** Um comando de verificação que não cobre `edu-common` reporta limpo um repositório sujo.
14. **Monkeypatch no módulo que define, não no que importa.** `from x import y` cria um nome novo no namespace de quem importa.
15. **`default=` do SQLAlchemy é client-side** e não cria DEFAULT no banco. Use `server_default=` junto quando o schema original tinha DEFAULT.
16. **Comentário que era verdade e virou mentira.** Seis casos na fase 1. Ao mudar comportamento, releia o docstring e os comentários do arquivo inteiro, não só as linhas editadas.
17. **`docker ps` reporta saudável container que não serve.** O watcher `--reload` do granian trava se arquivos somem debaixo dele. Depois de mexer em arquivo dentro de container rodando, `docker compose restart <svc>` antes de acreditar num health check.

**Armadilha entre blocos — LEIA ANTES DA TASK 22:**

> `commerce-service/app/config.py:17` declara `google_maps_api_key` e **nada o lê hoje**. Ele consta da lista de limpeza do backlog como "declarado e não lido". **Não remova.** O bloco C passa a lê-lo em `GET /orders/{id}/route`. A task 22 anota isso; não deleta.

**Comandos:**

```bash
# Suíte de um serviço (do diretório do serviço)
cd back-end/<servico> && uv run pytest -q
cd back-end/<servico> && uv run ruff check . && uv run ruff format --check .

# Todos os serviços de uma vez (da raiz do repo)
make services-test
make services-lint

# Num clone limpo, antes de qualquer coisa
make services-env
```

---

## File Structure

Nenhum arquivo novo de produção nasce neste bloco, exceto os testes de health e a migration de saneamento do analytics. A tabela abaixo é o mapa completo do que cada task toca.

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `learning-service/app/routers/diagnostico.py` | amarra questões ao tema; upsert atômico de progresso; deixa de publicar `revision.scheduled` | 1, 2, 4 |
| `learning-service/app/schemas/diagnostico.py` | teto na lista de respostas | 1 |
| `learning-service/app/scheduler.py` | marca `ultima_revisao`; payload com `subtema_nome` | 3, 4 |
| `learning-service/app/routers/materias.py` | `limite` → `limit` + `offset` | 23 |
| `notification-service/app/events/consumer.py` | handler de revisão usa o subtema | 4 |
| `auth-users-service/app/routers/auth.py` | parse de `birth_date`; `/auth/refresh` consulta o banco | 5, 7 |
| `auth-users-service/app/schemas/auth.py` · `user.py` · `address.py` | `max_length` em todo campo de texto | 6 |
| `auth-users-service/app/config.py` | remove `cors_origins` não lido | 22 |
| `api-gateway/app/main.py` | teto no corpo bufferizado | 8 |
| `api-gateway/app/config.py` | `max_request_body_bytes` | 8 |
| `api-gateway/app/routing.py` | remove entrada morta `"addresses"` | 21 |
| `commerce-service/app/routers/ocorrencias.py` | resolve atômico; publish pós-commit; leitura por dono | 9, 10 |
| `commerce-service/app/routers/admin.py` | `ge=0` e ajuste atômico de estoque | 11 |
| `analytics-service/app/events/consumer.py` | tira `nome`/`email` do `event_log` | 12 |
| `analytics-service/alembic/versions/*_scrub_pii_from_event_log.py` | **novo** — apaga o PII já gravado | 12 |
| `analytics-service/app/routers/analytics.py` · `schemas/analytics.py` | unifica "sem status" | 24 |
| `packages/edu-common/pyproject.toml` | os quatro blocos faltantes da receita | 13 |
| `api-gateway/pyproject.toml` | `asyncio_default_test_loop_scope` | 14 |
| `chatbot-service/pyproject.toml` | tira o whitelist de `requer_papel` inexistente | 15 |
| `{learning,commerce,notification}-service/pyproject.toml` | `httpx` runtime → dev | 16 |
| `analytics-service/Dockerfile.dockerignore` | adota a variante compartilhada | 17 |
| `{api-gateway,analytics,notification,chatbot}-service/tests/test_health.py` | **novos** — testam `/health` de verdade | 18 |
| `{auth,commerce,learning}-service/tests/test_openapi.py` | **renomeados** de `test_health.py` | 18 |
| `*/app/dependencies.py` | um nome só para a dependência de aluno | 19 |
| `*/app/database.py` | `sessionmaker` → `async_sessionmaker` | 20 |

---

# Parte 1 — Falhas vendorizadas

---

### Task 1: `/diagnostic/answer` amarra as questões ao tema do payload

Esta é a falha reproduzida ponta a ponta na revisão final da fase 1: 403 → `POST /answer` com questão de outro tema → 200 → gabarito liberado. O `GET /diagnostic/questions/{id}/context` checa se existe um `DiagnosticoResposta` do aluno para a questão — e é o próprio `/answer` que cria essa linha, para **qualquer** id existente, porque a query não amarra nada ao `payload.tema_id`.

**Files:**
- Modify: `back-end/learning-service/app/routers/diagnostico.py:51-53`
- Modify: `back-end/learning-service/app/schemas/diagnostico.py:11-19`
- Test: `back-end/learning-service/tests/test_diagnostic_routes.py`

**Interfaces:**
- Consumes: `Subtema` e `Tema` de `app.models.subtema` (já importados no router, linha 14).
- Produces: nada novo. `POST /diagnostic/answer` mantém a mesma assinatura e o mesmo `DiagnosticoResultado`.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `back-end/learning-service/tests/test_diagnostic_routes.py`. O segundo teste é o que realmente trava a vulnerabilidade — o primeiro sozinho poderia passar com um fix que rejeitasse a requisição mas ainda gravasse a linha.

```python
async def test_answer_ignores_questions_outside_the_payload_topic(
    client, db_session, student_identity
):
    """Questão de OUTRO tema não pode virar `DiagnosticoResposta`.

    Sem o join em Subtema, `Questao.id.in_(...)` aceita qualquer id existente
    e grava a resposta — que é a linha que o portão do gabarito checa.
    """
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()

    tema_alvo = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    tema_alheio = Tema(materia_id=materia.id, nome="Genética", ordem=2)
    db_session.add_all([tema_alvo, tema_alheio])
    await db_session.flush()

    subtema_alheio = Subtema(tema_id=tema_alheio.id, nome="Mendel", ordem=1)
    db_session.add(subtema_alheio)
    await db_session.flush()

    questao_alheia = Questao(
        subtema_id=subtema_alheio.id,
        enunciado="Qual a primeira lei de Mendel?",
        alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
        gabarito="A",
        nivel_dificuldade=1,
    )
    db_session.add(questao_alheia)
    await db_session.commit()

    response = await client.post(
        "/diagnostic/answer",
        json={
            "tema_id": tema_alvo.id,
            "respostas": [
                {"questao_id": questao_alheia.id, "alternativa_escolhida": "A"}
            ],
        },
        headers=student_identity.headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nenhuma resposta válida foi enviada"


async def test_answer_does_not_open_the_answer_key_gate_for_a_foreign_question(
    client, db_session, student_identity
):
    """Reprodução ponta a ponta da falha: /answer com questão de outro tema
    NÃO pode fazer o /context daquela questão passar a devolver o gabarito."""
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()

    tema_alvo = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    tema_alheio = Tema(materia_id=materia.id, nome="Genética", ordem=2)
    db_session.add_all([tema_alvo, tema_alheio])
    await db_session.flush()

    subtema_alheio = Subtema(tema_id=tema_alheio.id, nome="Mendel", ordem=1)
    db_session.add(subtema_alheio)
    await db_session.flush()

    questao_alheia = Questao(
        subtema_id=subtema_alheio.id,
        enunciado="Qual a primeira lei de Mendel?",
        alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
        gabarito="A",
        nivel_dificuldade=1,
    )
    db_session.add(questao_alheia)
    await db_session.commit()

    antes = await client.get(
        f"/diagnostic/questions/{questao_alheia.id}/context",
        headers=student_identity.headers,
    )
    assert antes.status_code == 403

    await client.post(
        "/diagnostic/answer",
        json={
            "tema_id": tema_alvo.id,
            "respostas": [
                {"questao_id": questao_alheia.id, "alternativa_escolhida": "A"}
            ],
        },
        headers=student_identity.headers,
    )

    depois = await client.get(
        f"/diagnostic/questions/{questao_alheia.id}/context",
        headers=student_identity.headers,
    )
    assert depois.status_code == 403, "o /answer abriu o portão do gabarito"


async def test_answer_rejects_more_responses_than_the_cap(client, student_identity):
    response = await client.post(
        "/diagnostic/answer",
        json={
            "tema_id": 1,
            "respostas": [
                {"questao_id": i, "alternativa_escolhida": "A"} for i in range(51)
            ],
        },
        headers=student_identity.headers,
    )
    assert response.status_code == 422
```

Acrescente ao topo do arquivo (se ainda não estiverem lá):

```python
from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_diagnostic_routes.py -k "outside_the_payload_topic or answer_key_gate or more_responses_than" -v`

Expected: os três FALHAM. Os dois primeiros com `assert 200 == 400` / `assert 200 == 403` — que é a vulnerabilidade em texto. O terceiro com `assert 400 == 422`.

- [ ] **Step 3: Amarre a query ao tema**

Em `back-end/learning-service/app/routers/diagnostico.py`, substitua as linhas 51-53:

```python
    questao_ids = [r.questao_id for r in payload.respostas]
    result = await db.execute(select(Questao).where(Questao.id.in_(questao_ids)))
    questoes = {q.id: q for q in result.scalars().all()}
```

por:

```python
    questao_ids = [r.questao_id for r in payload.respostas]
    # O join em Subtema amarra cada questão ao `payload.tema_id`. Sem ele,
    # `Questao.id.in_(...)` aceitava qualquer id existente e o laço abaixo
    # gravava um `DiagnosticoResposta` para ele — que é exatamente a linha
    # que `GET /diagnostic/questions/{id}/context` checa antes de liberar o
    # gabarito. Duas requisições e o aluno lia a resposta certa de qualquer
    # questão do banco. Ids fora do tema simplesmente não entram no dict e
    # caem no `continue` do laço; se nenhum sobrar, a rota devolve o 400 de
    # "nenhuma resposta válida".
    result = await db.execute(
        select(Questao)
        .join(Subtema, Questao.subtema_id == Subtema.id)
        .where(Questao.id.in_(questao_ids), Subtema.tema_id == payload.tema_id)
    )
    questoes = {q.id: q for q in result.scalars().all()}
```

Ainda em `diagnostico.py`, atualize o docstring de `contexto_questao` (linhas 258-282): apague o bloco `# TODO(fase 2): ...` inteiro e o parágrafo que começa em "Só libera o gabarito se existir um registro" passa a ler:

```python
    """
    Contexto completo de uma questão — enunciado, alternativas, gabarito
    E a alternativa que o próprio aluno escolheu — usado pelo Chatbot
    Service (`POST /chat/explicar-questao`) para explicar por que o aluno
    errou ou acertou.

    Só libera o gabarito se existir um registro de que ESTE aluno JÁ
    respondeu ESTA questão (`DiagnosticoResposta`). Desde a fase 2 essa
    linha só pode nascer de um `POST /diagnostic/answer` cujo `tema_id`
    contém a questão (o join em `Subtema` lá em cima), então o aluno não
    consegue mais fabricá-la para um id arbitrário.
    """
```

> Constraint 16: o docstring antigo garantia o contrário do que o código fazia. Apague a garantia falsa junto com a falha — não deixe as duas versões convivendo.

- [ ] **Step 4: Ponha teto na lista de respostas**

Em `back-end/learning-service/app/schemas/diagnostico.py`, troque:

```python
from pydantic import BaseModel
```

por:

```python
from pydantic import BaseModel, Field
```

e em `RespostaDiagnosticoIn`:

```python
    tema_id: int
    respostas: list[RespostaItem]
```

por:

```python
    tema_id: int
    # Teto por contrato (regra 4 do CLAUDE.md): o questionário do app tem 15
    # perguntas e `/subtopics/{id}/questions` já limita em 50. Sem teto, um
    # POST com 100 mil itens vira 100 mil INSERTs numa transação só.
    # Sem `min_length`: lista vazia continua caindo no 400 "Nenhuma resposta
    # válida foi enviada" que a suíte já trava, em vez de virar 422.
    respostas: list[RespostaItem] = Field(max_length=50)
```

E em `RespostaItem`:

```python
class RespostaItem(BaseModel):
    questao_id: int
    # `Questao.gabarito` é `String(1)`; a alternativa escolhida é comparada
    # com ele. Qualquer coisa maior é ruído que nunca casaria.
    alternativa_escolhida: str = Field(min_length=1, max_length=1)
```

- [ ] **Step 5: Rode os testes e confirme que passam**

Run: `cd back-end/learning-service && uv run pytest -q`

Expected: PASS, suíte inteira verde.

- [ ] **Step 6: Prove que o teste pode falhar (constraint 11)**

Reverta só o join (deixe o `.where(Questao.id.in_(questao_ids))` sem o join), rode `uv run pytest tests/test_diagnostic_routes.py -k "answer_key_gate" -v`, confirme FAIL, reaplique o fix e confirme PASS.

- [ ] **Step 7: Commit**

```bash
cd back-end/learning-service
uv run ruff check . && uv run ruff format .
cd ../..
git add back-end/learning-service/app/routers/diagnostico.py \
        back-end/learning-service/app/schemas/diagnostico.py \
        back-end/learning-service/tests/test_diagnostic_routes.py
git diff --staged
git commit -m "fix(learning): bind diagnostic answers to the payload topic

POST /diagnostic/answer selected questions by id alone and wrote a
DiagnosticoResposta for every existing one. That row is the gate
GET /diagnostic/questions/{id}/context checks before releasing the
answer key, so two requests exposed the key for any question in the
database. Reproduced end to end during phase 1.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: upsert atômico do progresso em `/diagnostic/answer`

`diagnostico.py:98-128` faz SELECT → decide → INSERT/UPDATE, e ainda soma `total_respondidas += len(respostas)` em Python. Duas requisições concorrentes do mesmo aluno no mesmo subtema (o app faz retry) leem "não existe" as duas, e a segunda estoura `IntegrityError` contra `uq_aluno_subtema` — 500 depois de já ter gravado as respostas. Regra 3 do `CLAUDE.md`.

**Files:**
- Modify: `back-end/learning-service/app/routers/diagnostico.py:99-129`
- Test: `back-end/learning-service/tests/test_diagnostic_routes.py`

**Interfaces:**
- Consumes: `AlunoTemaProgresso` (já importado, linha 11) e a constraint `uq_aluno_subtema` que já existe no model (`app/models/progresso.py:17`).
- Produces: nada novo.

- [ ] **Step 1: Escreva o teste que falha**

```python
async def test_answering_the_same_subtopic_twice_accumulates_instead_of_failing(
    client, db_session, student_identity
):
    """Duas chamadas ao /answer no mesmo subtema somam `total_respondidas`.

    O caminho antigo (SELECT -> INSERT) estourava `uq_aluno_subtema` quando
    as duas chamadas não viam a linha uma da outra; e mesmo em série, a soma
    em Python é read-modify-write.
    """
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db_session.add(subtema)
    await db_session.flush()
    questao = Questao(
        subtema_id=subtema.id,
        enunciado="O que é a bicamada lipídica?",
        alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
        gabarito="A",
        nivel_dificuldade=1,
    )
    db_session.add(questao)
    await db_session.commit()

    corpo = {
        "tema_id": tema.id,
        "respostas": [{"questao_id": questao.id, "alternativa_escolhida": "A"}],
    }
    primeira = await client.post(
        "/diagnostic/answer", json=corpo, headers=student_identity.headers
    )
    segunda = await client.post(
        "/diagnostic/answer", json=corpo, headers=student_identity.headers
    )
    assert primeira.status_code == 200
    assert segunda.status_code == 200

    result = await db_session.execute(
        select(AlunoTemaProgresso).where(
            AlunoTemaProgresso.aluno_id == student_identity.aluno_id,
            AlunoTemaProgresso.subtema_id == subtema.id,
        )
    )
    progresso = result.scalar_one()
    assert progresso.total_respondidas == 2
```

Imports novos no topo do arquivo de teste:

```python
from sqlalchemy import select

from app.models.progresso import AlunoTemaProgresso
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_diagnostic_routes.py -k "accumulates_instead_of_failing" -v`

Expected: FAIL. Com o `db_session` e a sessão da rota sendo sessões diferentes sobre o mesmo banco, a segunda chamada não enxerga a linha da primeira e estoura `IntegrityError` (500) ou grava `total_respondidas == 1`.

- [ ] **Step 3: Troque o SELECT-then-write por um upsert**

Em `back-end/learning-service/app/routers/diagnostico.py`, acrescente o import no topo:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
```

e substitua o bloco das linhas 99-129 (do `progresso_result = await db.execute(` até o `db.add(progresso)` do `else`) por:

```python
        # Upsert atômico (regra 3 do CLAUDE.md). O caminho anterior era
        # SELECT -> decidir -> INSERT/UPDATE com `total_respondidas += n` em
        # Python: duas requisições concorrentes do mesmo aluno no mesmo
        # subtema liam "não existe" as duas e a segunda estourava
        # `uq_aluno_subtema` DEPOIS de já ter gravado as respostas.
        #
        # `total_respondidas` soma no próprio SQL (`excluded` não serve: ele
        # carrega o valor que a linha NOVA traria, não o acumulado da linha
        # existente). Os outros campos são substituição, não acumulação.
        progresso_result = await db.execute(
            select(AlunoTemaProgresso).where(
                AlunoTemaProgresso.aluno_id == aluno_id,
                AlunoTemaProgresso.subtema_id == subtema_id,
            )
        )
        progresso_atual = progresso_result.scalar_one_or_none()
        intervalo_atual = progresso_atual.intervalo_dias if progresso_atual else 1.0
        streak_atual = progresso_atual.streak_acertos if progresso_atual else 0

        novo_intervalo, novo_streak, proxima_revisao = atualizar_revisao(
            dominio, intervalo_atual, streak_atual
        )

        stmt = (
            pg_insert(AlunoTemaProgresso)
            .values(
                aluno_id=aluno_id,
                subtema_id=subtema_id,
                nivel_dominio=dominio,
                intervalo_dias=novo_intervalo,
                streak_acertos=novo_streak,
                proxima_revisao=proxima_revisao,
                total_respondidas=len(respostas),
            )
            .on_conflict_do_update(
                constraint="uq_aluno_subtema",
                set_={
                    "nivel_dominio": dominio,
                    "intervalo_dias": novo_intervalo,
                    "streak_acertos": novo_streak,
                    "proxima_revisao": proxima_revisao,
                    "total_respondidas": (
                        AlunoTemaProgresso.total_respondidas + len(respostas)
                    ),
                },
            )
        )
        await db.execute(stmt)
```

Remova as linhas que restaram do bloco antigo (`novo_intervalo, novo_streak, proxima_revisao = atualizar_revisao(...)` original nas linhas 109-111, agora duplicado acima) e o `if progresso: ... else: ... db.add(progresso)` inteiro. `proxima_revisao` continua definido e é usado logo abaixo em `SubtemaAvaliadoOut`.

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest -q`

Expected: PASS, suíte inteira verde.

- [ ] **Step 5: Prove que o teste pode falhar (constraint 11)**

Troque `AlunoTemaProgresso.total_respondidas + len(respostas)` por `len(respostas)` no `set_`, rode o teste, confirme `assert 1 == 2`, reaplique.

- [ ] **Step 6: Commit**

```bash
cd back-end/learning-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/learning-service/app/routers/diagnostico.py \
        back-end/learning-service/tests/test_diagnostic_routes.py
git diff --staged
git commit -m "fix(learning): make the diagnostic progress write atomic

SELECT-then-INSERT/UPDATE on aluno_tema_progresso raced against
uq_aluno_subtema and summed total_respondidas in Python. Replaced by a
single ON CONFLICT DO UPDATE with the sum expressed in SQL.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: o scheduler para de renotificar todo dia para sempre

`scheduler.py` roda às 6h, seleciona todo `AlunoTemaProgresso` com `proxima_revisao <= agora` e publica `revision.scheduled`. Ele nunca escreve nada de volta — então a mesma linha casa de novo amanhã, e depois de amanhã, indefinidamente. A coluna `ultima_revisao` já existe no model (`progresso.py:25`) e nunca é escrita por ninguém.

**Files:**
- Modify: `back-end/learning-service/app/scheduler.py`
- Test: `back-end/learning-service/tests/test_scheduler.py` (novo)

**Interfaces:**
- Consumes: `AlunoTemaProgresso.ultima_revisao` / `.proxima_revisao` (`app/models/progresso.py`); `publish_event` de `app.events.publisher`.
- Produces: `verificar_revisoes_pendentes()` continua sem argumentos e sem retorno. A fixture `_stub_publish_event` do `conftest.py` já remenda `app.scheduler.publish_event` (linha 91) — não mexa nela.

- [ ] **Step 1: Escreva o teste que falha**

Crie `back-end/learning-service/tests/test_scheduler.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Materia, Subtema, Tema
from app.scheduler import verificar_revisoes_pendentes


async def _seed_progresso_vencido(db_session, aluno_id: uuid.UUID) -> AlunoTemaProgresso:
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db_session.add(subtema)
    await db_session.flush()

    progresso = AlunoTemaProgresso(
        aluno_id=aluno_id,
        subtema_id=subtema.id,
        nivel_dominio=0.4,
        intervalo_dias=1.0,
        streak_acertos=0,
        proxima_revisao=datetime.now(UTC) - timedelta(hours=2),
        total_respondidas=5,
    )
    db_session.add(progresso)
    await db_session.commit()
    await db_session.refresh(progresso)
    return progresso


async def test_scheduler_publishes_a_due_revision(db_session, _stub_publish_event):
    aluno_id = uuid.uuid4()
    await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()

    assert len(_stub_publish_event) == 1
    routing_key, payload = _stub_publish_event[0]
    assert routing_key == "revision.scheduled"
    assert payload["aluno_id"] == str(aluno_id)


async def test_scheduler_does_not_republish_the_same_revision_the_next_day(
    db_session, _stub_publish_event
):
    """Sem marcar `ultima_revisao`, a mesma linha volta a casar todo dia."""
    aluno_id = uuid.uuid4()
    await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()
    await verificar_revisoes_pendentes()

    assert len(_stub_publish_event) == 1, "a segunda passada renotificou a mesma revisão"


async def test_scheduler_marks_the_revision_as_notified(db_session, _stub_publish_event):
    aluno_id = uuid.uuid4()
    progresso = await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()

    result = await db_session.execute(
        select(AlunoTemaProgresso).where(AlunoTemaProgresso.id == progresso.id)
    )
    atualizado = result.scalar_one()
    assert atualizado.ultima_revisao is not None
    assert atualizado.ultima_revisao >= atualizado.proxima_revisao


async def test_a_new_due_date_makes_the_revision_eligible_again(
    db_session, _stub_publish_event
):
    aluno_id = uuid.uuid4()
    progresso = await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()
    assert len(_stub_publish_event) == 1

    progresso.proxima_revisao = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    await verificar_revisoes_pendentes()
    assert len(_stub_publish_event) == 2
```

> **Atenção (constraint 14):** `verificar_revisoes_pendentes` abre a própria sessão via `async_session` — ela **não** usa `get_db`, então o override do `client` não a alcança. O `db_session` do teste e a sessão do scheduler apontam para o mesmo `database_url_test`, então o commit do teste é visível para o scheduler. É por isso que estes testes pedem `db_session` e `_stub_publish_event` diretamente, sem `client`.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_scheduler.py -v`

Expected: o primeiro passa; `does_not_republish` FALHA com `assert 2 == 1`; `marks_the_revision_as_notified` FALHA com `assert None is not None`; `eligible_again` FALHA com `assert 3 == 2`.

- [ ] **Step 3: Marque a revisão como notificada**

Substitua `back-end/learning-service/app/scheduler.py` linhas 13-29 por:

```python
async def verificar_revisoes_pendentes() -> None:
    async with async_session() as db:
        agora = datetime.now(UTC)
        # `ultima_revisao >= proxima_revisao` significa "esta data de revisão
        # já virou notificação". Sem essa cláusula o job republicava a MESMA
        # linha toda manhã, para sempre: nada aqui escrevia de volta, e a
        # coluna `ultima_revisao` (que existe no model desde a importação)
        # nunca era usada por ninguém.
        #
        # Quando o aluno responde de novo, `/diagnostic/answer` grava um
        # `proxima_revisao` no futuro, que passa a ser maior que
        # `ultima_revisao` — e a linha volta a ficar elegível sozinha, sem
        # precisar de reset.
        result = await db.execute(
            select(AlunoTemaProgresso).where(
                AlunoTemaProgresso.proxima_revisao <= agora,
                or_(
                    AlunoTemaProgresso.ultima_revisao.is_(None),
                    AlunoTemaProgresso.ultima_revisao < AlunoTemaProgresso.proxima_revisao,
                ),
            )
        )
        pendentes = result.scalars().all()

        for item in pendentes:
            await publish_event(
                "revision.scheduled",
                {
                    "aluno_id": str(item.aluno_id),
                    "subtema_id": item.subtema_id,
                    "proxima_revisao": item.proxima_revisao.isoformat(),
                },
            )
            item.ultima_revisao = agora

        await db.commit()
```

e o import da linha 4:

```python
from sqlalchemy import or_, select
```

> `item.ultima_revisao = agora` fica **depois** do publish de propósito: se o publish estourar, o commit não acontece e a revisão continua pendente para a próxima passada. Entrega ao menos uma vez é o comportamento certo aqui — a alternativa (marcar antes) perde a notificação em silêncio.

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_scheduler.py -v && uv run pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd back-end/learning-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/learning-service/app/scheduler.py back-end/learning-service/tests/test_scheduler.py
git diff --staged
git commit -m "fix(learning): stop the revision scheduler from renotifying forever

The daily job selected every progress row past its due date and never
wrote anything back, so the same row matched again the next morning and
every morning after. It now stamps ultima_revisao and filters on it; a
new proxima_revisao from /diagnostic/answer makes the row eligible again
on its own.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: `revision.scheduled` deixa de virar N notificações idênticas

Duas metades do mesmo defeito. **Produtor:** `/diagnostic/answer` publica um `revision.scheduled` por subtema respondido, dentro do laço — um diagnóstico de 15 questões em 4 subtemas gera 4 eventos. **Consumidor:** `handle_revision_scheduled` ignora o `subtema_id` que recebe e escreve a constante `"seu conteúdo"`. Resultado: 4 notificações byte a byte idênticas por diagnóstico.

A correção separa os dois papéis: `/answer` **não notifica** (a revisão está agendada para dias à frente — dizer "Hora de revisar!" no segundo em que o aluno terminou o questionário é errado); o scheduler notifica quando vence, e o payload passa a carregar `subtema_nome` para o handler ter o que renderizar.

> **Esta task também fecha o item "eventos publicados antes do commit" do learning-service.** O backlog aponta `diagnostico.py:184` (publish) contra `:209` (commit) — e o publish da linha 184 é justamente o `revision.scheduled` de dentro do laço, que esta task **remove**. O outro publish do arquivo (`DiagnosticCompleted`, linha 216) já acontece depois do commit da 210 e fica como está. Confirme os dois com `grep -n "publish_event\|db.commit" app/routers/diagnostico.py` antes de fechar a task, e registre no relatório — senão alguém vai procurar por esse item na fase 3 e não vai achar.

**Files:**
- Modify: `back-end/learning-service/app/routers/diagnostico.py:185-192` (remove o publish)
- Modify: `back-end/learning-service/app/scheduler.py` (payload ganha `subtema_nome`)
- Modify: `back-end/notification-service/app/events/consumer.py:15,20-32`
- Test: `back-end/learning-service/tests/test_diagnostic_routes.py`, `back-end/learning-service/tests/test_scheduler.py`, `back-end/notification-service/tests/test_consumer.py`

**Interfaces:**
- Consumes: payload de `revision.scheduled`, que passa a ser `{"aluno_id": str, "subtema_id": int, "subtema_nome": str, "proxima_revisao": str}`.
- Produces: `handle_revision_scheduled` mantém a assinatura `(message: aio_pika.abc.AbstractIncomingMessage) -> None` e a entrada em `BINDINGS`.

- [ ] **Step 1: Escreva os testes que falham (produtor)**

Em `back-end/learning-service/tests/test_diagnostic_routes.py`:

```python
async def test_answer_does_not_publish_a_revision_notification(
    client, db_session, student_identity, _stub_publish_event
):
    """Revisão agendada para daqui a dias não vira notificação agora."""
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    subtemas = [
        Subtema(tema_id=tema.id, nome=nome, ordem=i)
        for i, nome in enumerate(["Membrana", "Organelas", "Núcleo"])
    ]
    db_session.add_all(subtemas)
    await db_session.flush()
    questoes = [
        Questao(
            subtema_id=s.id,
            enunciado=f"Pergunta de {s.nome}",
            alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
            gabarito="A",
            nivel_dificuldade=1,
        )
        for s in subtemas
    ]
    db_session.add_all(questoes)
    await db_session.commit()

    response = await client.post(
        "/diagnostic/answer",
        json={
            "tema_id": tema.id,
            "respostas": [
                {"questao_id": q.id, "alternativa_escolhida": "B"} for q in questoes
            ],
        },
        headers=student_identity.headers,
    )
    assert response.status_code == 200

    chaves = [routing_key for routing_key, _ in _stub_publish_event]
    assert "revision.scheduled" not in chaves
    assert chaves == ["diagnostic.completed"]
```

Em `back-end/learning-service/tests/test_scheduler.py`:

```python
async def test_scheduler_payload_carries_the_subtopic_name(db_session, _stub_publish_event):
    aluno_id = uuid.uuid4()
    await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()

    _routing_key, payload = _stub_publish_event[0]
    assert payload["subtema_nome"] == "Membrana"
```

- [ ] **Step 2: Rode e confirme que falham**

Run: `cd back-end/learning-service && uv run pytest tests/test_diagnostic_routes.py -k "does_not_publish_a_revision" tests/test_scheduler.py -k "subtopic_name" -v`

Expected: o primeiro FALHA (`chaves` tem 3 `revision.scheduled` antes do `diagnostic.completed`); o segundo FALHA com `KeyError: 'subtema_nome'`.

- [ ] **Step 3: Tire o publish do laço da rota**

Em `back-end/learning-service/app/routers/diagnostico.py`, apague as linhas 185-192 inteiras:

```python
        await publish_event(
            "revision.scheduled",
            {
                "aluno_id": str(aluno_id),
                "subtema_id": subtema_id,
                "proxima_revisao": proxima_revisao.isoformat(),
            },
        )
```

e acrescente, logo acima do `dominio_tema = calcular_dominio_tema(...)`:

```python
    # `revision.scheduled` NÃO sai daqui. Ele significa "há uma revisão
    # vencida agora", e no fim de um diagnóstico a próxima revisão está a
    # dias de distância — publicá-la aqui gerava uma notificação "Hora de
    # revisar!" no segundo em que o aluno terminou o questionário, uma por
    # subtema respondido. Quem publica é `app/scheduler.py`, quando vence.
```

- [ ] **Step 4: Ponha o nome do subtema no payload do scheduler**

Em `back-end/learning-service/app/scheduler.py`, troque o `select(AlunoTemaProgresso)` por um join que já traz o nome, e o laço por um que o usa:

```python
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import or_, select

from app.database import async_session
from app.events.publisher import publish_event
from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Subtema

_scheduler: AsyncIOScheduler | None = None


async def verificar_revisoes_pendentes() -> None:
    async with async_session() as db:
        agora = datetime.now(UTC)
        # `ultima_revisao >= proxima_revisao` significa "esta data de revisão
        # já virou notificação". Sem essa cláusula o job republicava a MESMA
        # linha toda manhã, para sempre.
        #
        # O join em Subtema carrega `subtema_nome` para o payload: o
        # notification-service não tem banco de conteúdo e escrevia uma
        # constante ("seu conteúdo") em toda notificação de revisão.
        result = await db.execute(
            select(AlunoTemaProgresso, Subtema.nome)
            .join(Subtema, AlunoTemaProgresso.subtema_id == Subtema.id)
            .where(
                AlunoTemaProgresso.proxima_revisao <= agora,
                or_(
                    AlunoTemaProgresso.ultima_revisao.is_(None),
                    AlunoTemaProgresso.ultima_revisao < AlunoTemaProgresso.proxima_revisao,
                ),
            )
        )
        pendentes = result.all()

        for item, subtema_nome in pendentes:
            await publish_event(
                "revision.scheduled",
                {
                    "aluno_id": str(item.aluno_id),
                    "subtema_id": item.subtema_id,
                    "subtema_nome": subtema_nome,
                    "proxima_revisao": item.proxima_revisao.isoformat(),
                },
            )
            item.ultima_revisao = agora

        await db.commit()
```

- [ ] **Step 5: Escreva o teste que falha (consumidor)**

Em `back-end/notification-service/tests/test_consumer.py`, acrescente:

```python
async def test_revision_notification_names_the_subtopic(db_session):
    await handle_revision_scheduled(
        _fake_message(
            {
                "aluno_id": "00000000-0000-0000-0000-000000000001",
                "subtema_id": 7,
                "subtema_nome": "Membrana Plasmática",
                "proxima_revisao": "2026-08-10T06:00:00+00:00",
            }
        )
    )

    result = await db_session.execute(select(Notificacao))
    notificacao = result.scalar_one()
    assert "Membrana Plasmática" in notificacao.descricao


async def test_revision_notification_falls_back_when_the_name_is_missing(db_session):
    """Payload antigo (sem `subtema_nome`) não pode derrubar o handler."""
    await handle_revision_scheduled(
        _fake_message(
            {
                "aluno_id": "00000000-0000-0000-0000-000000000001",
                "subtema_id": 7,
                "proxima_revisao": "2026-08-10T06:00:00+00:00",
            }
        )
    )

    result = await db_session.execute(select(Notificacao))
    notificacao = result.scalar_one()
    assert "seu conteúdo" in notificacao.descricao
```

> Reaproveite o helper de mensagem falsa que `test_consumer.py` já usa (leia o arquivo primeiro; ele existe porque a suíte já cobre os outros quatro handlers). Se o nome for outro que `_fake_message`, use o nome real — não crie um segundo helper.

- [ ] **Step 6: Rode e confirme que falha**

Run: `cd back-end/notification-service && uv run pytest tests/test_consumer.py -k "names_the_subtopic or falls_back_when_the_name" -v`

Expected: `names_the_subtopic` FALHA (a descrição diz "seu conteúdo"); `falls_back` passa por acidente — ele é a rede de proteção, não o alvo.

- [ ] **Step 7: Faça o handler usar o nome**

Em `back-end/notification-service/app/events/consumer.py`, troque as linhas 12-15:

```python
# Mapa de subtema_id -> nome amigável para exibir na notificação.
# Pro MVP, um cache simples em memória evita chamar o Learning Service
# a cada evento; pode ser substituído por uma consulta real se preciso.
NOMES_SUBTEMA_FALLBACK = "seu conteúdo"
```

por:

```python
# O produtor (`learning-service/app/scheduler.py`) manda `subtema_nome` no
# payload desde a fase 2 — este serviço não tem banco de conteúdo e não pode
# resolver o id sozinho. O fallback cobre mensagem antiga ainda na fila no
# momento do deploy; sem ele, um `KeyError` derrubaria o handler e a
# mensagem sumiria (não há DLQ até a fase 3).
NOMES_SUBTEMA_FALLBACK = "seu conteúdo"
```

e o corpo do handler (linhas 20-32):

```python
async def handle_revision_scheduled(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        subtema_nome = payload.get("subtema_nome") or NOMES_SUBTEMA_FALLBACK
        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo="Hora de revisar!",
                    descricao=f"Você tem uma revisão agendada para {subtema_nome}.",
                    tipo="estudo",
                )
            )
            await db.commit()
```

- [ ] **Step 8: Rode as duas suítes**

Run: `cd back-end/learning-service && uv run pytest -q && cd ../notification-service && uv run pytest -q`

Expected: PASS nas duas.

- [ ] **Step 9: Prove que o teste pode falhar (constraint 11)**

Troque `payload.get("subtema_nome") or NOMES_SUBTEMA_FALLBACK` de volta por `NOMES_SUBTEMA_FALLBACK`, rode `-k names_the_subtopic`, confirme FAIL, reaplique.

- [ ] **Step 10: Commit (dois commits — dois serviços, duas unidades lógicas)**

```bash
cd back-end/learning-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/learning-service/app/routers/diagnostico.py \
        back-end/learning-service/app/scheduler.py \
        back-end/learning-service/tests/test_diagnostic_routes.py \
        back-end/learning-service/tests/test_scheduler.py
git diff --staged
git commit -m "fix(learning): publish revision.scheduled only when a revision is due

/diagnostic/answer published one event per answered subtopic, inside the
loop, for a revision days away. The scheduler is what knows a revision is
due; its payload now carries subtema_nome so the consumer has something
to render.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

cd back-end/notification-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/notification-service/app/events/consumer.py \
        back-end/notification-service/tests/test_consumer.py
git diff --staged
git commit -m "fix(notification): render the subtopic name in revision notifications

The handler received subtema_id and ignored it, writing a constant
string, so every revision notification was byte-identical. It now reads
subtema_nome from the payload, falling back for messages already queued.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `POST /auth/register` deixa de dar 500 com `birth_date` em ISO

`RegisterIn.data_valida` (schemas/auth.py:46-53) valida `"2000-01-15"` como aceitável: `"2000-01-15".split("/")` devolve `["2000-01-15"]`, `reversed` + `join` devolve a mesma string, e `date.fromisoformat` a aceita. O router então chama `_parse_birth_date`, que faz `dia, mes, ano = valor.split("/")` e estoura `ValueError: not enough values to unpack` — 500 não autenticado.

**Files:**
- Modify: `back-end/auth-users-service/app/schemas/auth.py:46-53`
- Modify: `back-end/auth-users-service/app/routers/auth.py:60-62,77`
- Test: `back-end/auth-users-service/tests/test_schemas.py`, `back-end/auth-users-service/tests/test_auth_routes.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `RegisterIn.birth_date` continua `str` no formato `"DD/MM/AAAA"`. `_parse_birth_date(valor: str) -> date` deixa de existir; a conversão passa para o validador, que agora devolve `date`.

- [ ] **Step 1: Escreva o teste que falha**

Em `back-end/auth-users-service/tests/test_auth_routes.py`:

```python
async def test_register_rejects_an_iso_birth_date_with_422(client):
    """`birth_date` em ISO passava pelo validador e estourava no router."""
    response = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.iso@example.com",
            "phone": "11999999999",
            "birth_date": "2000-01-15",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert response.status_code == 422


async def test_register_rejects_an_impossible_date_with_422(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.31fev@example.com",
            "phone": "11999999999",
            "birth_date": "31/02/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert response.status_code == 422


async def test_register_accepts_the_documented_format(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.ok@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert response.status_code == 201
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/auth-users-service && uv run pytest tests/test_auth_routes.py -k "iso_birth_date or impossible_date or documented_format" -v`

Expected: `iso_birth_date` FALHA com 500 (ou com o `ValueError` vazando, dependendo do handler de exceção). Os outros dois passam.

- [ ] **Step 3: Faça o validador converter, em vez de só olhar**

Em `back-end/auth-users-service/app/schemas/auth.py`, troque o validador de `RegisterIn`:

```python
    @field_validator("birth_date")
    @classmethod
    def data_valida(cls, v: str) -> str:
        try:
            date.fromisoformat("-".join(reversed(v.split("/"))))
        except (ValueError, IndexError) as exc:
            raise ValueError("Data de nascimento deve estar no formato DD/MM/AAAA") from exc
        return v
```

por:

```python
    @field_validator("birth_date")
    @classmethod
    def data_valida(cls, v: str) -> str:
        """Aceita exatamente `DD/MM/AAAA`.

        A versão anterior fazia `date.fromisoformat("-".join(reversed(
        v.split("/"))))`, que para `"2000-01-15"` (sem barra nenhuma)
        devolve a própria string e é aceita — o validador passava e o
        router estourava `ValueError: not enough values to unpack` ao
        desempacotar em três partes. 500 não autenticado.

        `datetime.strptime` com formato fixo rejeita ISO, `31/02/2000` e
        qualquer variação de separador de uma vez só.
        """
        try:
            datetime.strptime(v, "%d/%m/%Y").date()  # noqa: DTZ007 — data civil, sem fuso
        except ValueError as exc:
            raise ValueError("Data de nascimento deve estar no formato DD/MM/AAAA") from exc
        return v
```

e o import do topo:

```python
from datetime import date, datetime
```

> `date` continua importado: outros schemas do arquivo o usam. Se `uv run ruff check .` acusar `F401`, remova-o — mas confira antes.

- [ ] **Step 4: Faça o router usar a mesma conversão**

Em `back-end/auth-users-service/app/routers/auth.py`, troque:

```python
def _parse_birth_date(valor: str) -> date:
    dia, mes, ano = valor.split("/")
    return date(int(ano), int(mes), int(dia))
```

por:

```python
def _parse_birth_date(valor: str) -> date:
    """`RegisterIn.data_valida` já garantiu o formato — este parse não pode
    mais ser a primeira validação (era, e por isso um ISO virava 500)."""
    return datetime.strptime(valor, "%d/%m/%Y").date()  # noqa: DTZ007 — data civil, sem fuso
```

O import da linha 2 já traz `datetime`.

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd back-end/auth-users-service && uv run pytest -q`

Expected: PASS.

- [ ] **Step 6: Prove que o teste pode falhar (constraint 11)**

Reverta o validador para a versão antiga, rode `-k iso_birth_date`, confirme FAIL, reaplique.

- [ ] **Step 7: Commit**

```bash
cd back-end/auth-users-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/auth-users-service/app/schemas/auth.py \
        back-end/auth-users-service/app/routers/auth.py \
        back-end/auth-users-service/tests/test_auth_routes.py
git diff --staged
git commit -m "fix(auth): reject an ISO birth_date with 422 instead of 500

date.fromisoformat on a string with no slash returns it unchanged, so the
validator accepted \"2000-01-15\" and the router blew up unpacking it into
three parts. An unauthenticated 500. strptime with a fixed format rejects
ISO, impossible dates and separator variants in one call.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: `max_length` em todo campo de texto do auth-users-service

Regra 4 do `CLAUDE.md`: limite no model **e** no schema. Os models já têm (`User.nome` é `String(150)`, `telefone` é `String(20)`); os schemas não têm nenhum, então um `name` de 10 MB atravessa o Pydantic e só morre no `INSERT` — 500 não autenticado em `POST /auth/register`, e uma requisição de 10 MB processada até o banco.

**Files:**
- Modify: `back-end/auth-users-service/app/schemas/auth.py`
- Modify: `back-end/auth-users-service/app/schemas/user.py`
- Modify: `back-end/auth-users-service/app/schemas/address.py`
- Test: `back-end/auth-users-service/tests/test_schemas.py`

**Interfaces:**
- Consumes: os comprimentos declarados em `app/models/user.py` e `app/models/address.py`.
- Produces: nada novo — só `Field(max_length=...)` nos schemas existentes.

- [ ] **Step 1: Levante os comprimentos reais dos models**

Run: `cd back-end/auth-users-service && grep -n "String(" app/models/user.py app/models/address.py`

Anote cada coluna e seu tamanho. **Todo `max_length` de schema abaixo tem que bater com a coluna correspondente** — não invente número, e não copie a constante do model para o teste (constraint 12: o teste escreve o número literal).

- [ ] **Step 2: Escreva o teste que falha**

Em `back-end/auth-users-service/tests/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas.address import AddressIn
from app.schemas.auth import PasswordResetConfirmIn, RegisterIn, RegisterStaffIn
from app.schemas.user import UserUpdateIn


def _register_payload(**overrides):
    base = {
        "name": "Ana",
        "email": "ana@example.com",
        "phone": "11999999999",
        "birth_date": "15/01/2000",
        "education_level": "3º ano",
        "password": "senha!forte1",
    }
    return {**base, **overrides}


def test_register_name_is_bounded():
    with pytest.raises(ValidationError):
        RegisterIn(**_register_payload(name="A" * 151))


def test_register_phone_is_bounded():
    with pytest.raises(ValidationError):
        RegisterIn(**_register_payload(phone="9" * 21))


def test_register_staff_fields_are_bounded():
    base = {
        "nome": "Bruno",
        "email": "bruno@example.com",
        "senha": "senha!forte1",
        "role": "separador",
    }
    with pytest.raises(ValidationError):
        RegisterStaffIn(**{**base, "nome": "B" * 151})
    with pytest.raises(ValidationError):
        RegisterStaffIn(**{**base, "telefone": "9" * 21})
    with pytest.raises(ValidationError):
        RegisterStaffIn(**{**base, "documento": "1" * 21})


def test_password_reset_code_is_bounded():
    """O código tem 6 dígitos; sem teto ele chega inteiro ao bcrypt."""
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(
            email="ana@example.com", code="0" * 100, new_password="senha!forte1"
        )


def test_user_update_fields_are_bounded():
    with pytest.raises(ValidationError):
        UserUpdateIn(nome="A" * 151)
    with pytest.raises(ValidationError):
        UserUpdateIn(telefone="9" * 21)


def test_address_fields_are_bounded():
    base = {
        "zip_code": "01310100",
        "street": "Av. Paulista",
        "number": "1000",
        "neighborhood": "Bela Vista",
        "city": "São Paulo",
        "state": "SP",
    }
    with pytest.raises(ValidationError):
        AddressIn(**{**base, "street": "R" * 256})
    with pytest.raises(ValidationError):
        AddressIn(**{**base, "city": "C" * 256})
```

> Ajuste cada literal ao que o Step 1 mediu. Se `Address.street` for `String(200)`, o teste usa `"R" * 201`. Um teste que use um número maior que o do model passaria mesmo com o `max_length` errado.

- [ ] **Step 3: Rode e confirme que falha**

Run: `cd back-end/auth-users-service && uv run pytest tests/test_schemas.py -v`

Expected: todos os testes novos FALHAM com `DID NOT RAISE ValidationError`.

- [ ] **Step 4: Ponha os limites**

Em `app/schemas/auth.py`, importe `Field` e anote cada campo de texto. Exemplo para `RegisterIn` (repita o padrão nos demais, com os números do Step 1):

```python
class RegisterIn(BaseModel):
    """Payload de `POST /auth/register` — casa com `AuthApi.register()`.

    Todo campo de texto tem `max_length` batendo com a coluna do model
    (regra 4 do CLAUDE.md). Sem isso o Pydantic aceitava megabytes e o
    limite só aparecia no INSERT, como 500 não autenticado.
    """

    name: str = Field(max_length=150)
    email: EmailStr
    phone: str = Field(max_length=20)
    birth_date: str = Field(max_length=10)  # "DD/MM/AAAA"
    education_level: EducationLevel
    password: str
```

`password` fica sem `max_length` de propósito: `_validar_bytes_senha` já barra por **bytes**, que é o limite real do bcrypt — um `max_length` em caracteres daria falsa sensação de cobertura (é o que o docstring de `_validar_bytes_senha` já explica).

Em `PasswordResetConfirmIn`, `code: str = Field(max_length=10)` — o código tem 6 dígitos e vai para `verify_password`.

Em `app/schemas/user.py`: `nome: str | None = Field(default=None, max_length=150)` e `telefone: str | None = Field(default=None, max_length=20)`.

Em `app/schemas/address.py`: um `Field(max_length=...)` por campo de texto em `AddressIn` **e** em `AddressPatch`, com os números de `app/models/address.py`.

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd back-end/auth-users-service && uv run pytest -q`

Expected: PASS, suíte inteira verde (`test_addresses_routes.py` e `test_users_routes.py` incluídos — se algum quebrar, o `max_length` está menor que o dado que a suíte já usava; confira contra o model antes de afrouxar).

- [ ] **Step 6: Commit**

```bash
cd back-end/auth-users-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/auth-users-service/app/schemas/ back-end/auth-users-service/tests/test_schemas.py
git diff --staged
git commit -m "fix(auth): bound every text field in the request schemas

The models declared String(150)/String(20) and the Pydantic schemas
declared none, so oversized input travelled all the way to the INSERT and
came back as an unauthenticated 500. Every max_length matches its column.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: `/auth/refresh` consulta o banco

Hoje o refresh só decodifica o token e emite um par novo. Desativar (`ativo = False`) ou rebaixar (`role`) um usuário não tem efeito nenhum até o refresh token expirar — 14 dias, com o `.env` compartilhado em vigor.

**Files:**
- Modify: `back-end/auth-users-service/app/routers/auth.py:152-188`
- Test: `back-end/auth-users-service/tests/test_auth_routes.py`

**Interfaces:**
- Consumes: `User` de `app.models.user`, `get_db` de `app.database` — os dois já importados no arquivo.
- Produces: `POST /auth/refresh` ganha `db: AsyncSession = Depends(get_db)`. Resposta continua `TokensOut` plana (sem wrapper) — é o que `TokenRefresher.refresh()` do Flutter espera.

- [ ] **Step 1: Escreva o teste que falha**

Em `back-end/auth-users-service/tests/test_auth_routes.py`:

```python
async def test_refresh_rejects_a_deactivated_user(client, db_session):
    registro = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.deactivate@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert registro.status_code == 201
    refresh_token = registro.json()["tokens"]["refresh_token"]

    result = await db_session.execute(
        select(User).where(User.email == "ana.deactivate@example.com")
    )
    user = result.scalar_one()
    user.ativo = False
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401


async def test_refresh_reflects_the_current_role(client, db_session):
    """Rebaixar o papel tem que valer no próximo refresh, não só na expiração."""
    registro = await client.post(
        "/auth/register",
        json={
            "name": "Bruno",
            "email": "bruno.role@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    refresh_token = registro.json()["tokens"]["refresh_token"]

    result = await db_session.execute(
        select(User).where(User.email == "bruno.role@example.com")
    )
    user = result.scalar_one()
    user.role = "separador"
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200

    decoded = decode_token(
        response.json()["access_token"],
        settings.jwt_secret,
        settings.jwt_algorithm,
        expected_type="access",
    )
    assert decoded["role"] == "separador"


async def test_refresh_rejects_a_token_for_a_deleted_user(client):
    from edu_common.security import create_refresh_token

    token = create_refresh_token(
        str(uuid.uuid4()),
        "student",
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.refresh_token_expire_days,
    )
    response = await client.post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
```

Imports novos no topo (confira quais já existem antes de duplicar):

```python
import uuid

from edu_common.security import decode_token
from sqlalchemy import select

from app.config import settings
from app.models.user import User
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/auth-users-service && uv run pytest tests/test_auth_routes.py -k "refresh_rejects or refresh_reflects" -v`

Expected: os três FALHAM — `assert 200 == 401`, `assert 'student' == 'separador'`, `assert 200 == 401`.

- [ ] **Step 3: Consulte o banco antes de emitir**

Em `back-end/auth-users-service/app/routers/auth.py`, substitua o bloco final de `refresh` (das linhas 174-188) e a assinatura:

```python
@router.post("/refresh", response_model=TokensOut)
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)):
    """Resposta plana (sem wrapper `tokens`) — casa com `TokenRefresher.refresh()`.

    Consulta o banco de propósito, apesar de o token já vir assinado: sem
    isso, desativar ou rebaixar um usuário não tinha efeito nenhum até o
    refresh token expirar (14 dias com o `.env` compartilhado em vigor). O
    papel do token novo vem da coluna, não da claim do token velho.
    """
    # `expected_type="refresh"` deixa o próprio decode_token recusar um access
    # token aqui, em vez de checar `decoded.get("type")` manualmente.
    decoded = decode_token(
        payload.refresh_token, settings.jwt_secret, settings.jwt_algorithm, expected_type="refresh"
    )
    if decoded is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")

    # `decoded` só vem de tokens assinados por este serviço, mas um payload
    # forjado por outro emissor com o mesmo segredo (ou um token antigo,
    # gerado antes de `role` existir nas claims) pode passar em `decode_token`
    # sem carregar `sub`. Acessar via índice levantaria `KeyError`, que o
    # FastAPI transforma em 500 — aqui isso é só mais um refresh token
    # inválido, então cai no mesmo 401 genérico dos outros casos.
    sub = decoded.get("sub")
    if sub is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")

    result = await db.execute(select(User).where(User.id == sub))
    user = result.scalar_one_or_none()
    # Mesmo 401 genérico para usuário inexistente e usuário desativado: a
    # distinção seria um oráculo de enumeração e não muda nada para o app,
    # que trata os dois com logout.
    if user is None or not user.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")

    access_token = create_access_token(
        str(user.id),
        user.role,
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.access_token_expire_minutes,
    )
    novo_refresh_token = create_refresh_token(
        str(user.id),
        user.role,
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.refresh_token_expire_days,
    )
    return TokensOut(access_token=access_token, refresh_token=novo_refresh_token)
```

> A checagem `role is None` do código antigo sai: o papel agora vem da coluna, não da claim. Um token legado sem `role` passa a funcionar e recebe o papel real — que é o comportamento certo.

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/auth-users-service && uv run pytest -q`

Expected: PASS. Se algum teste antigo assumia que um refresh token sem `role` dava 401, ele muda de expectativa — atualize-o e explique no corpo do commit.

- [ ] **Step 5: Prove que o teste pode falhar (constraint 11)**

Comente o bloco `if user is None or not user.ativo`, rode `-k refresh_rejects_a_deactivated_user`, confirme FAIL, reaplique.

- [ ] **Step 6: Commit**

```bash
cd back-end/auth-users-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/auth-users-service/app/routers/auth.py \
        back-end/auth-users-service/tests/test_auth_routes.py
git diff --staged
git commit -m "fix(auth): look the user up on refresh

/auth/refresh only decoded and re-signed, so deactivating or demoting a
user had no effect until the refresh token expired — 14 days under the
shared .env. The new pair now carries the role from the column.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: teto no corpo bufferizado do gateway

`api-gateway/app/main.py:51` faz `body = await request.body()`, que junta o corpo inteiro em memória antes de qualquer autenticação. A fase 1 comprovou com um POST não autenticado de 9,6 MB.

**Files:**
- Modify: `back-end/api-gateway/app/main.py:37-51`
- Modify: `back-end/api-gateway/app/config.py`
- Test: `back-end/api-gateway/tests/test_proxy.py`

**Interfaces:**
- Consumes: `settings.max_request_body_bytes` (novo campo).
- Produces: `Settings.max_request_body_bytes: int = 2 * 1024 * 1024`. O gateway passa a responder **413** com `detail="Corpo da requisição excede o limite de N bytes"`.

- [ ] **Step 1: Escreva o teste que falha**

Em `back-end/api-gateway/tests/test_proxy.py`:

```python
async def test_oversized_body_is_rejected_before_reaching_a_service(client, monkeypatch):
    """O gateway bufferiza o corpo inteiro antes de qualquer auth. Sem teto,
    um POST não autenticado de megabytes já custa a memória."""
    chamou = False

    async def _nunca_deveria_ser_chamado(*args, **kwargs):
        nonlocal chamou
        chamou = True
        raise AssertionError("o gateway repassou um corpo acima do teto")

    monkeypatch.setattr("app.main.httpx.AsyncClient.request", _nunca_deveria_ser_chamado)

    corpo = b"x" * (2 * 1024 * 1024 + 1)
    response = await client.post(
        "/api/auth/login", content=corpo, headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    assert not chamou


async def test_a_body_under_the_cap_still_passes_through(client, monkeypatch):
    async def _eco(self, method, url, **kwargs):
        import httpx as _httpx

        return _httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("app.main.httpx.AsyncClient.request", _eco)

    response = await client.post(
        "/api/auth/login", content=b"x" * 1024, headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
```

> Constraint 12: o teste escreve `2 * 1024 * 1024 + 1` literal, não `settings.max_request_body_bytes + 1`. Se alguém mudar o default por engano, o teste avisa.
> Constraint 14: o alvo do monkeypatch é `app.main.httpx...` porque `main.py` faz `import httpx` (não `from httpx import ...`) — confira antes de rodar; se o import mudar, o alvo muda.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/api-gateway && uv run pytest tests/test_proxy.py -k "oversized_body or under_the_cap" -v`

Expected: `oversized_body` FALHA — o gateway repassa e o stub estoura o `AssertionError`.

- [ ] **Step 3: Declare o limite na config**

Em `back-end/api-gateway/app/config.py`, acrescente ao `Settings`:

```python
    # Teto do corpo que o gateway bufferiza em memória antes de repassar. O
    # proxy chama `await request.body()` ANTES de qualquer autenticação, então
    # sem teto um POST anônimo de megabytes já custa a memória do gateway —
    # comprovado na fase 1 com 9,6 MB. 2 MiB cobre com folga o maior corpo que
    # o app envia hoje (JSON de pedido/endereço); upload de imagem é fase 3 e
    # vai precisar de um caminho próprio, não deste.
    max_request_body_bytes: int = 2 * 1024 * 1024
```

Acrescente a mesma variável ao `back-end/api-gateway/.env.example` como `MAX_REQUEST_BODY_BYTES=2097152`.

- [ ] **Step 4: Aplique o teto no proxy**

Em `back-end/api-gateway/app/main.py`, substitua a linha 51 (`body = await request.body()`) por:

```python
    # Teto antes de bufferizar (ver `settings.max_request_body_bytes`). Duas
    # checagens porque `Content-Length` é uma dica do cliente, não um fato:
    # ele pode mentir, vir ausente, ou o corpo pode chegar em chunked. A
    # primeira evita ler o corpo à toa quando o cliente é honesto; a segunda
    # é a que realmente vale.
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit():
        if int(content_length) > settings.max_request_body_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Corpo da requisição excede o limite de "
                    f"{settings.max_request_body_bytes} bytes"
                ),
            )

    body = await request.body()
    if len(body) > settings.max_request_body_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Corpo da requisição excede o limite de {settings.max_request_body_bytes} bytes"
            ),
        )
```

> Isso ainda bufferiza o corpo inteiro no caso chunked antes de rejeitar — é uma melhora, não uma defesa completa. A defesa completa é o teto no reverse proxy à frente do gateway (`client_max_body_size` no nginx), que não existe neste ambiente. Registre isso no corpo do commit.

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd back-end/api-gateway && uv run pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd back-end/api-gateway && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/api-gateway/app/main.py back-end/api-gateway/app/config.py \
        back-end/api-gateway/.env.example back-end/api-gateway/tests/test_proxy.py
git diff --staged
git commit -m "fix(gateway): cap the buffered request body at 2 MiB

The proxy called await request.body() before any authentication, so an
anonymous POST of megabytes already cost the gateway its memory — proven
in phase 1 with 9.6 MB. Content-Length is checked first as a cheap hint,
then the buffered length as the real gate. A chunked body is still fully
read before rejection; the complete defence is a cap on the reverse proxy
in front, which this environment does not have.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: `POST /occurrences/{id}/resolve` fica atômico e publica depois do commit

Duas coisas no mesmo endpoint. **(a)** `ocorrencias.py:255-274` faz `pedido.valor_total = pedido.valor_total + diferenca` — read-modify-write sem lock, contra a regra 3 do `CLAUDE.md`; e o `if ocorrencia.status != "ABERTA"` da linha 221 é TOCTOU, então duas requisições concorrentes resolvem a mesma ocorrência duas vezes e aplicam a diferença de preço duas vezes. **(b)** o `publish_event("order.status_changed")` da linha 295 acontece **antes** do `await db.commit()` da linha 308 — se o commit falhar, o notification-service já disse ao aluno que o pedido foi cancelado.

**Files:**
- Modify: `back-end/commerce-service/app/routers/ocorrencias.py:205-321`
- Test: `back-end/commerce-service/tests/test_occurrences_routes.py`

**Interfaces:**
- Consumes: `select(...).with_for_update()` do SQLAlchemy.
- Produces: `POST /occurrences/{id}/resolve` mantém `OcorrenciaOut` e os mesmos códigos de status. A ordem dos eventos publicados muda: `order.status_changed` (quando há cancelamento) e `order.occurrence_resolved` saem os dois **depois** do commit, nessa ordem.

- [ ] **Step 1: Escreva os testes que falham**

Em `back-end/commerce-service/tests/test_occurrences_routes.py`:

O arquivo já define, no topo, `headers_for(role, sub)`, `_seed_pedido(db_session, status, **overrides)`, `_seed_produto(db_session)` e as constantes `ALUNO`/`PICKER_A`/`PICKER_B`/`DELIVERER_A`/`ADMIN`. Reaproveite-os; acrescente só o helper de ocorrência.

```python
ALUNO = "00000000-0000-0000-0000-000000000001"  # sub padrão de headers_for("student")


async def _seed_ocorrencia_falta_estoque(db_session, pedido, produto) -> Ocorrencia:
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="FALTA_ESTOQUE",
        status="ABERTA",
        produto_id=produto.id,
        motivo="Sem estoque no CD",
        criado_por=PICKER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    return ocorrencia


async def test_resolving_the_same_occurrence_twice_applies_the_price_delta_once(
    client, db_session
):
    """O `status != ABERTA` da linha 221 é TOCTOU sem lock de linha."""
    original = await _seed_produto(db_session)          # preço 100.00 no helper
    substituto = Produto(nome="Substituto", preco=Decimal("150.00"), categoria="apostila")
    db_session.add(substituto)
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, aluno_id=ALUNO, separador_id=PICKER_A
    )
    db_session.add(
        PedidoItem(
            pedido_id=pedido.id,
            produto_id=original.id,
            fornecedor_id=None,
            quantidade=2,
            preco_unitario=Decimal("100.00"),
        )
    )
    pedido.valor_total = Decimal("200.00")
    await db_session.commit()
    ocorrencia = await _seed_ocorrencia_falta_estoque(db_session, pedido, original)

    corpo = {"resolucao": "substituir", "produto_escolhido_id": substituto.id}
    primeira = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve", json=corpo, headers=headers_for("student")
    )
    segunda = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve", json=corpo, headers=headers_for("student")
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 400

    await db_session.refresh(pedido)
    # 200.00 + (150.00 - 100.00) * 2 = 300.00. Aplicada UMA vez.
    assert pedido.valor_total == Decimal("300.00")


async def test_cancel_publishes_the_status_change_after_the_commit(
    client, db_session, _stub_publish_event
):
    """Ordem dos eventos: nada é publicado antes de a transação fechar."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, aluno_id=ALUNO, separador_id=PICKER_A
    )
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        nova_data_sugerida=datetime.now(UTC) + timedelta(days=2),
        motivo="Chuva na rota",
        criado_por=DELIVERER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    _stub_publish_event.clear()  # ignora o que o seed publicou

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student"),
    )
    assert response.status_code == 200

    chaves = [routing_key for routing_key, _ in _stub_publish_event]
    assert chaves == ["order.status_changed", "order.occurrence_resolved"]

    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.CANCELADO.value
```

Imports novos no topo do arquivo de teste (confira quais já existem):

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.ocorrencia import Ocorrencia
from app.models.pedido import PedidoItem
from app.models.produto import Produto
```

> Confira o preço que `_seed_produto` usa antes de confiar no `300.00` — se o helper não usar `100.00`, ajuste **o número literal do teste**, nunca calcule-o a partir do helper (constraint 12).
>
> O segundo teste sozinho **não** prova a ordem publish/commit (ele passaria também no código atual, que publica antes). Ele trava a ordem relativa dos dois eventos. A prova de que o publish é pós-commit é o Step 5.

- [ ] **Step 2: Rode e confirme que o primeiro falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_occurrences_routes.py -k "price_delta_once or after_the_commit" -v`

Expected: `price_delta_once` FALHA — sem lock, a segunda chamada também vê `ABERTA` e aplica a diferença de novo.

- [ ] **Step 3: Trave as linhas e mova os publishes**

Em `back-end/commerce-service/app/routers/ocorrencias.py`, na função `resolver_ocorrencia`:

Troque o SELECT da ocorrência (linha 216) por:

```python
    # `with_for_update()` nos dois: sem ele, o `status != ABERTA` abaixo é um
    # TOCTOU — duas requisições concorrentes leem "ABERTA", as duas passam, e
    # a diferença de preço da substituição é aplicada duas vezes no
    # `valor_total`. Regra 3 do CLAUDE.md.
    result = await db.execute(
        select(Ocorrencia).where(Ocorrencia.id == ocorrencia_id).with_for_update()
    )
```

e o SELECT do pedido (linha 224) por:

```python
    pedido_result = await db.execute(
        select(Pedido).where(Pedido.id == ocorrencia.pedido_id).with_for_update()
    )
```

No ramo `cancelar_pedido`, **remova** o `await publish_event("order.status_changed", ...)` das linhas 295-302 e no lugar guarde a intenção:

```python
    elif resolucao == "cancelar_pedido":
        if not validar_transicao(pedido.status, StatusPedido.CANCELADO.value):
            raise HTTPException(400, f"Não é possível cancelar um pedido em status {pedido.status}")
        pedido.status = StatusPedido.CANCELADO.value
        db.add(
            PedidoStatusHistorico(
                pedido_id=pedido.id,
                status=StatusPedido.CANCELADO.value,
                user_id=aluno_id,
                observacao=f"Cancelado pelo aluno via ocorrência #{ocorrencia.id}",
            )
        )
        cancelou = True
```

Inicialize `cancelou = False` logo depois de `resolucao = payload.resolucao` (linha 229).

Depois do `await db.refresh(ocorrencia)` (linha 309), publique os dois na ordem:

```python
    # Os dois publishes ficam DEPOIS do commit. Publicar antes fazia o
    # notification-service avisar "seu pedido foi cancelado" mesmo quando a
    # transação estourava logo em seguida — o aluno recebia a notificação de
    # um cancelamento que não aconteceu.
    if cancelou:
        await publish_event(
            "order.status_changed",
            {
                "pedido_id": pedido.id,
                "aluno_id": str(pedido.aluno_id),
                "status": StatusPedido.CANCELADO.value,
            },
        )

    await publish_event(
        "order.occurrence_resolved",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(pedido.aluno_id),
            "ocorrencia_id": ocorrencia.id,
            "resolucao": resolucao,
        },
    )
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS.

- [ ] **Step 5: Prove que o publish é pós-commit**

Acrescente o teste que só passa com a ordem certa:

```python
async def test_a_failed_commit_publishes_nothing(client, db_session, monkeypatch, _stub_publish_event):
    """Se o commit estourar, o aluno não pode ter sido notificado."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, aluno_id=ALUNO, separador_id=PICKER_A
    )
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        nova_data_sugerida=datetime.now(UTC) + timedelta(days=2),
        motivo="Chuva na rota",
        criado_por=DELIVERER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    _stub_publish_event.clear()

    async def _commit_que_falha(self):
        raise RuntimeError("commit falhou")

    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.commit", _commit_que_falha)

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student"),
    )
    assert response.status_code == 500
    assert _stub_publish_event == []
```

> `monkeypatch.setattr` sobre `AsyncSession.commit` afeta **toda** sessão, inclusive a do `db_session`. Por isso o seed acontece antes do patch e o teste não commita nada depois.

Rode-o contra o código **antigo** (reverta a ordem dos publishes) e confirme que ele falha com `assert [('order.status_changed', ...)] == []`. Reaplique o fix e confirme PASS.

- [ ] **Step 6: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/routers/ocorrencias.py \
        back-end/commerce-service/tests/test_occurrences_routes.py
git diff --staged
git commit -m "fix(commerce): lock the rows and publish after the commit on resolve

The ABERTA check was a TOCTOU without a row lock, so two concurrent
resolves applied the substitution price delta twice to valor_total. And
order.status_changed went out before db.commit(), so a failing
transaction still told the student their order was cancelled.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: leitura de ocorrência deixa de ser staff-wide

`ocorrencias.py:137` e `:188` liberam `separador`, `entregador`, `admin` e `student`. O aluno é filtrado pelo dono (linhas 146 e 196), mas **separador e entregador veem qualquer pedido** — inclusive os que não estão trabalhando. O resto do serviço já aplica a regra "só quem reivindicou o pedido, ou admin" (`ocorrencias.py:50` e `:100`, com o mesmo raciocínio documentado ali).

**Files:**
- Modify: `back-end/commerce-service/app/routers/ocorrencias.py:131-155,185-202`
- Test: `back-end/commerce-service/tests/test_occurrences_routes.py`

**Interfaces:**
- Consumes: `Pedido.separador_id`, `Pedido.entregador_id`.
- Produces: função nova no módulo, usada pelas duas rotas:
  `def _pode_ver_pedido(user: dict, pedido: Pedido) -> bool`.

- [ ] **Step 1: Escreva o teste que falha**

`_seed_pedido` recebe o status como **posicional** e o resto por `**overrides` — a assinatura real é `_seed_pedido(db_session, status, **overrides)`. `PICKER_A`/`PICKER_B`/`DELIVERER_A`/`ADMIN` já existem no arquivo.

```python
async def test_a_picker_cannot_read_occurrences_of_an_order_they_do_not_hold(
    client, db_session
):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A
    )

    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("separador", sub=PICKER_B)
    )
    assert response.status_code == 403


async def test_a_courier_cannot_read_occurrences_of_an_order_they_do_not_hold(
    client, db_session
):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.get(
        f"/occurrences/order/{pedido.id}",
        headers=headers_for("entregador", sub=str(uuid.uuid4())),
    )
    assert response.status_code == 403


async def test_a_picker_with_no_assignment_at_all_is_also_refused(client, db_session):
    """`separador_id is None` não pode ser lido como "é meu"."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value)

    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 403


async def test_the_assigned_picker_can_read_them(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A
    )

    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 200


async def test_an_admin_still_reads_any_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A
    )
    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("admin", sub=ADMIN)
    )
    assert response.status_code == 200


async def test_occurrence_detail_applies_the_same_rule(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A
    )
    ocorrencia = await _seed_ocorrencia_falta_estoque(db_session, pedido, produto)

    response = await client.get(
        f"/occurrences/{ocorrencia.id}", headers=headers_for("separador", sub=PICKER_B)
    )
    assert response.status_code == 403
```

> `_seed_ocorrencia_falta_estoque` foi escrito na task 9. Se você estiver executando a task 10 sem ter feito a 9, copie-o de lá.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_occurrences_routes.py -k "cannot_read_occurrences or detail_applies_the_same" -v`

Expected: os três testes de negação FALHAM com `assert 200 == 403`.

- [ ] **Step 3: Extraia a regra e aplique-a nas duas rotas**

Em `back-end/commerce-service/app/routers/ocorrencias.py`, acrescente logo abaixo do `router = APIRouter(...)`:

```python
def _pode_ver_pedido(user: dict, pedido: Pedido) -> bool:
    """Mesma regra que `reportar_falta_estoque`/`reportar_atraso_entrega` já
    aplicam na escrita (linhas 50 e 100): admin vê tudo, aluno vê o próprio
    pedido, e separador/entregador só veem o pedido que reivindicaram.

    A leitura era staff-wide: qualquer separador lia a ocorrência de qualquer
    pedido, incluindo os que ele não está trabalhando.
    """
    papel = user.get("role")
    if papel == "admin":
        return True
    if papel == "student":
        return str(pedido.aluno_id) == user["sub"]
    if papel == "separador":
        return pedido.separador_id is not None and str(pedido.separador_id) == user["sub"]
    if papel == "entregador":
        return pedido.entregador_id is not None and str(pedido.entregador_id) == user["sub"]
    return False
```

Em `listar_ocorrencias_pedido`, troque as linhas 145-147:

```python
    # Aluno só pode ver ocorrências do próprio pedido
    if user["role"] == "student" and str(pedido.aluno_id) != user["sub"]:
        raise HTTPException(403, "Sem permissão para ver este pedido")
```

por:

```python
    if not _pode_ver_pedido(user, pedido):
        raise HTTPException(403, "Sem permissão para ver este pedido")
```

Em `detalhe_ocorrencia`, troque as linhas 196-200:

```python
    if user["role"] == "student":
        pedido_result = await db.execute(select(Pedido).where(Pedido.id == ocorrencia.pedido_id))
        pedido = pedido_result.scalar_one_or_none()
        if not pedido or str(pedido.aluno_id) != user["sub"]:
            raise HTTPException(403, "Sem permissão para ver esta ocorrência")
```

por:

```python
    pedido_result = await db.execute(select(Pedido).where(Pedido.id == ocorrencia.pedido_id))
    pedido = pedido_result.scalar_one_or_none()
    if not pedido or not _pode_ver_pedido(user, pedido):
        raise HTTPException(403, "Sem permissão para ver esta ocorrência")
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS. Se algum teste antigo assumia que um separador qualquer lia qualquer ocorrência, ele estava travando o defeito — atualize-o e diga isso no corpo do commit.

- [ ] **Step 5: Prove que o teste pode falhar (constraint 11)**

Faça `_pode_ver_pedido` retornar `True` para `separador` incondicionalmente, rode `-k cannot_read_occurrences`, confirme FAIL, reaplique.

- [ ] **Step 6: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/routers/ocorrencias.py \
        back-end/commerce-service/tests/test_occurrences_routes.py
git diff --staged
git commit -m "fix(commerce): scope occurrence reads to whoever holds the order

Both read routes let any separador or entregador see any order's
occurrences. The write routes already enforced 'only the assigned staff,
or admin'; the same rule is now one function used by both sides.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11: ajuste de estoque não aceita negativo e é atômico

`admin.py:96-110` recebe `quantidade: int` sem `ge=0` — um admin põe `-50` no estoque e a rota grava. E o SELECT-then-assign não segura a linha, então dois ajustes concorrentes se sobrescrevem em silêncio.

**Files:**
- Modify: `back-end/commerce-service/app/routers/admin.py:96-110`
- Test: `back-end/commerce-service/tests/test_admin_routes.py`

**Interfaces:**
- Consumes: `Estoque` de `app.models.produto`.
- Produces: `PATCH /admin/inventory/{estoque_id}/adjust` passa a rejeitar `quantidade < 0` com 422.

- [ ] **Step 1: Escreva o teste que falha**

`test_admin_routes.py` já define `_seed_estoque(db_session)` — **sem** parâmetro de quantidade. Leia a quantidade que ele grava e escreva-a literal no teste (constraint 12); não passe um argumento que o helper não aceita.

```python
async def test_inventory_adjust_rejects_a_negative_quantity(client, db_session):
    estoque = await _seed_estoque(db_session)
    quantidade_inicial = estoque.quantidade

    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=-50",
        headers=headers_for("admin", sub=ADMIN),
    )

    assert response.status_code == 422
    await db_session.refresh(estoque)
    assert estoque.quantidade == quantidade_inicial


async def test_inventory_adjust_accepts_zero(client, db_session):
    """Zero é um ajuste legítimo — "acabou o estoque" não é o mesmo que
    "valor inválido". O piso é 0, não 1."""
    estoque = await _seed_estoque(db_session)
    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=0",
        headers=headers_for("admin", sub=ADMIN),
    )
    assert response.status_code == 200
    assert response.json()["quantidade"] == 0
```

> `quantidade_inicial` é lido do objeto e não escrito literal aqui de propósito: a asserção é "não mudou", não "é 10". Se o helper mudar o valor, este teste continua correto — e é essa a propriedade que ele trava.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_admin_routes.py -k "negative_quantity or accepts_zero" -v`

Expected: `negative_quantity` FALHA com `assert 200 == 422` e o estoque em -50.

- [ ] **Step 3: Ponha o piso e o lock**

Em `back-end/commerce-service/app/routers/admin.py`:

```python
@router.patch("/inventory/{estoque_id}/adjust", response_model=EstoqueOut)
async def ajustar_estoque(
    estoque_id: int,
    # `ge=0`: sem piso, um admin gravava estoque negativo e a separação
    # passava a trabalhar contra um número que não existe no mundo físico.
    quantidade: int = Query(ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    # `with_for_update()`: o ajuste é um read→write sobre recurso compartilhado
    # (regra 3 do CLAUDE.md). Sem o lock, dois ajustes concorrentes na mesma
    # linha se sobrescrevem sem erro nenhum.
    result = await db.execute(
        select(Estoque).where(Estoque.id == estoque_id).with_for_update()
    )
    estoque = result.scalar_one_or_none()
    if not estoque:
        raise HTTPException(404, "Registro de estoque não encontrado")
    estoque.quantidade = quantidade
    await db.commit()
    await db.refresh(estoque)
    return estoque
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/routers/admin.py \
        back-end/commerce-service/tests/test_admin_routes.py
git diff --staged
git commit -m "fix(commerce): floor inventory adjustments at zero and lock the row

quantidade had no ge=0, so an admin could store negative stock; and the
select-then-assign let two concurrent adjustments overwrite each other
silently.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: `nome` e `email` saem do `event_log`

`analytics-service/app/events/consumer.py:35` grava o payload bruto de todo evento. `student.created` carrega `nome` e `email` (`auth-users-service/app/routers/auth.py:92`), então o `analytics_db` acumula nome e e-mail de todo aluno cadastrado, para sempre, sem nenhum endpoint que os leia. Passivo puro.

**Files:**
- Modify: `back-end/analytics-service/app/events/consumer.py`
- Create: `back-end/analytics-service/alembic/versions/<hash>_scrub_pii_from_event_log.py`
- Test: `back-end/analytics-service/tests/test_consumer.py` (novo)

**Interfaces:**
- Consumes: nada novo.
- Produces: `CHAVES_PII: frozenset[str]` e `def _sem_pii(payload: dict) -> dict` no módulo do consumer.

- [ ] **Step 1: Escreva o teste que falha**

Crie `back-end/analytics-service/tests/test_consumer.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from app.events.consumer import handle_event
from app.models.event_log import EventLog


def _fake_message(routing_key: str, payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = routing_key
    message.process = MagicMock(return_value=AsyncMock())
    message.process.return_value.__aenter__ = AsyncMock(return_value=None)
    message.process.return_value.__aexit__ = AsyncMock(return_value=None)
    return message


async def test_student_created_is_logged_without_name_or_email(db_session):
    await handle_event(
        _fake_message(
            "student.created",
            {
                "aluno_id": "00000000-0000-0000-0000-000000000001",
                "nome": "Ana Souza",
                "email": "ana@example.com",
            },
        )
    )

    result = await db_session.execute(select(EventLog))
    registro = result.scalar_one()
    assert registro.payload == {"aluno_id": "00000000-0000-0000-0000-000000000001"}
    assert "nome" not in registro.payload
    assert "email" not in registro.payload


async def test_non_pii_payloads_are_stored_untouched(db_session):
    payload = {
        "pedido_id": 7,
        "aluno_id": "00000000-0000-0000-0000-000000000001",
        "valor_total": 199.9,
    }
    await handle_event(_fake_message("order.created", payload))

    result = await db_session.execute(select(EventLog))
    registro = result.scalar_one()
    assert registro.payload == payload


async def test_staff_created_is_logged_without_name(db_session):
    await handle_event(
        _fake_message(
            "staff.created",
            {
                "user_id": "00000000-0000-0000-0000-000000000002",
                "nome": "Bruno",
                "role": "separador",
            },
        )
    )

    result = await db_session.execute(select(EventLog))
    registro = result.scalar_one()
    assert registro.payload == {
        "user_id": "00000000-0000-0000-0000-000000000002",
        "role": "separador",
    }
```

> Se `tests/test_consumer.py` já existir no analytics-service (ele **não** existe hoje — confira antes com `ls`), acrescente os testes em vez de sobrescrever, e use o helper de mensagem falsa que estiver lá.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/analytics-service && uv run pytest tests/test_consumer.py -v`

Expected: `student_created` e `staff_created` FALHAM — o payload gravado ainda tem `nome`/`email`.

- [ ] **Step 3: Filtre na entrada**

Em `back-end/analytics-service/app/events/consumer.py`, acrescente abaixo de `ROUTING_KEYS`:

```python
# Chaves que nunca entram no log. `student.created` e `staff.created` carregam
# nome e e-mail; este serviço grava payload bruto de todo evento, com retenção
# infinita e sem nenhum endpoint que leia esses campos — era passivo puro.
#
# A lista é de CHAVES, não de eventos: um produtor futuro que mande `email`
# noutro evento também é filtrado, sem precisar lembrar de atualizar nada.
CHAVES_PII: frozenset[str] = frozenset({"nome", "email", "telefone", "documento"})


def _sem_pii(payload: dict) -> dict:
    """Remove as chaves de PII do primeiro nível do payload.

    Só o primeiro nível de propósito: nenhum evento de hoje aninha PII, e
    uma varredura recursiva sobre payload arbitrário é custo por evento sem
    ameaça correspondente. Se um produtor passar a aninhar, o teste que
    cobrir esse evento é quem tem que pegar.
    """
    return {chave: valor for chave, valor in payload.items() if chave not in CHAVES_PII}
```

e troque o corpo de `handle_event`:

```python
async def handle_event(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        tipo = message.routing_key

        async with async_session() as db:
            db.add(EventLog(tipo=tipo, payload=_sem_pii(payload)))
            await db.commit()
```

- [ ] **Step 4: Escreva a migration que apaga o que já está lá**

Run: `cd back-end/analytics-service && uv run alembic revision -m "scrub pii from event_log"`

(Sem `--autogenerate`: não há mudança de schema, só de dado.)

No arquivo gerado:

```python
"""scrub pii from event_log

O consumer passou a filtrar `nome`/`email`/`telefone`/`documento` na
entrada (app/events/consumer.py), mas as linhas já gravadas continuam
carregando o PII. Esta revision as limpa in-place.

Irreversível de propósito: `downgrade` não tem como recuperar o dado
apagado, e não deveria — recuperá-lo seria reintroduzir o passivo.
"""

from alembic import op

revision = "<hash gerado>"
down_revision = "<hash da baseline>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE event_log "
        "SET payload = payload - 'nome' - 'email' - 'telefone' - 'documento' "
        "WHERE payload ?| array['nome', 'email', 'telefone', 'documento']"
    )


def downgrade() -> None:
    # Sem volta: o dado apagado não existe mais em lugar nenhum, e restaurá-lo
    # seria desfazer o próprio objetivo da revision.
    pass
```

> O `?|` do Postgres é o operador "tem alguma destas chaves". Em SQLAlchemy `text()` ele **não** precisa de escape porque não há bind param nenhum aqui — mas se você adicionar um, `?` vira ambíguo com o placeholder do driver. Não adicione: a lista é estática.

- [ ] **Step 5: Aplique e verifique**

```bash
cd back-end/analytics-service && uv run pytest -q
cd ../.. && make stack-up
cd back-end && docker compose exec -T analytics-service uv run alembic upgrade head
docker compose exec -T postgres psql -U edu -d analytics_db -c \
  "SELECT count(*) FROM event_log WHERE payload ?| array['nome','email','telefone','documento'];"
```

Expected: `pytest` PASS; a contagem final é **0**.

- [ ] **Step 6: Confirme que o Alembic ficou em sincronia**

Run: `cd back-end && docker compose exec -T analytics-service uv run alembic revision --autogenerate -m "sync check"`

Expected: a revision gerada tem `upgrade()` e `downgrade()` **vazios** (só `pass`). Apague o arquivo gerado. Se ele não vier vazio, algo divergiu — pare e investigue antes de commitar.

> Constraint 13: esse sync-check só tem significado porque `compare_server_default=True` está no `alembic/env.py` — a fase 1 fechou essa armadilha. Confirme com `grep -n compare_server_default alembic/env.py` antes de confiar no resultado.

- [ ] **Step 7: Commit**

```bash
cd back-end/analytics-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/analytics-service/app/events/consumer.py \
        back-end/analytics-service/alembic/versions/ \
        back-end/analytics-service/tests/test_consumer.py
git diff --staged
git commit -m "fix(analytics): keep personal data out of the event log

student.created and staff.created carry nome and email, and the consumer
stored every payload verbatim with no retention limit and no endpoint
reading those fields. They are now dropped on the way in, and a data
migration scrubs the rows already stored.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# Parte 2 — Limpeza de frota

Nada aqui muda comportamento de rota. Cada task é pequena e independente; se uma for rejeitada na revisão, as outras seguem.

---

### Task 13: `edu-common` recebe os quatro blocos que faltam da receita

`packages/edu-common/pyproject.toml` nunca ganhou `per-file-ignores`, `asyncio_default_fixture_loop_scope`, `asyncio_default_test_loop_scope`, o marker `slow` e `pytest-cov` — e carrega dois `# noqa` escritos à mão que só existem porque `per-file-ignores` está faltando.

**Files:**
- Modify: `back-end/packages/edu-common/pyproject.toml`
- Modify: `back-end/packages/edu-common/tests/test_deps.py:39,44`

**Interfaces:** nenhuma — só configuração.

- [ ] **Step 1: Confirme o estado atual**

Run: `cd back-end/packages/edu-common && grep -n "per-file-ignores\|loop_scope\|markers\|pytest-cov" pyproject.toml`

Expected: nenhuma saída. É isso que esta task corrige.

- [ ] **Step 2: Acrescente os blocos**

Em `back-end/packages/edu-common/pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "httpx>=0.28.0",
]
```

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S", "ASYNC"]
```

```toml
# `Depends(...)` como default de argumento é o idioma do FastAPI, não o
# bug que o B008 procura. `require_role` entra na lista pelo mesmo motivo
# dos serviços: `Depends(auth.require_role("admin"))` é chamada inline por
# design. Sem esta entrada, os testes carregavam `# noqa: B008` à mão.
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends",
    "fastapi.Security",
    "edu_common.deps.AuthDeps.require_role",
]
```

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
# As duas linhas de loop_scope andam juntas. Só a de fixture não basta: o
# default de teste é "function", e um engine criado no loop da sessão
# estoura no segundo teste que tocar recurso compartilhado.
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
    "slow: tests that load a real embeddings model (opt-in)",
]

[tool.coverage.run]
source = ["src/edu_common"]
```

- [ ] **Step 3: Remova os dois `# noqa: B008`**

Em `back-end/packages/edu-common/tests/test_deps.py`, apague ` # noqa: B008` das linhas 39 e 44. **Deixe** os dois `# noqa: S105` de `test_deps.py:11` e `test_security.py:17` — `per-file-ignores` para `tests/**` já cobre `S`, então rode o Step 4 e, se o ruff não reclamar, apague-os também.

- [ ] **Step 4: Rode lint e testes**

Run: `cd back-end/packages/edu-common && uv sync && uv run ruff check . && uv run pytest -q`

Expected: PASS, zero avisos do ruff. Se `B008` reaparecer nas linhas 39/44, o caminho em `extend-immutable-calls` está errado — o ruff casa pelo caminho pontilhado como escrito no código, então confira como `require_role` é chamado no teste e ajuste.

- [ ] **Step 5: Prove que `--strict-markers` está ativo**

Run: `cd back-end/packages/edu-common && uv run pytest -q -m naoexiste`

Expected: erro `Unknown pytest.mark` — que é a prova de que `addopts` foi lido. Se rodar sem erro, o bloco `[tool.pytest.ini_options]` não está sendo carregado.

- [ ] **Step 6: Commit**

```bash
git add back-end/packages/edu-common/pyproject.toml back-end/packages/edu-common/tests/
git diff --staged
git commit -m "refactor(edu-common): converge pyproject on the shared recipe

per-file-ignores, both asyncio loop scopes, the slow marker and
pytest-cov were never applied here, and the two hand-written noqa: B008
existed only because of that.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 14: `asyncio_default_test_loop_scope` no gateway

`api-gateway/pyproject.toml` declara `asyncio_default_fixture_loop_scope = "session"` sem o par obrigatório. Os outros seis serviços declaram os dois, com o comentário explicando por quê.

**Files:**
- Modify: `back-end/api-gateway/pyproject.toml`

- [ ] **Step 1: Acrescente a linha que falta**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
# As duas linhas de loop_scope andam juntas. Só a de fixture não basta: o
# default de teste é "function", e uma fixture de escopo de sessão usada por
# um teste de escopo de função vive num loop diferente do teste — falha que
# só aparece quando o serviço ganha o seu segundo teste assíncrono sobre o
# mesmo recurso, não no primeiro.
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

- [ ] **Step 2: Rode e confirme**

Run: `cd back-end/api-gateway && uv run pytest -q`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add back-end/api-gateway/pyproject.toml
git diff --staged
git commit -m "refactor(gateway): declare the missing asyncio test loop scope

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 15: `chatbot-service` para de whitelistar uma função que não define

`chatbot-service/pyproject.toml` lista `app.dependencies.requer_papel` em `extend-immutable-calls`. O comentário logo acima diz, corretamente, que o serviço **não** usa `requer_papel` — e a entrada está lá mesmo assim. É uma entrada morta que só engana quem lê.

**Files:**
- Modify: `back-end/chatbot-service/pyproject.toml`

- [ ] **Step 1: Confirme que a função de fato não existe**

Run: `cd back-end/chatbot-service && grep -rn "requer_papel\|require_role" app/`

Expected: nenhuma ocorrência em `app/`.

- [ ] **Step 2: Remova a entrada**

Confira o bloco `[tool.ruff.lint.flake8-bugbear]` — se `"app.dependencies.requer_papel"` estiver na lista, remova essa linha. O comentário acima do bloco já explica a ausência e fica como está.

> **Se `grep` do Step 1 achar `requer_papel` em `app/`, esta task muda de sinal:** a entrada não é morta, e o backlog está errado. Nesse caso, não remova nada — anote o achado no relatório da task e siga.

- [ ] **Step 3: Rode e confirme**

Run: `cd back-end/chatbot-service && uv run ruff check . && uv run pytest -q`

Expected: PASS, zero `B008` novo.

- [ ] **Step 4: Commit**

```bash
git add back-end/chatbot-service/pyproject.toml
git diff --staged
git commit -m "refactor(chatbot): drop the bugbear whitelist for a dependency it never defines

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 16: `httpx` sai das dependências de runtime

`learning-service`, `commerce-service` e `notification-service` declaram `httpx>=0.28.0` em `[project].dependencies`, mas nenhum dos três o importa fora de teste. A imagem de produção carrega uma biblioteca HTTP que ninguém usa.

**Files:**
- Modify: `back-end/learning-service/pyproject.toml`
- Modify: `back-end/commerce-service/pyproject.toml`
- Modify: `back-end/notification-service/pyproject.toml`
- Modify: os três `uv.lock` correspondentes

**Interfaces:** nenhuma.

> **Nota de sequência:** o bloco C acrescenta `commerce-service/app/services/auth_client.py`, que **usa** `httpx` em runtime. Ele terá que devolver a dependência ao grupo de runtime do commerce. Isso é esperado e está registrado no plano C — mover agora continua certo, porque hoje é mentira.

- [ ] **Step 1: Confirme que os três só usam em teste**

Run:
```bash
cd back-end && for s in learning-service commerce-service notification-service; do
  echo "→ $s"; grep -rn "httpx" $s/app/ || echo "   (nada em app/)"
done
```

Expected: `(nada em app/)` nos três. **Se algum tiver import em `app/`, tire-o da task** e diga por quê no relatório.

- [ ] **Step 2: Mova a declaração**

Em cada um dos três `pyproject.toml`: remova a linha `"httpx>=0.28.0",` de `[project].dependencies` e acrescente-a a `[dependency-groups].dev`.

- [ ] **Step 3: Regenere os lockfiles**

Run:
```bash
cd back-end && for s in learning-service commerce-service notification-service; do
  (cd $s && uv sync) || exit 1
done
```

- [ ] **Step 4: Rode as três suítes**

Run: `cd back-end && for s in learning-service commerce-service notification-service; do (cd $s && uv run pytest -q) || exit 1; done`

Expected: PASS nas três — `httpx` continua disponível porque o conftest o usa e ele está no grupo dev.

- [ ] **Step 5: Confirme que a imagem ainda sobe**

Run: `cd back-end && docker compose build learning-service commerce-service notification-service && docker compose up -d && docker compose ps`

Expected: os três containers saudáveis. **Constraint 17:** `docker ps` saudável não é prova — confirme com `curl -s localhost:8102/health`, `localhost:8103/health` e `localhost:8105/health` (confira as portas em `back-end/docker-compose.yml` antes).

- [ ] **Step 6: Commit**

```bash
git add back-end/learning-service/pyproject.toml back-end/learning-service/uv.lock \
        back-end/commerce-service/pyproject.toml back-end/commerce-service/uv.lock \
        back-end/notification-service/pyproject.toml back-end/notification-service/uv.lock
git diff --staged
git commit -m "refactor(deps): move httpx to the dev group where nothing imports it

learning, commerce and notification declared httpx as a runtime
dependency and only ever used it in tests, so the production images
carried an HTTP client nobody called.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 17: uma variante só de `Dockerfile.dockerignore`

Seis serviços compartilham o mesmo arquivo (md5 `f793b29e...`); o `analytics-service` tem outro, incompatível. O do analytics usa padrões **sem** o prefixo `**/` em `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache` e `.git` — e a armadilha 6 da fase 1 registra exatamente isso: padrão de `.dockerignore` sem `**/` não casa em subdiretório.

**Files:**
- Modify: `back-end/analytics-service/Dockerfile.dockerignore`

- [ ] **Step 1: Confirme a divergência**

Run: `cd back-end && md5sum */Dockerfile.dockerignore`

Expected: seis hashes iguais e o do `analytics-service` diferente.

- [ ] **Step 2: Adote a variante compartilhada**

Run: `cd back-end && cp commerce-service/Dockerfile.dockerignore analytics-service/Dockerfile.dockerignore`

- [ ] **Step 3: Confirme que não sobrou nada exclusivo do analytics**

Run: `cd back-end && git diff analytics-service/Dockerfile.dockerignore`

Leia o diff: qualquer padrão que **saiu** e era específico do analytics (um diretório de modelo, um artefato de build próprio) precisa voltar ao arquivo novo. Os padrões que saíram na leitura da fase 1 eram só as variantes sem `**/` dos mesmos diretórios — mas confira, não assuma.

- [ ] **Step 4: Confirme que a imagem ainda sobe e que o contexto encolheu**

Run:
```bash
cd back-end && docker compose build analytics-service
docker compose up -d analytics-service && curl -s localhost:8106/health
```

Expected: build OK e `{"status":"ok"}`. (Confira a porta real em `docker-compose.yml`.)

- [ ] **Step 5: Commit**

```bash
git add back-end/analytics-service/Dockerfile.dockerignore
git diff --staged
git commit -m "refactor(analytics): use the shared dockerignore

The analytics variant declared .venv/__pycache__/.git without the **/
prefix, which does not match in subdirectories — trap 6 from phase 1. Six
services already shared one file; now seven do.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 18: testes de health que testam health

Três arquivos chamados `test_health.py` não tocam `/health` — testam `/openapi.json` e prefixos de rota. Quatro serviços não têm nenhum teste do próprio `/health` (`api-gateway` e `chatbot-service` testam de raspão dentro de outro arquivo; `analytics-service` e `notification-service` não testam).

**Files:**
- Rename: `{auth-users,commerce,learning}-service/tests/test_health.py` → `tests/test_openapi.py`
- Create: `{api-gateway,auth-users,commerce,learning,notification,analytics,chatbot}-service/tests/test_health.py`

**Interfaces:** nenhuma — só testes.

- [ ] **Step 1: Confirme o estado**

Run: `cd back-end && ls */tests/test_health.py && grep -rn '"/health"' */tests/ | grep -v legacy`

Expected: três `test_health.py` (auth, commerce, learning), nenhum deles batendo em `/health`; e duas batidas incidentais em `api-gateway/tests/test_proxy.py:28` e `chatbot-service/tests/test_chat_routes.py:50`.

- [ ] **Step 2: Renomeie os três**

Run:
```bash
cd back-end && for s in auth-users-service commerce-service learning-service; do
  git mv $s/tests/test_health.py $s/tests/test_openapi.py
done
```

- [ ] **Step 3: Escreva o teste de health, um por serviço**

Crie `tests/test_health.py` nos **sete** serviços, com este corpo (idêntico em todos, ajustando só o docstring se o serviço tiver algo a dizer):

```python
async def test_health_returns_ok(client):
    """`/health` é o que o compose usa como healthcheck. Ele não pode
    depender de nenhum router — se um import de router quebrar, este teste
    tem que continuar sendo a coisa que responde."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Confira o corpo real que cada `/health` devolve antes de assertar (`grep -n -A3 'def health' <servico>/app/main.py`) — se algum devolver outra coisa, o teste asserta o que o serviço devolve, não o que este plano supõe.

- [ ] **Step 4: Retire a batida incidental do `test_proxy.py`**

Em `back-end/api-gateway/tests/test_proxy.py:28`, o teste que bate em `/health` agora tem um lar próprio. Se aquele teste for **só** sobre health, apague-o de lá (o novo `test_health.py` o cobre). Se ele testa outra coisa e usa `/health` como caminho conveniente, deixe-o. Leia antes de decidir. Mesma leitura para `chatbot-service/tests/test_chat_routes.py:50`.

- [ ] **Step 5: Rode tudo**

Run: `make services-test`

Expected: PASS nos oito alvos (`packages/edu-common` incluído).

- [ ] **Step 6: Commit**

```bash
git add back-end/*/tests/test_health.py back-end/*/tests/test_openapi.py \
        back-end/api-gateway/tests/test_proxy.py back-end/chatbot-service/tests/test_chat_routes.py
git diff --staged
git commit -m "test(fleet): give every service a health test that tests health

Three files named test_health.py exercised /openapi.json and route
prefixes instead; they are now test_openapi.py. All seven services get a
real /health test — the endpoint the compose healthcheck depends on.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 19: um nome só para a dependência de aluno autenticado

`edu-common` exporta `get_current_user_id`. Cada serviço a reexporta com um nome diferente: `get_current_student_id` (commerce, learning), `get_current_student` (chatbot). Três nomes, uma função.

**Files:**
- Modify: `back-end/{commerce,learning,chatbot,notification,analytics,auth-users}-service/app/dependencies.py`
- Modify: todos os routers que importam o nome antigo
- Modify: os testes que importam o nome antigo

**Interfaces:**
- Produces: **`get_current_user_id`** é o nome canônico em todo serviço, igual ao do `edu-common`. `get_current_user` e `requer_papel` ficam como estão.

- [ ] **Step 1: Levante todos os usos**

Run: `cd back-end && grep -rn "get_current_student_id\|get_current_student\b" --include='*.py' . | grep -v legacy`

Anote arquivo e linha de cada um. Este é o escopo exato da task.

- [ ] **Step 2: Renomeie no `dependencies.py` de cada serviço**

Em cada `app/dependencies.py` que tiver a linha, troque:

```python
get_current_student_id = _auth.get_current_user_id
```

por:

```python
# Mesmo nome do `edu-common` de propósito: os serviços tinham três nomes
# (`get_current_student_id`, `get_current_student`, `get_current_user_id`)
# para a mesma função, e a leitura de qualquer router exigia lembrar qual
# convenção aquele serviço adotou.
get_current_user_id = _auth.get_current_user_id
```

(No chatbot, o nome antigo é `get_current_student`.)

- [ ] **Step 3: Atualize os chamadores**

Run: `cd back-end && grep -rln "get_current_student_id\|get_current_student\b" --include='*.py' . | grep -v legacy | xargs sed -i 's/get_current_student_id/get_current_user_id/g; s/get_current_student\b/get_current_user_id/g'`

Depois **releia cada diff**: `sed` não distingue um nome de dependência de uma palavra dentro de um docstring ou comentário. Onde o texto explicava a dependência, o novo nome está certo; onde ele falava do aluno como pessoa, o `sed` estragou a frase — conserte à mão.

- [ ] **Step 4: Rode tudo**

Run: `make services-test && make services-lint`

Expected: PASS. Um `ImportError` aqui significa um chamador que o `grep` não pegou (import indireto, string em `monkeypatch.setattr`) — procure por ele com `grep -rn "get_current_student"` de novo.

- [ ] **Step 5: Commit**

```bash
git add back-end/
git diff --staged
git commit -m "refactor(fleet): use one name for the authenticated-user dependency

edu-common exports get_current_user_id; the services re-exported it as
get_current_student_id and get_current_student. Three names for one
function meant reading a router required remembering which convention its
service picked.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 20: `sessionmaker` legado → `async_sessionmaker`

Os cinco serviços com banco usam `sessionmaker(engine, class_=AsyncSession, ...)` em `app/database.py`, enquanto os conftests já usam `async_sessionmaker`. O primeiro é a forma legada do SQLAlchemy 1.4; ele funciona, mas não tipa e o `class_=` é o sintoma.

**Files:**
- Modify: `back-end/{auth-users,learning,commerce,notification,analytics}-service/app/database.py`

**Interfaces:**
- Produces: `async_session: async_sessionmaker[AsyncSession]` em cada `app/database.py`. O nome da variável **não muda** — `app/scheduler.py`, os consumers e os routers importam `async_session` e continuam funcionando.

- [ ] **Step 1: Confirme o alvo**

Run: `cd back-end && grep -n "sessionmaker" */app/database.py | grep -v legacy`

Expected: cinco linhas de import e cinco de uso.

- [ ] **Step 2: Troque em cada um dos cinco**

Em cada `app/database.py`:

```python
from sqlalchemy.orm import declarative_base, sessionmaker
...
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

vira:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import declarative_base
...
# `async_sessionmaker` é a fábrica tipada do SQLAlchemy 2.x. O
# `sessionmaker(..., class_=AsyncSession)` que estava aqui é a forma da 1.4:
# funciona, mas devolve `sessionmaker` sem parâmetro de tipo, então nada
# checa que `async_session()` produz uma `AsyncSession`. Os conftests já
# usavam a forma nova — só `app/database.py` ficou para trás.
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

Confira o import de `AsyncSession` em cada arquivo: se ele só existia para o `class_=`, o ruff vai acusar `F401` — remova. Se `get_db` o usa na anotação, deixe.

- [ ] **Step 3: Rode tudo**

Run: `make services-test && make services-lint`

Expected: PASS.

- [ ] **Step 4: Confirme que o consumer e o scheduler continuam abrindo sessão**

Run: `cd back-end && docker compose up -d && docker compose logs --tail=50 notification-service analytics-service learning-service`

Expected: nenhum `TypeError`/`AttributeError` no start. **Constraint 17:** se você editou arquivos com os containers de pé, `docker compose restart` antes de ler os logs.

- [ ] **Step 5: Commit**

```bash
git add back-end/*/app/database.py
git diff --staged
git commit -m "refactor(fleet): use async_sessionmaker in the five service databases

sessionmaker(..., class_=AsyncSession) is the 1.4 form: it works but
returns an untyped factory. The conftests already used the 2.x one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 21: entrada morta `"addresses"` no `SERVICE_MAP`

`api-gateway/app/routing.py` mapeia `"addresses" -> "auth"`. Ninguém serve `/addresses`: os dois backends montam `/auth/addresses`, que o gateway já resolve pelo primeiro segmento `auth`. A entrada só faz `/api/addresses/...` virar um 404 do auth-users-service em vez de um 404 honesto do gateway com a mensagem que aponta para `app/routing.py`.

**Files:**
- Modify: `back-end/api-gateway/app/routing.py`
- Test: `back-end/api-gateway/tests/test_routing.py`

- [ ] **Step 1: Confirme que ninguém serve `/addresses`**

Run: `cd back-end && grep -rn 'prefix="/addresses"\|APIRouter(prefix="/addresses' --include='*.py' . | grep -v legacy && grep -rn 'prefix=' auth-users-service/app/routers/addresses.py`

Expected: o router de endereços monta `/auth/addresses`, e nada monta `/addresses`.

- [ ] **Step 2: Escreva o teste**

Em `back-end/api-gateway/tests/test_routing.py`:

```python
def test_addresses_is_not_a_top_level_route():
    """Ninguém serve `/addresses` — os dois backends montam `/auth/addresses`,
    que já resolve pelo primeiro segmento `auth`. Mapear o segmento solto
    trocava um 404 do gateway (com a dica de app/routing.py) por um 404 do
    auth-users-service, que não diz nada a quem está depurando."""
    assert resolve_destination("addresses/123") is None


def test_auth_addresses_still_resolves_to_the_auth_service():
    destino = resolve_destination("auth/addresses/123")
    assert destino is not None
    base_url, final_path = destino
    assert final_path == "/auth/addresses/123"
```

- [ ] **Step 3: Rode e confirme que falha**

Run: `cd back-end/api-gateway && uv run pytest tests/test_routing.py -k "addresses" -v`

Expected: o primeiro FALHA (devolve uma tupla, não `None`).

- [ ] **Step 4: Remova a entrada**

Em `back-end/api-gateway/app/routing.py`, apague a linha `"addresses": "auth",` do `SERVICE_MAP`.

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd back-end/api-gateway && uv run pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add back-end/api-gateway/app/routing.py back-end/api-gateway/tests/test_routing.py
git diff --staged
git commit -m "refactor(gateway): drop the dead addresses entry from SERVICE_MAP

Nothing serves /addresses; both backends mount /auth/addresses, which the
auth segment already resolves. The entry only swapped the gateway's
pointer-to-routing.py 404 for a silent one from auth-users-service.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 22: `cors_origins` declarado e não lido no auth-users-service

`auth-users-service/app/config.py:19` declara `cors_origins: list[str]` e nenhum middleware o consome. O CORS é do gateway (`api-gateway/app/main.py:14-20`), que é quem o browser alcança; as portas 8101-8106 são de desenvolvimento.

**Files:**
- Modify: `back-end/auth-users-service/app/config.py`
- Modify: `back-end/auth-users-service/.env.example` (se declarar `CORS_ORIGINS`)

> **NÃO TOQUE em `commerce-service/app/config.py:17` (`google_maps_api_key`).** Ele também está na lista de "declarado e não lido" do backlog, e também parece morto — mas o bloco C passa a lê-lo em `GET /orders/{id}/route`. Removê-lo agora força o bloco C a reintroduzi-lo. Veja o aviso no topo deste plano.

- [ ] **Step 1: Confirme que nada o lê**

Run: `cd back-end && grep -rn "cors_origins\|CORSMiddleware" auth-users-service/`

Expected: só a declaração em `app/config.py`. Nenhum `add_middleware`.

- [ ] **Step 2: Remova a declaração**

Em `back-end/auth-users-service/app/config.py`, apague a linha `cors_origins: list[str] = ["http://localhost:3000"]`.

`model_config` tem `extra="ignore"`, então um `CORS_ORIGINS` que continue no ambiente é ignorado sem erro. Se `.env.example` declarar `CORS_ORIGINS=`, apague a linha também.

- [ ] **Step 3: Escreva o comentário que impede a volta**

Acrescente logo acima do fim da classe `Settings`:

```python
    # Sem `cors_origins` aqui de propósito: CORS é do gateway
    # (`api-gateway/app/main.py`), que é quem o browser alcança. As portas
    # 8101-8106 existem só para desenvolvimento e não recebem tráfego de
    # browser. O campo estava declarado e nenhum middleware o lia.
```

- [ ] **Step 4: Rode e confirme**

Run: `cd back-end/auth-users-service && uv run pytest -q && cd ../.. && cd back-end && docker compose up -d auth-users-service && curl -s localhost:8101/health`

Expected: PASS e `{"status":"ok"}`. (Confira a porta em `docker-compose.yml`.)

- [ ] **Step 5: Commit**

```bash
git add back-end/auth-users-service/app/config.py back-end/auth-users-service/.env.example
git diff --staged
git commit -m "refactor(auth): drop the cors_origins setting nothing reads

CORS belongs to the gateway, which is what a browser reaches. The field
was declared here with no middleware consuming it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 23: `/subtopics/{id}/questions` usa `limit` e ganha `offset`

`learning-service/app/routers/materias.py:109` chama o parâmetro de `limite` — o único em português entre os sete serviços — e não tem `offset`. A fase 1 traduziu os paths deste serviço e deixou este query param para trás.

**Files:**
- Modify: `back-end/learning-service/app/routers/materias.py:106-131`
- Test: `back-end/learning-service/tests/test_subjects_routes.py`

**Interfaces:**
- Produces: `GET /subtopics/{subtema_id}/questions?limit=&offset=`. `limit` mantém default 8 e teto 50; `offset` entra com default 0 e `ge=0`.

> Isto **muda um contrato público**, mas de uma rota que o Flutter não consome (o app usa `/topics/{id}/quiz`). Confirme antes de mudar: `grep -rn "subtopics" front-end-flutter/lib`. Se houver uso, pare e reporte.

- [ ] **Step 1: Confirme que o Flutter não usa**

Run: `cd /home/elias/programming/fiap/estuda_app && grep -rn "subtopics" front-end-flutter/lib`

Expected: nenhuma ocorrência. **Se houver, esta task sai do bloco A** — vira decisão de contrato e volta para o spec.

- [ ] **Step 2: Escreva o teste que falha**

```python
async def test_subtopic_questions_paginate_with_limit_and_offset(
    client, db_session, auth_headers
):
    subtema, questoes = await _seed_subtema_com_questoes(db_session, quantidade=5)

    primeira = await client.get(
        f"/subtopics/{subtema.id}/questions?limit=2&offset=0", headers=auth_headers
    )
    segunda = await client.get(
        f"/subtopics/{subtema.id}/questions?limit=2&offset=2", headers=auth_headers
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert len(primeira.json()) == 2
    assert len(segunda.json()) == 2
    ids_primeira = {q["id"] for q in primeira.json()}
    ids_segunda = {q["id"] for q in segunda.json()}
    assert ids_primeira.isdisjoint(ids_segunda)


async def test_subtopic_questions_reject_a_negative_offset(client, db_session, auth_headers):
    subtema, _ = await _seed_subtema_com_questoes(db_session, quantidade=1)
    response = await client.get(
        f"/subtopics/{subtema.id}/questions?offset=-1", headers=auth_headers
    )
    assert response.status_code == 422
```

Leia `test_subjects_routes.py` antes: se ele já tiver um seed de subtema com questões, use o nome de lá. Se não, escreva este no topo do arquivo:

```python
async def _seed_subtema_com_questoes(db_session, *, quantidade: int) -> tuple[Subtema, list[Questao]]:
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db_session.add(subtema)
    await db_session.flush()

    questoes = [
        Questao(
            subtema_id=subtema.id,
            enunciado=f"Pergunta {i}",
            alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
            gabarito="A",
            nivel_dificuldade=1,
        )
        for i in range(quantidade)
    ]
    db_session.add_all(questoes)
    await db_session.commit()
    for q in questoes:
        await db_session.refresh(q)
    return subtema, questoes
```

Chame-o com `quantidade` nomeado (`_seed_subtema_com_questoes(db_session, quantidade=5)`), como os testes acima fazem.

- [ ] **Step 3: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_subjects_routes.py -k "paginate_with_limit_and_offset or negative_offset" -v`

Expected: FALHAM — `limit` é ignorado (o nome é `limite`), então a rota devolve 5 nos dois casos.

- [ ] **Step 4: Traduza e pagine**

Em `back-end/learning-service/app/routers/materias.py`:

```python
@router.get("/subtopics/{subtema_id}/questions")
async def listar_questoes_diagnostico(
    subtema_id: int,
    limit: int = Query(8, ge=1, le=50),
    offset: int = Query(0, ge=0),
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Questionário focado em UM único subtema (ex: só "Membrana Plasmática"),
    útil para prática pontual — diferente de `/topics/{id}/quiz`, que cobre
    o tema inteiro. Não retorna o gabarito para o cliente.

    `order_by(Questao.id)` é obrigatório com `offset`: sem ordem declarada o
    Postgres não garante ordem estável entre páginas, e a mesma questão pode
    aparecer nas duas — ou em nenhuma.
    """
    result = await db.execute(
        select(Questao)
        .where(Questao.subtema_id == subtema_id)
        .order_by(Questao.id)
        .limit(limit)
        .offset(offset)
    )
```

O resto do corpo fica como está.

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest -q`

Expected: PASS. Se `test_health.py`/`test_openapi.py` do learning tinha um teste travando "nenhum segmento em português no path", ele continua verde — `limite` é query param, não segmento. Considere estendê-lo para query params num commit separado.

- [ ] **Step 6: Commit**

```bash
cd back-end/learning-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/learning-service/app/routers/materias.py \
        back-end/learning-service/tests/test_subjects_routes.py
git diff --staged
git commit -m "refactor(learning): rename limite to limit and paginate subtopic questions

The last Portuguese query param in the seven services, and the only
listing without offset. Ordering by id is what makes the offset stable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 24: um jeito só de dizer "sem status" no analytics

`GET /analytics/deliveries` devolve `StatusContagemOut.status: str | None` — `null` em JSON. `GET /analytics/executive-summary` devolve `pedidos_por_status: dict[str, int]` com a sentinela `"sem_status"`. Mesma ausência, duas representações, na mesma API.

A sentinela é a forma certa: JSON não admite chave nula, então o dicionário do executive-summary **não pode** usar `null` — e uma chave `null` no array de `/deliveries` obriga todo cliente a tratar dois casos. `/deliveries` adota a sentinela.

**Files:**
- Modify: `back-end/analytics-service/app/routers/analytics.py:67-86`
- Modify: `back-end/analytics-service/app/schemas/analytics.py:24-26`
- Test: `back-end/analytics-service/tests/test_analytics_routes.py`

**Interfaces:**
- Produces: `StatusContagemOut.status: str` (não mais `str | None`). `/analytics/deliveries` devolve `"sem_status"` onde antes devolvia `null`.
- `SEM_CHAVE_STATUS` deixa de ser privado do executive-summary e passa a valer para as duas rotas.

> Isto muda um contrato público. Ninguém no Flutter consome `/analytics` (é rota de admin, `requer_papel("admin")`) — confirme com `grep -rn "analytics" front-end-flutter/lib` antes.

- [ ] **Step 1: Confirme que o Flutter não consome analytics**

Run: `cd /home/elias/programming/fiap/estuda_app && grep -rn "analytics" front-end-flutter/lib`

Expected: nenhuma ocorrência. Se houver, pare e reporte.

- [ ] **Step 2: Escreva o teste que falha**

```python
async def test_deliveries_reports_a_missing_status_as_the_sentinel(client, db_session):
    """Um `order.status_changed` sem a chave `status` no payload."""
    db_session.add(
        EventLog(tipo="order.status_changed", payload={"pedido_id": 1, "aluno_id": "x"})
    )
    await db_session.commit()

    response = await client.get("/analytics/deliveries", headers=headers_for("admin"))

    assert response.status_code == 200
    linhas = response.json()
    assert len(linhas) == 1
    assert linhas[0]["status"] == "sem_status"


async def test_deliveries_and_executive_summary_agree_on_the_sentinel(client, db_session):
    db_session.add(
        EventLog(tipo="order.status_changed", payload={"pedido_id": 1, "aluno_id": "x"})
    )
    await db_session.commit()

    deliveries = await client.get("/analytics/deliveries", headers=headers_for("admin"))
    resumo = await client.get("/analytics/executive-summary", headers=headers_for("admin"))

    chave_deliveries = deliveries.json()[0]["status"]
    chaves_resumo = list(resumo.json()["metricas"]["pedidos_por_status"].keys())
    assert chave_deliveries in chaves_resumo
```

- [ ] **Step 3: Rode e confirme que falha**

Run: `cd back-end/analytics-service && uv run pytest tests/test_analytics_routes.py -k "sentinel" -v`

Expected: FALHAM — `/deliveries` devolve `null`.

- [ ] **Step 4: Aplique a sentinela nas duas rotas**

Em `back-end/analytics-service/app/schemas/analytics.py`:

```python
class StatusContagemOut(BaseModel):
    """`status` nunca é nulo.

    `EventLog.payload["status"].astext` devolve NULL quando o payload logado
    não traz a chave — este serviço grava payload bruto de outros serviços e
    não controla o formato. As duas rotas que agrupam por status resolvem
    esse NULL na origem com a MESMA sentinela (`SEM_CHAVE_STATUS`), porque
    `/executive-summary` agrupa num `dict[str, int]` e JSON não admite chave
    nula. Manter `str | None` aqui deixava a mesma ausência com duas formas
    na mesma API.
    """

    status: str
    total: int
```

Em `back-end/analytics-service/app/routers/analytics.py`, na `metricas_entregas`:

```python
    return [
        StatusContagemOut(status=row.status or SEM_CHAVE_STATUS, total=row.total)
        for row in result.all()
    ]
```

e atualize o docstring de `metricas_entregas` para mencionar a sentinela.

Atualize também o docstring de `ResumoMetricasOut` (schemas/analytics.py:35-42), que hoje explica a sentinela como se ela fosse exclusiva do executive-summary — constraint 16.

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd back-end/analytics-service && uv run pytest -q`

Expected: PASS. Se algum teste antigo assertava `status is None`, ele travava a divergência — atualize-o.

- [ ] **Step 6: Commit**

```bash
cd back-end/analytics-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/analytics-service/app/routers/analytics.py \
        back-end/analytics-service/app/schemas/analytics.py \
        back-end/analytics-service/tests/test_analytics_routes.py
git diff --staged
git commit -m "refactor(analytics): report a missing status one way across the API

/deliveries returned JSON null and /executive-summary returned the
sem_status sentinel for the same absence. The dict in executive-summary
cannot use null, so /deliveries adopts the sentinel.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

# Parte 3 — Portão de saída

---

### Task 25: portão do bloco A e sondagem para o bloco C

Nenhuma mudança de código. Este é o portão que o spec chama de "check de sincronia como portão de cada bloco", mais a **medição** de que o bloco C precisa antes de escrever a migration de reconstrução.

**Files:** nenhum de produção. Produz um relatório.

- [ ] **Step 1: Suíte e lint em toda a frota**

Run: `make services-test && make services-lint`

Expected: PASS nos oito alvos. Anote a contagem de testes por serviço — o bloco B e o C vão comparar contra ela.

- [ ] **Step 2: Sync-check do Alembic nos cinco serviços com banco**

```bash
cd back-end && make stack-up
for s in auth-users-service learning-service commerce-service notification-service analytics-service; do
  echo "→ $s"
  docker compose exec -T $s uv run alembic upgrade head
  docker compose exec -T $s uv run alembic revision --autogenerate -m "sync check $s"
done
```

Para cada um: abra a revision gerada e confirme que `upgrade()` e `downgrade()` estão **vazios**. Apague os cinco arquivos gerados.

> **Constraint 13.** Este check só significa alguma coisa porque `compare_server_default=True` está nos cinco `alembic/env.py`. Confirme primeiro:
> `cd back-end && grep -l compare_server_default */alembic/env.py | wc -l` → tem que dar **5**.
> Se der menos, o check é cego para default de banco e o resultado não vale nada — que é exatamente o que aconteceu na fase 1 inteira.

- [ ] **Step 3: Prove que os sete serviços de fato servem**

```bash
cd back-end && docker compose ps
for p in 8100 8101 8102 8103 8104 8105 8106; do
  echo -n "$p: "; curl -s -m 3 "localhost:$p/health" || echo "SEM RESPOSTA"
done
```

Expected: `{"status":"ok"}` nos sete. **Constraint 17:** `docker compose ps` dizendo `healthy` não é prova — o watcher `--reload` do granian trava se arquivos sumiram debaixo dele durante as tasks acima. Se algum não responder, `docker compose restart <svc>` e tente de novo.

Confira as portas reais em `back-end/docker-compose.yml` antes de confiar na lista acima.

- [ ] **Step 4: Meça `commerce_db` — a sondagem que o bloco C precisa**

O spec registra a estratégia da migration do bloco C como **suposição verificável**: "o `commerce_db` nunca teve dado de produção, então a migration é uma reconstrução declarada". Meça agora, enquanto o stack está de pé:

```bash
cd back-end && docker compose exec -T postgres psql -U edu -d commerce_db -c "
  SELECT 'produtos' AS tabela, count(*) FROM produtos
  UNION ALL SELECT 'pedidos', count(*) FROM pedidos
  UNION ALL SELECT 'pedido_itens', count(*) FROM pedido_itens
  UNION ALL SELECT 'pedido_status_historico', count(*) FROM pedido_status_historico
  UNION ALL SELECT 'ocorrencias', count(*) FROM ocorrencias
  UNION ALL SELECT 'estoque', count(*) FROM estoque
  UNION ALL SELECT 'fornecedores', count(*) FROM fornecedores;
"
```

Registre a saída literal no relatório da task.

- **Se todas as contagens forem 0:** a suposição do spec está confirmada. O bloco C escreve a migration como reconstrução declarada.
- **Se qualquer contagem for > 0:** a suposição está **errada**. Não prossiga para o bloco C sem levar isso ao autor do spec — a migration vira preservadora (`ALTER` com conversão de tipo de PK, `USING`, backfill) e o custo do bloco C sobe.

- [ ] **Step 5: Relate**

Escreva um relatório curto com: contagem de testes por serviço, resultado dos cinco sync-checks, resultado dos sete `/health`, e a tabela de contagem do `commerce_db` com o veredito da suposição.

Nada a commitar. Se o Step 4 contradisse o spec, o bloco B pode começar assim mesmo (ele não depende disso); o bloco C, não.

---

## Notas de sequência para os outros blocos

- **Task 16** tira `httpx` do runtime do commerce. O **bloco C** o devolve, porque `auth_client.py` o usa de verdade.
- **Task 22** deixa `google_maps_api_key` de pé no commerce de propósito. O **bloco C** é quem passa a lê-lo.
- **Task 19** renomeia a dependência para `get_current_user_id` em todo serviço. Os planos **B**, **C** e **D** usam esse nome, não os antigos.
- **Task 25 / Step 4** é pré-requisito do **bloco C**, não do B.
