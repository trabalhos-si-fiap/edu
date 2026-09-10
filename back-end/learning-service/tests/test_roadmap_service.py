import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema
from app.services.roadmap import (
    concluir_etapa,
    distribuir_prazos,
    gerar_roadmap,
    prazo_apertado,
)

HOJE = date(2026, 9, 10)


async def _seed_conteudo(db, *, materias=1, temas=2, subtemas=2):
    """Cria uma árvore previsível: matéria 'M{i}' > tema 'T{j}' > subtema 'S{k}'.

    Devolve os subtemas na ordem que o roadmap DEVE produzir.
    """
    esperados = []
    for i in range(materias):
        materia = Materia(nome=f"M{i}")
        db.add(materia)
        await db.flush()
        for j in range(temas):
            tema = Tema(materia_id=materia.id, nome=f"T{i}{j}", ordem=j + 1)
            db.add(tema)
            await db.flush()
            for k in range(subtemas):
                subtema = Subtema(tema_id=tema.id, nome=f"S{i}{j}{k}", ordem=k + 1)
                db.add(subtema)
                await db.flush()
                esperados.append(subtema)
    await db.commit()
    return esperados


def test_a_primeira_etapa_e_hoje_e_a_ultima_e_a_data_alvo():
    prazos = distribuir_prazos(5, HOJE, HOJE + timedelta(days=20))
    assert prazos[0] == HOJE
    assert prazos[-1] == HOJE + timedelta(days=20)
    assert prazos == sorted(prazos)


def test_uma_etapa_so_vence_na_data_alvo():
    assert distribuir_prazos(1, HOJE, HOJE + timedelta(days=9)) == [HOJE + timedelta(days=9)]


def test_zero_etapas_devolve_lista_vazia():
    assert distribuir_prazos(0, HOJE, HOJE + timedelta(days=9)) == []


def test_prazo_curto_agrupa_em_vez_de_falhar():
    prazos = distribuir_prazos(10, HOJE, HOJE + timedelta(days=2))
    assert len(prazos) == 10
    assert prazos[0] == HOJE
    assert prazos[-1] == HOJE + timedelta(days=2)
    assert len(set(prazos)) < len(prazos)  # dias repetidos, de propósito
    assert prazo_apertado(10, HOJE, HOJE + timedelta(days=2)) is True


def test_prazo_folgado_nao_e_apertado():
    assert prazo_apertado(3, HOJE, HOJE + timedelta(days=30)) is False


def test_data_alvo_hoje_poe_tudo_hoje():
    prazos = distribuir_prazos(4, HOJE, HOJE)
    assert prazos == [HOJE] * 4
    assert prazo_apertado(4, HOJE, HOJE) is True


async def test_roadmap_cobre_todos_os_subtemas_na_ordem_do_conteudo(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()

    total = await gerar_roadmap(
        db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE
    )
    await db_session.commit()

    assert total == len(esperados)
    etapas = (
        (
            await db_session.execute(
                select(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == aluno)
                .order_by(EtapaRoadmap.ordem)
            )
        )
        .scalars()
        .all()
    )
    assert [e.subtema_id for e in etapas] == [s.id for s in esperados]
    assert [e.ordem for e in etapas] == list(range(len(esperados)))
    assert etapas[0].prazo == HOJE
    assert etapas[-1].prazo == HOJE + timedelta(days=30)


async def test_subtema_ja_dominado_nasce_concluido(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    db_session.add(
        AlunoTemaProgresso(aluno_id=aluno, subtema_id=esperados[1].id, nivel_dominio=0.9)
    )
    db_session.add(
        AlunoTemaProgresso(aluno_id=aluno, subtema_id=esperados[2].id, nivel_dominio=0.5)
    )
    await db_session.commit()

    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE)
    await db_session.commit()

    etapas = {
        e.subtema_id: e
        for e in (
            await db_session.execute(select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno))
        )
        .scalars()
        .all()
    }
    assert etapas[esperados[1].id].concluida_em is not None
    assert etapas[esperados[2].id].concluida_em is None


async def test_regerar_preserva_conclusoes_e_troca_prazos(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE)
    await db_session.commit()

    concluido = await concluir_etapa(
        db_session, aluno_id=aluno, subtema_id=esperados[0].id, quando=datetime.now(UTC)
    )
    await db_session.commit()
    assert concluido is True

    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=60), hoje=HOJE)
    await db_session.commit()

    etapas = {
        e.subtema_id: e
        for e in (
            await db_session.execute(select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno))
        )
        .scalars()
        .all()
    }
    assert len(etapas) == len(esperados)
    assert etapas[esperados[0].id].concluida_em is not None
    assert etapas[esperados[-1].id].prazo == HOJE + timedelta(days=60)


async def test_concluir_etapa_duas_vezes_devolve_false_na_segunda(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE)
    await db_session.commit()

    agora = datetime.now(UTC)
    assert (
        await concluir_etapa(db_session, aluno_id=aluno, subtema_id=esperados[0].id, quando=agora)
        is True
    )
    await db_session.commit()
    assert (
        await concluir_etapa(db_session, aluno_id=aluno, subtema_id=esperados[0].id, quando=agora)
        is False
    )


async def test_concluir_etapa_de_subtema_fora_do_roadmap_devolve_false(db_session):
    await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    assert (
        await concluir_etapa(
            db_session, aluno_id=aluno, subtema_id=999_999, quando=datetime.now(UTC)
        )
        is False
    )


async def test_roadmap_de_conteudo_vazio_e_vazio(db_session):
    aluno = uuid.uuid4()
    total = await gerar_roadmap(
        db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE
    )
    await db_session.commit()
    assert total == 0
