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

from app.models.subtema import Materia, Subtema, Tema


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


async def test_subtopic_questions_limite_has_a_hard_cap(client, auth_headers):
    response = await client.get("/subtopics/1/questions?limite=99999", headers=auth_headers)
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
