from datetime import date, timedelta

from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema


async def _seed(db, *, com_questao_no_primeiro=True, quantos=3):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    subtemas = []
    for k in range(quantos):
        subtema = Subtema(tema_id=tema.id, nome=f"S{k}", ordem=k + 1)
        db.add(subtema)
        await db.flush()
        subtemas.append(subtema)
    if com_questao_no_primeiro:
        db.add(
            Questao(
                subtema_id=subtemas[0].id,
                enunciado="Enunciado",
                alternativas={"A": "a", "B": "b"},
                gabarito="A",
                nivel_dificuldade=1,
            )
        )
    await db.commit()
    return subtemas


async def _fazer_onboarding(client, headers, dias=30):
    return await client.post(
        "/onboarding",
        headers=headers,
        json={
            "titulo": "Medicina",
            "data_alvo": (date.today() + timedelta(days=dias)).isoformat(),
        },
    )


async def test_sem_objetivo_a_lista_vem_vazia_com_motivo(client, auth_headers):
    resposta = await client.get("/roadmap", headers=auth_headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["items"] == []
    assert corpo["total"] == 0
    assert corpo["objetivo"] is None
    assert corpo["motivo"]
    assert "objetivo" in corpo["motivo"].lower()


async def test_com_objetivo_traz_as_etapas_em_ordem(client, db_session, auth_headers):
    subtemas = await _seed(db_session)
    await _fazer_onboarding(client, auth_headers)

    corpo = (await client.get("/roadmap", headers=auth_headers)).json()
    assert corpo["total"] == 3
    assert [e["subtema_id"] for e in corpo["items"]] == [s.id for s in subtemas]
    assert [e["ordem"] for e in corpo["items"]] == [0, 1, 2]
    assert corpo["motivo"] is None
    assert corpo["objetivo"]["titulo"] == "Medicina"


async def test_etapa_carrega_os_nomes_da_hierarquia(client, db_session, auth_headers):
    await _seed(db_session)
    await _fazer_onboarding(client, auth_headers)

    primeira = (await client.get("/roadmap", headers=auth_headers)).json()["items"][0]
    assert primeira["materia_nome"] == "Biologia"
    assert primeira["tema_nome"] == "Citologia"
    assert primeira["subtema_nome"] == "S0"


async def test_subtema_sem_questao_vem_marcado(client, db_session, auth_headers):
    await _seed(db_session, com_questao_no_primeiro=True)
    await _fazer_onboarding(client, auth_headers)

    itens = (await client.get("/roadmap", headers=auth_headers)).json()["items"]
    assert itens[0]["tem_questoes"] is True
    assert itens[1]["tem_questoes"] is False
    assert itens[2]["tem_questoes"] is False


async def test_a_listagem_pagina(client, db_session, auth_headers):
    await _seed(db_session, quantos=5)
    await _fazer_onboarding(client, auth_headers)

    corpo = (await client.get("/roadmap?limit=2&offset=2", headers=auth_headers)).json()
    assert corpo["total"] == 5
    assert corpo["limit"] == 2
    assert corpo["offset"] == 2
    assert [e["ordem"] for e in corpo["items"]] == [2, 3]


async def test_limite_fora_de_faixa_e_recusado(client, auth_headers):
    assert (await client.get("/roadmap?limit=0", headers=auth_headers)).status_code == 422
    assert (await client.get("/roadmap?limit=500", headers=auth_headers)).status_code == 422


async def test_o_roadmap_e_do_aluno_do_token(client, db_session, student_identity, auth_headers):
    """Duas identidades, dois percursos — nenhuma enxerga a outra."""
    await _seed(db_session)
    await _fazer_onboarding(client, student_identity.headers)

    outro = await client.get("/roadmap", headers=auth_headers)
    assert outro.status_code == 200


async def test_roadmap_exige_token(client):
    assert (await client.get("/roadmap")).status_code == 403


async def test_prazo_apertado_aparece_no_corpo(client, db_session, auth_headers):
    await _seed(db_session, quantos=5)
    await _fazer_onboarding(client, auth_headers, dias=1)
    corpo = (await client.get("/roadmap", headers=auth_headers)).json()
    assert corpo["prazo_apertado"] is True
