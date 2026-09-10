from pathlib import Path

from sqlalchemy import func, select, text

from app.models.subtema import Materia, Subtema, Tema

SEED = Path(__file__).resolve().parents[1] / "scripts" / "seed_enem.sql"


async def _rodar_seed(db):
    # `text()` com um arquivo do próprio repositório, sem interpolação de
    # nada vindo do usuário — é execução de script, não montagem de query.
    # Split by semicolon porque asyncpg não permite múltiplos statements
    # numa única prepared statement.
    sql_content = SEED.read_text()
    for statement in sql_content.split(";"):
        statement = statement.strip()
        if statement:
            await db.execute(text(statement))
    await db.commit()


async def test_o_seed_existe_e_e_sql():
    assert SEED.exists()
    conteudo = SEED.read_text()
    assert "INSERT INTO materia" in conteudo
    assert "ON CONFLICT (id) DO NOTHING" in conteudo


async def test_o_seed_cria_a_estrutura_completa(db_session):
    await _rodar_seed(db_session)

    materias = (await db_session.execute(select(func.count()).select_from(Materia))).scalar_one()
    temas = (await db_session.execute(select(func.count()).select_from(Tema))).scalar_one()
    subtemas = (await db_session.execute(select(func.count()).select_from(Subtema))).scalar_one()
    assert materias == 11
    assert temas == 33
    assert subtemas == 99


async def test_toda_materia_tem_ao_menos_um_subtema(db_session):
    await _rodar_seed(db_session)

    orfas = (
        (
            await db_session.execute(
                select(Materia.nome)
                .outerjoin(Tema, Tema.materia_id == Materia.id)
                .outerjoin(Subtema, Subtema.tema_id == Tema.id)
                .group_by(Materia.id, Materia.nome)
                .having(func.count(Subtema.id) == 0)
            )
        )
        .scalars()
        .all()
    )
    assert orfas == []


async def test_toda_ordem_esta_preenchida(db_session):
    await _rodar_seed(db_session)

    temas_sem_ordem = (
        await db_session.execute(select(func.count()).select_from(Tema).where(Tema.ordem == 0))
    ).scalar_one()
    subtemas_sem_ordem = (
        await db_session.execute(
            select(func.count()).select_from(Subtema).where(Subtema.ordem == 0)
        )
    ).scalar_one()
    assert temas_sem_ordem == 0
    assert subtemas_sem_ordem == 0


async def test_o_seed_e_idempotente_em_duas_passadas(db_session):
    await _rodar_seed(db_session)
    await _rodar_seed(db_session)

    materias = (await db_session.execute(select(func.count()).select_from(Materia))).scalar_one()
    subtemas = (await db_session.execute(select(func.count()).select_from(Subtema))).scalar_one()
    assert materias == 11
    assert subtemas == 99


async def test_as_faixas_de_id_nao_invadem_o_seed_de_citologia(db_session):
    """`seed_biologia_citologia.sql` ocupa temas 1-3 e subtemas 1-8. Se o
    seed novo entrar nessa faixa, rodar os dois no mesmo banco perde
    linhas em silêncio pelo `ON CONFLICT DO NOTHING`."""
    await _rodar_seed(db_session)

    menor_tema = (await db_session.execute(select(func.min(Tema.id)))).scalar_one()
    menor_subtema = (await db_session.execute(select(func.min(Subtema.id)))).scalar_one()
    assert menor_tema >= 100
    assert menor_subtema >= 100
