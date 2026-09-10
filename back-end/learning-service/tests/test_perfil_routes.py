from datetime import UTC, date, datetime, timedelta

from app.models.objetivo import ObjetivoAluno
from app.models.pontuacao import LancamentoPontos
from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _subtemas(db, quantos=3):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    criados = []
    for k in range(quantos):
        subtema = Subtema(tema_id=tema.id, nome=f"S{k}", ordem=k + 1)
        db.add(subtema)
        await db.flush()
        criados.append(subtema)
    await db.commit()
    return criados


async def test_aluno_zerado_mostra_zero(client, auth_headers):
    """O teste que fecha o objetivo da spec: recém-criado é zero, não 3.120."""
    corpo = (await client.get("/profile/summary", headers=auth_headers)).json()
    assert corpo["objetivo"] is None
    assert corpo["roadmap"] == {"etapas_totais": 0, "etapas_concluidas": 0, "progresso": 0.0}
    assert corpo["pontos"] == {"total": 0, "nivel": 1, "streak": 0}
    assert corpo["estudo"] == {"questoes_respondidas": 0, "subtemas_iniciados": 0}


async def test_objetivo_traz_dias_decorridos_e_totais(client, db_session, student_identity):
    criado_em = datetime.now(UTC) - timedelta(days=10)
    db_session.add(
        ObjetivoAluno(
            aluno_id=student_identity.aluno_id,
            titulo="Medicina USP",
            data_alvo=date.today() + timedelta(days=90),
            criado_em=criado_em,
            atualizado_em=criado_em,
        )
    )
    await db_session.commit()

    objetivo = (await client.get("/profile/summary", headers=student_identity.headers)).json()[
        "objetivo"
    ]
    assert objetivo["titulo"] == "Medicina USP"
    assert objetivo["dias_decorridos"] == 10
    assert objetivo["dias_totais"] == 100


async def test_progresso_do_roadmap_e_a_razao_de_etapas_concluidas(
    client, db_session, student_identity
):
    subtemas = await _subtemas(db_session, quantos=4)
    for indice, subtema in enumerate(subtemas):
        db_session.add(
            EtapaRoadmap(
                aluno_id=student_identity.aluno_id,
                subtema_id=subtema.id,
                ordem=indice,
                prazo=date.today(),
                concluida_em=datetime.now(UTC) if indice < 3 else None,
            )
        )
    await db_session.commit()

    roadmap = (await client.get("/profile/summary", headers=student_identity.headers)).json()[
        "roadmap"
    ]
    assert roadmap["etapas_totais"] == 4
    assert roadmap["etapas_concluidas"] == 3
    assert roadmap["progresso"] == 0.75


async def test_pontos_e_nivel_saem_do_extrato(client, db_session, student_identity):
    for referencia in ("1", "2", "3"):
        db_session.add(
            LancamentoPontos(
                aluno_id=student_identity.aluno_id,
                origem="questao",
                referencia=referencia,
                pontos=50,
            )
        )
    await db_session.commit()

    pontos = (await client.get("/profile/summary", headers=student_identity.headers)).json()[
        "pontos"
    ]
    assert pontos["total"] == 150
    assert pontos["nivel"] == 2  # 150 está na faixa que começa em 100


async def test_streak_e_o_maior_do_aluno_e_estudo_soma_respostas(
    client, db_session, student_identity
):
    subtemas = await _subtemas(db_session, quantos=2)
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtemas[0].id,
            streak_acertos=2,
            total_respondidas=7,
        )
    )
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtemas[1].id,
            streak_acertos=5,
            total_respondidas=3,
        )
    )
    await db_session.commit()

    corpo = (await client.get("/profile/summary", headers=student_identity.headers)).json()
    assert corpo["pontos"]["streak"] == 5
    assert corpo["estudo"] == {"questoes_respondidas": 10, "subtemas_iniciados": 2}


async def test_objetivo_criado_hoje_nao_divide_por_zero(client, db_session, student_identity):
    db_session.add(
        ObjetivoAluno(
            aluno_id=student_identity.aluno_id,
            titulo="Prova amanhã",
            data_alvo=date.today(),
        )
    )
    await db_session.commit()

    objetivo = (await client.get("/profile/summary", headers=student_identity.headers)).json()[
        "objetivo"
    ]
    assert objetivo["dias_totais"] == 0
    assert objetivo["dias_decorridos"] == 0


async def test_dias_decorridos_nunca_passa_do_total(client, db_session, student_identity):
    criado_em = datetime.now(UTC) - timedelta(days=200)
    db_session.add(
        ObjetivoAluno(
            aluno_id=student_identity.aluno_id,
            titulo="Prova que já passou",
            data_alvo=date.today(),
            criado_em=criado_em,
            atualizado_em=criado_em,
        )
    )
    await db_session.commit()

    objetivo = (await client.get("/profile/summary", headers=student_identity.headers)).json()[
        "objetivo"
    ]
    assert objetivo["dias_decorridos"] == objetivo["dias_totais"] == 200


async def test_summary_exige_token(client):
    assert (await client.get("/profile/summary")).status_code == 403
