import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.objetivo import ObjetivoAluno
from app.models.pontuacao import LancamentoPontos
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _um_subtema(db):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db.add(subtema)
    await db.flush()
    return subtema


async def test_um_objetivo_por_aluno(db_session):
    aluno = uuid.uuid4()
    db_session.add(ObjetivoAluno(aluno_id=aluno, titulo="Medicina", data_alvo=date(2027, 11, 7)))
    await db_session.commit()

    db_session.add(ObjetivoAluno(aluno_id=aluno, titulo="Direito", data_alvo=date(2027, 11, 7)))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_uma_etapa_por_aluno_e_subtema(db_session):
    aluno = uuid.uuid4()
    subtema = await _um_subtema(db_session)
    db_session.add(
        EtapaRoadmap(aluno_id=aluno, subtema_id=subtema.id, ordem=0, prazo=date(2027, 1, 1))
    )
    await db_session.commit()

    db_session.add(
        EtapaRoadmap(aluno_id=aluno, subtema_id=subtema.id, ordem=1, prazo=date(2027, 2, 1))
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_lancamento_e_idempotente_por_origem_e_referencia(db_session):
    aluno = uuid.uuid4()
    db_session.add(LancamentoPontos(aluno_id=aluno, origem="questao", referencia="7", pontos=10))
    await db_session.commit()

    db_session.add(LancamentoPontos(aluno_id=aluno, origem="questao", referencia="7", pontos=10))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_a_mesma_referencia_em_origens_diferentes_convive(db_session):
    aluno = uuid.uuid4()
    db_session.add(LancamentoPontos(aluno_id=aluno, origem="questao", referencia="7", pontos=10))
    db_session.add(LancamentoPontos(aluno_id=aluno, origem="etapa", referencia="7", pontos=50))
    await db_session.commit()  # não levanta


async def test_etapa_nasce_sem_conclusao(db_session):
    aluno = uuid.uuid4()
    subtema = await _um_subtema(db_session)
    etapa = EtapaRoadmap(aluno_id=aluno, subtema_id=subtema.id, ordem=0, prazo=date(2027, 1, 1))
    db_session.add(etapa)
    await db_session.commit()
    assert etapa.concluida_em is None
