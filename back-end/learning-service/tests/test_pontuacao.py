import uuid

import pytest

from app.services.pontuacao import (
    PONTOS_ETAPA_CONCLUIDA,
    PONTOS_QUESTAO_CORRETA,
    PONTOS_REVISAO_NO_PRAZO,
    TETO_BONUS_STREAK,
    bonus_streak,
    nivel_do_total,
    registrar,
    total_de_pontos,
)


def test_a_tabela_de_pontos_e_a_da_spec():
    assert (PONTOS_QUESTAO_CORRETA, PONTOS_REVISAO_NO_PRAZO, PONTOS_ETAPA_CONCLUIDA) == (10, 15, 50)


@pytest.mark.parametrize(
    ("streak", "esperado"),
    [(0, 0), (1, 5), (5, 25), (10, 50), (11, 50), (1000, 50), (-3, 0)],
)
def test_bonus_de_sequencia_tem_teto(streak, esperado):
    assert bonus_streak(streak) == esperado
    assert bonus_streak(streak) <= TETO_BONUS_STREAK


@pytest.mark.parametrize(
    ("total", "nivel"),
    [
        (0, 1),
        (99, 1),
        (100, 2),
        (299, 2),
        (300, 3),
        (600, 4),
        (1000, 5),
        (1500, 6),
        (2100, 7),
        (2800, 8),
        (3600, 9),
        (4500, 10),
        (999_999, 10),
    ],
)
def test_nivel_nas_fronteiras_das_faixas(total, nivel):
    assert nivel_do_total(total) == nivel


async def test_registrar_grava_uma_vez_e_devolve_true(db_session):
    aluno = uuid.uuid4()
    assert (
        await registrar(db_session, aluno_id=aluno, origem="questao", referencia="7", pontos=10)
        is True
    )
    await db_session.commit()
    assert await total_de_pontos(db_session, aluno) == 10


async def test_registrar_a_mesma_referencia_de_novo_nao_pontua(db_session):
    aluno = uuid.uuid4()
    await registrar(db_session, aluno_id=aluno, origem="questao", referencia="7", pontos=10)
    await db_session.commit()

    assert (
        await registrar(db_session, aluno_id=aluno, origem="questao", referencia="7", pontos=10)
        is False
    )
    await db_session.commit()
    assert await total_de_pontos(db_session, aluno) == 10


async def test_alunos_diferentes_nao_disputam_a_mesma_referencia(db_session):
    a, b = uuid.uuid4(), uuid.uuid4()
    await registrar(db_session, aluno_id=a, origem="questao", referencia="7", pontos=10)
    await registrar(db_session, aluno_id=b, origem="questao", referencia="7", pontos=10)
    await db_session.commit()
    assert await total_de_pontos(db_session, a) == 10
    assert await total_de_pontos(db_session, b) == 10


async def test_total_de_aluno_sem_lancamento_e_zero(db_session):
    assert await total_de_pontos(db_session, uuid.uuid4()) == 0


async def test_registrar_nao_faz_commit(db_session):
    """Quem decide a transação é o chamador — na rota de resposta os pontos
    entram no MESMO commit que grava o progresso."""
    aluno = uuid.uuid4()
    await registrar(db_session, aluno_id=aluno, origem="etapa", referencia="3", pontos=50)
    await db_session.rollback()
    assert await total_de_pontos(db_session, aluno) == 0
