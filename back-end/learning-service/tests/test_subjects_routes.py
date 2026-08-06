"""Testes de rota para `/subjects`, `/topics`, `/subtopics`.

Adaptações em relação ao brief da task 9: os cinco endpoints de
`app/routers/materias.py` não tinham controle de acesso (achado do review
da task anterior, agora corrigido — ver `Depends(get_current_user)` no
router). Isso significa que os testes do brief que esperavam 200/422/404
SEM header de autenticação teriam, na verdade, batido primeiro no 403 de
"não autenticado" (a dependência de auth é resolvida antes da validação
dos parâmetros de query do próprio endpoint) — confirmado rodando a
suíte. Por isso todos os testes que exercitam o corpo do endpoint usam a
fixture `auth_headers`; só o teste do path antigo (que nem chega a
resolver dependência nenhuma, pois a rota não existe mais) continua sem
header.

Fix round 1 (MINOR 6) acrescenta testes que seedam mais linhas do que o
limite padrão para provar que `.limit(limit).offset(offset)` está
realmente aplicado — os testes originais só provavam a ANOTAÇÃO (422 em
`limit=1000`), não o comportamento; apagar `.limit()/.offset()` do router
deixava todos os testes anteriores verdes. Também acrescenta testes com
`ordem` duplicado (MINOR 5) para provar que o desempate por `.id` evita
linhas puladas/repetidas entre páginas.
"""

from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema


async def _seed_subtema_com_questoes(
    db_session, *, quantidade: int
) -> tuple[Subtema, list[Questao]]:
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


async def test_subjects_are_listed_in_english_path(client, auth_headers):
    response = await client.get("/subjects", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_subjects_require_authentication(client):
    assert (await client.get("/subjects")).status_code == 403


async def test_old_portuguese_path_is_gone(client):
    assert (await client.get("/materias")).status_code == 404


async def test_subjects_listing_is_paginated(client, auth_headers):
    response = await client.get("/subjects?limit=1000", headers=auth_headers)
    assert response.status_code == 422


async def test_topics_of_unknown_subject_return_404(client, auth_headers):
    response = await client.get("/subjects/999999/topics", headers=auth_headers)
    assert response.status_code == 404


async def test_topics_require_authentication(client):
    assert (await client.get("/subjects/1/topics")).status_code == 403


async def test_topics_listing_is_paginated(client, auth_headers):
    response = await client.get("/subjects/1/topics?limit=1000", headers=auth_headers)
    assert response.status_code == 422


async def test_subtopics_of_unknown_topic_return_404(client, auth_headers):
    response = await client.get("/topics/999999/subtopics", headers=auth_headers)
    assert response.status_code == 404


async def test_subtopics_require_authentication(client):
    assert (await client.get("/topics/1/subtopics")).status_code == 403


async def test_subtopics_listing_is_paginated(client, auth_headers):
    response = await client.get("/topics/1/subtopics?limit=1000", headers=auth_headers)
    assert response.status_code == 422


async def test_quiz_requires_authentication(client):
    assert (await client.get("/topics/1/quiz")).status_code == 403


async def test_quiz_quantidade_has_a_hard_cap(client, auth_headers):
    response = await client.get("/topics/1/quiz?quantidade=99999", headers=auth_headers)
    assert response.status_code == 422


async def test_subtopic_questions_require_authentication(client):
    assert (await client.get("/subtopics/1/questions")).status_code == 403


async def test_subtopic_questions_limit_has_a_hard_cap(client, auth_headers):
    response = await client.get("/subtopics/1/questions?limit=99999", headers=auth_headers)
    assert response.status_code == 422


async def test_subjects_listing_returns_seeded_rows(client, auth_headers, db_session):
    db_session.add(Materia(nome="Biologia"))
    await db_session.commit()

    response = await client.get("/subjects", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert any(item["nome"] == "Biologia" for item in body)


async def test_subtopics_listing_never_leaks_the_internal_ai_description(
    client, auth_headers, db_session
):
    """`listar_subtemas` costumava devolver o objeto `Subtema` do SQLAlchemy
    cru (achado do review da task anterior, corrigido junto com
    `get_recomendacao`) — o que vazava `descricao_ia` (texto interno só
    para o classificador de IA, nunca exibido ao aluno) na resposta JSON.
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

    response = await client.get(f"/topics/{tema.id}/subtopics", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": body[0]["id"],
            "tema_id": tema.id,
            "nome": "Membrana",
            "ordem": 1,
            "videoaula_base_url": None,
            "videoaula_revisao_url": None,
        }
    ]


async def test_subjects_listing_defaults_to_fifty_and_supports_offset(
    client, auth_headers, db_session
):
    for i in range(55):
        db_session.add(Materia(nome=f"Materia {i}"))
    await db_session.commit()

    first_page = await client.get("/subjects", headers=auth_headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 50

    second_page = await client.get("/subjects?offset=50", headers=auth_headers)
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body) == 5

    ids_first = {item["id"] for item in first_body}
    ids_second = {item["id"] for item in second_body}
    assert ids_first.isdisjoint(ids_second)


async def test_topics_listing_defaults_to_fifty_and_supports_offset(
    client, auth_headers, db_session
):
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    for i in range(55):
        db_session.add(Tema(materia_id=materia.id, nome=f"Tema {i}", ordem=i))
    await db_session.commit()

    first_page = await client.get(f"/subjects/{materia.id}/topics", headers=auth_headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 50

    second_page = await client.get(f"/subjects/{materia.id}/topics?offset=50", headers=auth_headers)
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body) == 5

    ids_first = {item["id"] for item in first_body}
    ids_second = {item["id"] for item in second_body}
    assert ids_first.isdisjoint(ids_second)


async def test_topics_pagination_is_stable_when_ordem_is_not_unique(
    client, auth_headers, db_session
):
    """MINOR 5: `Tema.ordem` tem `default=0` e não é única. Ordenar só por
    `.ordem` deixa a ordem entre linhas empatadas a critério do banco, que
    pode mudar entre duas execuções da mesma query paginada — o que pula
    ou repete linhas entre páginas. Seed 55 temas todos com `ordem=0` (o
    pior caso: todos empatados) e prova que o desempate por `.id` garante
    que a união das páginas contém as 55 linhas, sem repetição.
    """
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    for i in range(55):
        db_session.add(Tema(materia_id=materia.id, nome=f"Tema {i}", ordem=0))
    await db_session.commit()

    first_page = (await client.get(f"/subjects/{materia.id}/topics", headers=auth_headers)).json()
    second_page = (
        await client.get(f"/subjects/{materia.id}/topics?offset=50", headers=auth_headers)
    ).json()

    ids_first = {item["id"] for item in first_page}
    ids_second = {item["id"] for item in second_page}
    assert len(ids_first) == 50
    assert len(ids_second) == 5
    assert ids_first.isdisjoint(ids_second)
    assert len(ids_first) + len(ids_second) == 55


async def test_subtopics_listing_defaults_to_fifty_and_supports_offset(
    client, auth_headers, db_session
):
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    for i in range(55):
        db_session.add(Subtema(tema_id=tema.id, nome=f"Subtema {i}", ordem=i))
    await db_session.commit()

    first_page = await client.get(f"/topics/{tema.id}/subtopics", headers=auth_headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 50

    second_page = await client.get(f"/topics/{tema.id}/subtopics?offset=50", headers=auth_headers)
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body) == 5

    ids_first = {item["id"] for item in first_body}
    ids_second = {item["id"] for item in second_body}
    assert ids_first.isdisjoint(ids_second)


async def test_subtopics_pagination_is_stable_when_ordem_is_not_unique(
    client, auth_headers, db_session
):
    """MINOR 5, mesma correção que em `Tema.ordem` acima, agora para
    `Subtema.ordem` (também `default=0`, também não única).
    """
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    for i in range(55):
        db_session.add(Subtema(tema_id=tema.id, nome=f"Subtema {i}", ordem=0))
    await db_session.commit()

    first_page = (await client.get(f"/topics/{tema.id}/subtopics", headers=auth_headers)).json()
    second_page = (
        await client.get(f"/topics/{tema.id}/subtopics?offset=50", headers=auth_headers)
    ).json()

    ids_first = {item["id"] for item in first_page}
    ids_second = {item["id"] for item in second_page}
    assert len(ids_first) == 50
    assert len(ids_second) == 5
    assert ids_first.isdisjoint(ids_second)
    assert len(ids_first) + len(ids_second) == 55


# ── B7, ultimo dos sete sitios do sweep: `/subtopics/{id}/questions` tinha
# so o teste do cap (422 em `limite=99999`), que exercita a anotacao
# `Query(le=50)` e nada mais — apagar `.limit(limite)` de
# `app/routers/materias.py:118` o deixava verde. Task 23 traduz `limite`
# para `limit` (era o unico param em portugues dos sete servicos) e
# acrescenta `offset`, com `order_by(Questao.id)` para a pagina ser
# estavel — sem duplicar linha nem pular nenhuma entre paginas. ────────


async def test_subtopic_questions_actually_applies_the_limit(client, auth_headers, db_session):
    subtema, _ = await _seed_subtema_com_questoes(db_session, quantidade=30)

    explicito = await client.get(f"/subtopics/{subtema.id}/questions?limit=5", headers=auth_headers)
    assert explicito.status_code == 200
    assert len(explicito.json()) == 5

    # Default de 8 — literal de proposito: usar a constante da
    # implementacao faria o teste seguir uma mudanca de default em vez de
    # detecta-la.
    padrao = await client.get(f"/subtopics/{subtema.id}/questions", headers=auth_headers)
    assert padrao.status_code == 200
    assert len(padrao.json()) == 8


async def test_subtopic_questions_paginate_with_limit_and_offset(client, db_session, auth_headers):
    subtema, _questoes = await _seed_subtema_com_questoes(db_session, quantidade=5)

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


async def test_subtopic_questions_pagination_is_stable_when_more_than_one_page_ties_on_id_order(
    client, auth_headers, db_session
):
    """Prova que a estabilidade da paginacao vem de `order_by(Questao.id)`,
    nao de sorte: sem ordenacao declarada o Postgres pode devolver as
    linhas em qualquer ordem entre duas execucoes da mesma query, e
    `offset` passaria a pular ou repetir questoes entre paginas."""
    subtema, questoes = await _seed_subtema_com_questoes(db_session, quantidade=12)

    primeira = (
        await client.get(
            f"/subtopics/{subtema.id}/questions?limit=8&offset=0", headers=auth_headers
        )
    ).json()
    segunda = (
        await client.get(
            f"/subtopics/{subtema.id}/questions?limit=8&offset=8", headers=auth_headers
        )
    ).json()

    ids_primeira = [q["id"] for q in primeira]
    ids_segunda = [q["id"] for q in segunda]
    todos_ids_ordenados = sorted(q.id for q in questoes)
    assert ids_primeira == todos_ids_ordenados[:8]
    assert ids_segunda == todos_ids_ordenados[8:]
    assert set(ids_primeira).isdisjoint(ids_segunda)


async def test_subtopic_questions_404_only_when_truly_empty_not_past_the_last_page(
    client, auth_headers, db_session
):
    """`offset` tornou alcancavel um terceiro significado para "vazio". Antes
    so existia `offset=0`, e vazio so podia querer dizer "este subtema nao
    tem questao nenhuma" — 404 fazia sentido. Agora um cliente tambem pode
    pedir uma pagina alem do fim de um subtema que TEM questoes; nesse caso
    vazio quer dizer "voce passou do fim", nao "nao ha nada aqui", e 404
    afirmaria algo falso (um cliente que trate 404 como "sem conteudo"
    erraria ao paginar ate o fim). Os dois casos precisam responder
    diferente, entao este teste exercita os dois juntos."""
    subtema_vazio, _ = await _seed_subtema_com_questoes(db_session, quantidade=0)
    subtema_com_questoes, _ = await _seed_subtema_com_questoes(db_session, quantidade=1)

    vazio_de_verdade = await client.get(
        f"/subtopics/{subtema_vazio.id}/questions", headers=auth_headers
    )
    passou_do_fim = await client.get(
        f"/subtopics/{subtema_com_questoes.id}/questions?offset=5", headers=auth_headers
    )

    assert vazio_de_verdade.status_code == 404
    assert passou_do_fim.status_code == 200
    assert passou_do_fim.json() == []
