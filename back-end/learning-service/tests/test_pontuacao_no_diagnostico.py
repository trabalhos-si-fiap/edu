from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models.pontuacao import LancamentoPontos
from app.models.progresso import AlunoTemaProgresso
from app.models.questao import Questao
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _cenario(db, *, quantas_questoes=4):
    """Um tema com um subtema e N questões, todas de dificuldade 1."""
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db.add(subtema)
    await db.flush()
    questoes = []
    for _ in range(quantas_questoes):
        questao = Questao(
            subtema_id=subtema.id,
            enunciado="Enunciado",
            alternativas={"A": "a", "B": "b"},
            gabarito="A",
            nivel_dificuldade=1,
        )
        db.add(questao)
        await db.flush()
        questoes.append(questao)
    await db.commit()
    return tema, subtema, questoes


def _respostas(questoes, corretas):
    return [
        {"questao_id": q.id, "alternativa_escolhida": "A" if i < corretas else "B"}
        for i, q in enumerate(questoes)
    ]


async def _pontos(db, aluno_id, origem=None):
    stmt = select(LancamentoPontos).where(LancamentoPontos.aluno_id == aluno_id)
    if origem:
        stmt = stmt.where(LancamentoPontos.origem == origem)
    return (await db.execute(stmt)).scalars().all()


async def test_cada_questao_correta_vale_dez(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session)

    resposta = await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=3)},
    )
    assert resposta.status_code == 200

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="questao")
    assert len(lancamentos) == 3
    assert {lancamento.pontos for lancamento in lancamentos} == {10}


async def test_responder_de_novo_nao_pontua_de_novo(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session)
    corpo = {"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)}

    await client.post("/diagnostic/answer", headers=student_identity.headers, json=corpo)
    await client.post("/diagnostic/answer", headers=student_identity.headers, json=corpo)

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="questao")
    assert len(lancamentos) == 4  # e não 8


async def test_dominio_alto_conclui_a_etapa_e_pontua_cinquenta(
    client, db_session, student_identity
):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        EtapaRoadmap(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            ordem=0,
            prazo=date.today(),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )

    etapa = (
        await db_session.execute(
            select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
        )
    ).scalar_one()
    assert etapa.concluida_em is not None

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="etapa")
    assert [lancamento.pontos for lancamento in lancamentos] == [50]


async def test_dominio_baixo_nao_conclui_etapa(client, db_session, student_identity):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        EtapaRoadmap(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            ordem=0,
            prazo=date.today(),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=1)},
    )

    etapa = (
        await db_session.execute(
            select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
        )
    ).scalar_one()
    assert etapa.concluida_em is None
    assert await _pontos(db_session, student_identity.aluno_id, origem="etapa") == []


async def test_revisao_vencida_respondida_pontua_quinze(client, db_session, student_identity):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            nivel_dominio=0.8,
            proxima_revisao=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="revisao")
    assert [lancamento.pontos for lancamento in lancamentos] == [15]


async def test_revisao_no_futuro_nao_pontua(client, db_session, student_identity):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            nivel_dominio=0.8,
            proxima_revisao=datetime.now(UTC) + timedelta(days=3),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )
    assert await _pontos(db_session, student_identity.aluno_id, origem="revisao") == []


async def test_primeira_resposta_de_um_subtema_nao_conta_como_revisao(
    client, db_session, student_identity
):
    """Sem linha de progresso anterior não há revisão vencida — a primeira
    resposta é estudo novo, não revisão."""
    tema, _subtema, questoes = await _cenario(db_session)
    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )
    assert await _pontos(db_session, student_identity.aluno_id, origem="revisao") == []


async def test_bonus_de_sequencia_cresce_com_o_streak(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session, quantas_questoes=8)
    primeira = questoes[:4]
    segunda = questoes[4:]

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(primeira, corretas=4)},
    )
    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(segunda, corretas=4)},
    )

    lancamentos = sorted(
        lancamento.pontos
        for lancamento in await _pontos(db_session, student_identity.aluno_id, origem="streak")
    )
    assert lancamentos == [5, 10]  # streak 1 e streak 2


async def test_o_resumo_enxerga_os_pontos_lancados(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session)
    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )

    corpo = (await client.get("/profile/summary", headers=student_identity.headers)).json()
    # 4 questões x 10 + bônus de sequência 1 x 5 = 45
    assert corpo["pontos"]["total"] == 45
    assert corpo["estudo"]["questoes_respondidas"] == 4
    assert corpo["estudo"]["subtemas_iniciados"] == 1
