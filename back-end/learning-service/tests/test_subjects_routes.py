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
