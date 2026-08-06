"""Testes de rota para `/diagnostic`, `/recommendations`, `/reviews`.

Estes quatro testes vêm do brief da task 9 sem alteração — os endpoints já
exigiam autenticação antes desta task (só o path mudou de português para
inglês), então "sem header -> 403" continua batendo direto, sem nenhum
outro parâmetro inválido competindo pela resposta.

Os dois testes adicionais no final cobrem o segundo achado do review da
task anterior que estava no escopo desta task: `GET
/recommendations/related/{id}` não tinha nenhum controle de acesso.

Fix round 1 acrescenta: um teste de vazamento honesto (com dado real
seedado) para `get_recomendacao`, e dois testes travando a validação de
`k` em `get_subtemas_relacionados` (SPEC ❌ 2).
"""

from datetime import UTC, datetime, timedelta

from app.models.progresso import AlunoTemaProgresso
from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema


async def test_answer_requires_authentication(client):
    response = await client.post("/diagnostic/answer", json={"tema_id": 1, "respostas": []})
    assert response.status_code == 403


async def test_question_context_requires_authentication(client):
    assert (await client.get("/diagnostic/questions/1/context")).status_code == 403


async def test_recommendations_require_authentication(client):
    assert (await client.get("/recommendations?tema_id=1")).status_code == 403


async def test_reviews_today_requires_authentication(client):
    assert (await client.get("/reviews/today")).status_code == 403


async def test_related_subtopics_require_authentication(client):
    assert (await client.get("/recommendations/related/1")).status_code == 403


async def test_recommendation_response_never_leaks_the_internal_ai_description(
    client, auth_headers, db_session
):
    """`get_recomendacao` costumava devolver o objeto `Subtema` do SQLAlchemy
    cru (achado do review da task anterior) — o que vazava `descricao_ia`
    (texto interno só para o classificador de IA, nunca exibido ao aluno)
    na resposta JSON.

    Fix round 1 (IMPORTANT 3): a versão anterior deste teste consultava um
    `tema_id` inexistente (999999) e só verificava `status_code == 200` e
    `response.json() is None` — isso passa IGUAL contra o código pré-fix
    (`return subtema`, com `subtema is None` serializado como `null` em
    ambos os casos), então não provava nada sobre o vazamento. Este teste
    seed a real `Subtema` com `descricao_ia` preenchido, consulta o
    `tema_id` real (garantindo que `proximo_subtema` de fato o encontre e
    a construção de `SubtemaRecomendadoOut` em recomendacao.py:25-32
    rode), e verifica o corpo da resposta campo a campo.

    Provado não-vácuo revertendo temporariamente `get_recomendacao` para
    `return subtema` (o código pré-fix): o teste falha porque o encoder
    default do FastAPI inclui `descricao_ia` no JSON — ver "Fix round 1"
    no relatório da task para a evidência exata. Revertido antes do commit.
    """
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    db_session.add(
        Subtema(tema_id=tema.id, nome="Membrana", ordem=1, descricao_ia="segredo interno de IA")
    )
    await db_session.commit()

    response = await client.get(f"/recommendations?tema_id={tema.id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": body["id"],
        "tema_id": tema.id,
        "nome": "Membrana",
        "ordem": 1,
        "videoaula_base_url": None,
        "videoaula_revisao_url": None,
    }


async def test_related_subtopics_k_has_a_hard_cap(client, auth_headers):
    """SPEC ❌ 2: `k` era um `int` puro sem `Query(ge=/le=)` — sem cap,
    `?k=100000` fazia `recomendacao_semantica.py` rankear o catálogo
    inteiro de subtemas via `NearestNeighbors(n_neighbors=<todas as
    linhas>)` a cada chamada.
    """
    response = await client.get("/recommendations/related/1?k=100000", headers=auth_headers)
    assert response.status_code == 422


async def test_related_subtopics_negative_k_is_a_validation_error_not_a_503(client, auth_headers):
    """SPEC ❌ 2, defeito secundário: sem `ge=1`, `k=-5` chegava ao corpo do
    endpoint, `k_efetivo = k + 1 = -4` estourava dentro de
    `NearestNeighbors.fit`, e o `except Exception` amplo em
    `recomendacao.py` convertia isso num 503 enganoso ("serviço
    indisponível") em vez de um 422 de requisição inválida. Com
    `Query(ge=1)`, a validação agora acontece antes do corpo rodar.
    """
    response = await client.get("/recommendations/related/1?k=-5", headers=auth_headers)
    assert response.status_code == 422


async def test_reviews_today_listing_has_a_default_cap_and_offset(
    client, db_session, student_identity
):
    """SPEC ❌ 1: `/reviews/today` não tinha `limit`/`offset` — a query era
    um `select(...).join(...)` sem teto, crescendo com o histórico de
    estudo do aluno. Seed 55 revisões vencidas para o MESMO aluno
    (`student_identity.aluno_id`, para que o filtro `aluno_id == ...` da
    rota realmente as encontre) e prova o cap de 50 + que `offset` alcança
    o restante, sem sobreposição entre páginas.
    """
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()

    vencida = datetime.now(UTC) - timedelta(days=1)
    total = 55
    for i in range(total):
        subtema = Subtema(tema_id=tema.id, nome=f"Subtema {i}", ordem=i)
        db_session.add(subtema)
        await db_session.flush()
        db_session.add(
            AlunoTemaProgresso(
                aluno_id=student_identity.aluno_id,
                subtema_id=subtema.id,
                nivel_dominio=0.5,
                intervalo_dias=1.0,
                streak_acertos=0,
                proxima_revisao=vencida,
                total_respondidas=1,
            )
        )
    await db_session.commit()

    first_page = await client.get("/reviews/today", headers=student_identity.headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 50

    second_page = await client.get("/reviews/today?offset=50", headers=student_identity.headers)
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body) == total - 50

    ids_first = {item["subtema_id"] for item in first_body}
    ids_second = {item["subtema_id"] for item in second_body}
    assert ids_first.isdisjoint(ids_second)
    assert len(ids_first) + len(ids_second) == total


async def test_reviews_today_listing_rejects_an_oversized_limit(client, auth_headers):
    response = await client.get("/reviews/today?limit=1000", headers=auth_headers)
    assert response.status_code == 422


# ── B8: nada amarrava o payload que esta rota publica aos dois servicos
# que o consomem. Renomear a chave `dominio_tema` no router deixava
# learning (56), notification (20) e analytics (26) TODOS verdes — 102
# testes cegos ao defeito. Causa: a fixture `_stub_publish_event` era um
# noop que descartava o payload, e cada consumidor recriava um literal
# local cuja docstring PROMETIA espelhar o produtor sem importar nada
# dele. O produtor agora monta o payload por `edu_common.contracts`, os
# consumidores constroem seus fixtures da mesma classe, e este teste fixa
# o formato de barramento com LITERAIS — usar `DiagnosticCompleted.
# ROUTING_KEY` ou os nomes dos campos aqui faria o teste seguir uma
# renomeacao em vez de detecta-la. ─────────────────────────────────────


async def test_answer_publishes_the_exact_diagnostic_completed_payload(
    client, db_session, student_identity, _stub_publish_event
):
    from app.models.questao import Questao

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
        enunciado="Qual organela sintetiza proteinas?",
        alternativas={"A": "Ribossomo", "B": "Lisossomo", "C": "Vacuolo", "D": "Centriolo"},
        gabarito="A",
        nivel_dificuldade=1,
    )
    db_session.add(questao)
    await db_session.commit()

    response = await client.post(
        "/diagnostic/answer",
        json={
            "tema_id": tema.id,
            "respostas": [{"questao_id": questao.id, "alternativa_escolhida": "A"}],
        },
        headers=student_identity.headers,
    )
    assert response.status_code == 200, response.text

    publicados = [
        (routing_key, payload)
        for routing_key, payload in _stub_publish_event
        if routing_key == "diagnostic.completed"
    ]
    assert len(publicados) == 1
    _, payload = publicados[0]

    assert set(payload) == {"aluno_id", "tema_id", "dominio_tema", "acao"}
    assert payload["aluno_id"] == str(student_identity.aluno_id)
    assert payload["tema_id"] == tema.id
    assert isinstance(payload["dominio_tema"], float)
    assert payload["acao"] in {"estudar", "avancar", "retroceder"}


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
            "respostas": [{"questao_id": questao_alheia.id, "alternativa_escolhida": "A"}],
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
            "respostas": [{"questao_id": questao_alheia.id, "alternativa_escolhida": "A"}],
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
            "respostas": [{"questao_id": i, "alternativa_escolhida": "A"} for i in range(51)],
        },
        headers=student_identity.headers,
    )
    assert response.status_code == 422
