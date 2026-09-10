from datetime import date, timedelta

from sqlalchemy import select

from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _seed_conteudo(db, quantos=4):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    for k in range(quantos):
        db.add(Subtema(tema_id=tema.id, nome=f"S{k}", ordem=k + 1))
    await db.commit()


async def test_aluno_sem_objetivo_recebe_null(client, auth_headers):
    resposta = await client.get("/onboarding", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json() is None


async def test_criar_objetivo_gera_o_roadmap(client, db_session, student_identity):
    await _seed_conteudo(db_session)
    alvo = date.today() + timedelta(days=30)

    resposta = await client.post(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina USP", "data_alvo": alvo.isoformat()},
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["objetivo"]["titulo"] == "Medicina USP"
    assert corpo["objetivo"]["data_alvo"] == alvo.isoformat()
    assert corpo["etapas_geradas"] == 4
    assert corpo["prazo_apertado"] is False

    etapas = (
        (
            await db_session.execute(
                select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(etapas) == 4


async def test_data_no_passado_e_recusada_com_mensagem_exibivel(client, auth_headers):
    ontem = date.today() - timedelta(days=1)
    resposta = await client.post(
        "/onboarding",
        headers=auth_headers,
        json={"titulo": "Medicina", "data_alvo": ontem.isoformat()},
    )
    assert resposta.status_code == 422
    assert "passado" in resposta.text.lower()


async def test_titulo_vazio_ou_so_espaco_e_recusado(client, auth_headers):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    for titulo in ("", "   "):
        resposta = await client.post(
            "/onboarding", headers=auth_headers, json={"titulo": titulo, "data_alvo": alvo}
        )
        assert resposta.status_code == 422


async def test_titulo_acima_do_teto_e_recusado(client, auth_headers):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    resposta = await client.post(
        "/onboarding", headers=auth_headers, json={"titulo": "x" * 121, "data_alvo": alvo}
    )
    assert resposta.status_code == 422


async def test_segundo_objetivo_do_mesmo_aluno_e_conflito(client, db_session, auth_headers):
    await _seed_conteudo(db_session)
    alvo = (date.today() + timedelta(days=30)).isoformat()
    primeira = await client.post(
        "/onboarding", headers=auth_headers, json={"titulo": "Medicina", "data_alvo": alvo}
    )
    assert primeira.status_code == 201

    segunda = await client.post(
        "/onboarding", headers=auth_headers, json={"titulo": "Direito", "data_alvo": alvo}
    )
    assert segunda.status_code == 409


async def test_alterar_a_data_regenera_os_prazos(client, db_session, student_identity):
    await _seed_conteudo(db_session)
    alvo = date.today() + timedelta(days=30)
    await client.post(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina", "data_alvo": alvo.isoformat()},
    )

    novo_alvo = date.today() + timedelta(days=90)
    resposta = await client.put(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina", "data_alvo": novo_alvo.isoformat()},
    )
    assert resposta.status_code == 200
    assert resposta.json()["etapas_geradas"] == 4

    etapas = (
        (
            await db_session.execute(
                select(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
                .order_by(EtapaRoadmap.ordem)
            )
        )
        .scalars()
        .all()
    )
    assert etapas[-1].prazo == novo_alvo


async def test_alterar_so_o_titulo_nao_mexe_nos_prazos(client, db_session, student_identity):
    await _seed_conteudo(db_session)
    alvo = date.today() + timedelta(days=30)
    await client.post(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina", "data_alvo": alvo.isoformat()},
    )
    antes = [
        e.prazo
        for e in (
            await db_session.execute(
                select(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
                .order_by(EtapaRoadmap.ordem)
            )
        )
        .scalars()
        .all()
    ]

    await client.put(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina UFMG", "data_alvo": alvo.isoformat()},
    )
    depois = [
        e.prazo
        for e in (
            await db_session.execute(
                select(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
                .order_by(EtapaRoadmap.ordem)
            )
        )
        .scalars()
        .all()
    ]
    assert antes == depois


async def test_put_sem_objetivo_e_404(client, auth_headers):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    resposta = await client.put(
        "/onboarding", headers=auth_headers, json={"titulo": "Medicina", "data_alvo": alvo}
    )
    assert resposta.status_code == 404


async def test_rotas_de_onboarding_exigem_token(client):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    assert (await client.get("/onboarding")).status_code == 403
    assert (
        await client.post("/onboarding", json={"titulo": "x", "data_alvo": alvo})
    ).status_code == 403


async def test_prazo_apertado_e_sinalizado(client, db_session, auth_headers):
    await _seed_conteudo(db_session, quantos=10)
    resposta = await client.post(
        "/onboarding",
        headers=auth_headers,
        json={
            "titulo": "Prova da semana",
            "data_alvo": (date.today() + timedelta(days=2)).isoformat(),
        },
    )
    assert resposta.status_code == 201
    assert resposta.json()["prazo_apertado"] is True
