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

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

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


async def test_concurrent_answers_on_the_same_subtopic_do_not_collide(
    client, db_session, student_identity, monkeypatch
):
    """Duas chamadas SIMULTANEAS ao /answer no mesmo subtema somam, sem 500.

    Este teste precisa ser concorrente E precisa forcar a intercalacao. Em
    serie o defeito nao aparece: o SELECT da segunda chamada enxerga a linha
    ja commitada pela primeira e o `+= len(respostas)` chega a 2 sozinho. E
    um `asyncio.gather` puro tambem nao basta — as queries locais voltam
    rapido demais para o event loop trocar de tarefa, entao as duas
    requisicoes rodam de ponta a ponta uma depois da outra (medido).

    O encontro e feito sem `sleep`, para nao depender de tempo: a PRIMEIRA
    requisicao para dentro de `publish_event` e so segue quando a SEGUNDA
    avisa que ja passou pelo seu proprio SELECT de progresso. O aviso sai de
    `atualizar_revisao`, que roda entre o SELECT e a escrita — logo as duas
    leram "nao existe" antes de qualquer uma escrever, que e exatamente a
    corrida que o `ON CONFLICT` fecha.

    Contra o codigo antigo uma das duas termina em IntegrityError
    (`uq_aluno_subtema`) DEPOIS de ja ter gravado as respostas.
    """
    import app.routers.diagnostico as mod

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
        enunciado="O que e a bicamada lipidica?",
        alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
        gabarito="A",
        nivel_dificuldade=1,
    )
    db_session.add(questao)
    await db_session.commit()

    a_segunda_leu = asyncio.Event()
    estado = {"leituras": 0, "ja_esperou": False}
    atualizar_real = mod.atualizar_revisao

    def _avisar_na_segunda_leitura(*args, **kwargs):
        estado["leituras"] += 1
        if estado["leituras"] == 2:
            a_segunda_leu.set()
        return atualizar_real(*args, **kwargs)

    async def _publicar_segurando_a_primeira(routing_key, payload):
        if not estado["ja_esperou"]:
            estado["ja_esperou"] = True
            await a_segunda_leu.wait()

    monkeypatch.setattr(mod, "atualizar_revisao", _avisar_na_segunda_leitura)
    monkeypatch.setattr(mod, "publish_event", _publicar_segurando_a_primeira)

    corpo = {
        "tema_id": tema.id,
        "respostas": [{"questao_id": questao.id, "alternativa_escolhida": "A"}],
    }
    primeira, segunda = await asyncio.gather(
        client.post("/diagnostic/answer", json=corpo, headers=student_identity.headers),
        client.post("/diagnostic/answer", json=corpo, headers=student_identity.headers),
    )
    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 200, segunda.text

    result = await db_session.execute(
        select(AlunoTemaProgresso).where(
            AlunoTemaProgresso.aluno_id == student_identity.aluno_id,
            AlunoTemaProgresso.subtema_id == subtema.id,
        )
    )
    progresso = result.scalar_one()
    assert progresso.total_respondidas == 2


async def test_concurrent_answers_keep_both_streak_increments(
    client, db_session, student_identity, monkeypatch
):
    """`total_respondidas` era a UNICA coluna atomica do upsert.

    O teste irmao acima cobre a corrida de INSERCAO (linha inexistente,
    fechada pela constraint + `on_conflict_do_update`) e so afirma
    `total_respondidas`, que virou soma em SQL. `streak_acertos`,
    `intervalo_dias` e `nivel_dominio` saiam de um SELECT sem lock e
    voltavam como SUBSTITUICAO — read->write em linha compartilhada, que e
    a regra 3 do CLAUDE.md.

    Aqui a linha JA EXISTE (`streak_acertos = 3` seedado), que e o unico
    caso que `with_for_update()` consegue fechar: sem lock, duas respostas
    certas simultaneas leem 3, calculam 4 e gravam 4. O esperado e 5.

    ── Por que a intercalacao precisa ser forcada, e forcada ASSIM ──

    `asyncio.gather` sozinho nao basta, medido: com as duas requisicoes
    livres, a primeira le 3 e a segunda le 4 (ou seja, a segunda so chega
    ao SELECT depois do `db.commit()` da primeira) e o teste passa contra o
    codigo defeituoso.

    E o encontro do teste irmao nao serve aqui, mas nao pelo motivo obvio:
    ele TAMBEM e de mao unica — avisa dentro de `atualizar_revisao` e
    espera dentro de `publish_event`, que roda DEPOIS do `db.commit()`
    (`app/routers/diagnostico.py`, commit antes do publish), ou seja com o
    lock ja solto, sem ninguem pendurado. O que nao serve e o MOMENTO do
    aviso: `atualizar_revisao` roda depois do SELECT do progresso, tarde
    demais para forcar a intercalacao no ponto que decide o streak.

    Entao o encontro e de mao unica, entre dois pontos escolhidos:

    * quem AVISA e `calcular_dominio`, que roda ANTES do SELECT de
      progresso — ponto que a segunda requisicao alcanca mesmo quando o
      SELECT vai travar;
    * quem ESPERA e `buscar_tema_anterior`, que roda DEPOIS do upsert e
      ANTES do `db.commit()` — a primeira requisicao para ali segurando a
      sua transacao aberta.

    Contra o codigo sem lock: a primeira segura o upsert nao commitado, a
    segunda faz um SELECT comum (que sob READ COMMITTED nao trava em linha
    com UPDATE pendente), le 3, calcula 4, e o seu proprio upsert e que
    espera o commit da primeira. Resultado 4 — o incremento perdido.

    Com `with_for_update()`: o SELECT da segunda trava, a primeira commita,
    a segunda le 4 e grava 5.

    O arranjo e deterministico, nao probabilistico: 20 execucoes
    consecutivas contra o codigo sem lock falharam as 20 com
    `streak_acertos == 4`.

    Medido nesta rodada, com `_espiao_get_db` temporario: as duas
    requisicoes recebem `AsyncSession` distintas e conexoes DBAPI
    distintas do pool (`Pool size: 5`), entao o lock de linha entre
    conexoes e de fato exercitado — nao e um lock que o mesmo `AsyncSession`
    daria de graca.
    """
    import app.routers.diagnostico as mod

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
        enunciado="O que e a bicamada lipidica?",
        alternativas={"A": "a", "B": "b", "C": "c", "D": "d"},
        gabarito="A",
        nivel_dificuldade=1,
    )
    db_session.add(questao)
    # `streak_acertos` seedado em 3 e nao em 0 para o valor perdido ser
    # visivel: com 0 o defeito daria 1 e o correto 2, e um off-by-one em
    # qualquer lado ficaria ambiguo.
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            nivel_dominio=1.0,
            intervalo_dias=1.0,
            streak_acertos=3,
            total_respondidas=0,
        )
    )
    await db_session.commit()

    a_segunda_chegou = asyncio.Event()
    estado = {"dominios": 0, "ja_esperou": False}
    calcular_real = mod.calcular_dominio
    anterior_real = mod.buscar_tema_anterior

    def _avisar_na_segunda(respostas):
        estado["dominios"] += 1
        if estado["dominios"] == 2:
            a_segunda_chegou.set()
        return calcular_real(respostas)

    async def _segurar_a_primeira(db, tema_):
        if not estado["ja_esperou"]:
            estado["ja_esperou"] = True
            # `wait_for` e nao `wait`: se o ponto de encontro deixar de ser
            # alcancavel, o teste falha alto em vez de pendurar a suite.
            await asyncio.wait_for(a_segunda_chegou.wait(), timeout=10)
        return await anterior_real(db, tema_)

    monkeypatch.setattr(mod, "calcular_dominio", _avisar_na_segunda)
    monkeypatch.setattr(mod, "buscar_tema_anterior", _segurar_a_primeira)

    # Alternativa CERTA nas duas: `calcular_dominio` devolve 1.0, que cai no
    # ramo `dominio >= 0.7` de `atualizar_revisao` — o unico que incrementa
    # o streak.
    corpo = {
        "tema_id": tema.id,
        "respostas": [{"questao_id": questao.id, "alternativa_escolhida": "A"}],
    }
    primeira, segunda = await asyncio.gather(
        client.post("/diagnostic/answer", json=corpo, headers=student_identity.headers),
        client.post("/diagnostic/answer", json=corpo, headers=student_identity.headers),
    )
    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 200, segunda.text

    progresso = (
        await db_session.execute(
            select(AlunoTemaProgresso).where(
                AlunoTemaProgresso.aluno_id == student_identity.aluno_id,
                AlunoTemaProgresso.subtema_id == subtema.id,
            )
        )
    ).scalar_one()
    assert progresso.total_respondidas == 2
    assert progresso.streak_acertos == 5, (
        f"streak perdeu um incremento: {progresso.streak_acertos} (as duas leram 3 e gravaram 4)"
    )


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
            "respostas": [{"questao_id": q.id, "alternativa_escolhida": "B"} for q in questoes],
        },
        headers=student_identity.headers,
    )
    assert response.status_code == 200

    chaves = [routing_key for routing_key, _ in _stub_publish_event]
    assert "revision.scheduled" not in chaves
    assert chaves == ["diagnostic.completed"]
