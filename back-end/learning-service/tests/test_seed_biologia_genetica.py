from pathlib import Path

from sqlalchemy import func, select, text

from app.models.questao import Questao

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SEED = SCRIPTS / "seed_biologia_genetica.sql"
SEED_CITOLOGIA = SCRIPTS / "seed_biologia_citologia.sql"

# "Leis de Mendel" e "Herança e Genótipo/Fenótipo", criados por
# `seed_biologia_citologia.sql` com duas questões cada.
SUBTEMAS_GENETICA = (7, 8)
QUESTOES_DA_CITOLOGIA = 26
ALTERNATIVAS = {"A", "B", "C", "D"}


async def _rodar(db, arquivo: Path) -> None:
    # Mesmo carregador de `test_seed_enem.py`: `text()` com um arquivo do
    # próprio repositório, sem nada vindo do usuário, dividido por ponto e
    # vírgula porque o asyncpg não aceita vários statements num prepare só.
    for statement in arquivo.read_text().split(";"):
        statement = statement.strip()
        if statement:
            await db.execute(text(statement))
    await db.commit()


async def _rodar_os_dois(db) -> set[int]:
    """Aplica a citologia (dona dos subtemas 7 e 8) e depois a genética.
    Devolve os ids que a genética acrescentou."""
    await _rodar(db, SEED_CITOLOGIA)
    antes = set((await db.execute(select(Questao.id))).scalars().all())
    await _rodar(db, SEED)
    depois = set((await db.execute(select(Questao.id))).scalars().all())
    return depois - antes


async def _questoes_novas(db, ids: set[int]) -> list[Questao]:
    return list(
        (await db.execute(select(Questao).where(Questao.id.in_(ids)).order_by(Questao.id)))
        .scalars()
        .all()
    )


async def test_o_seed_existe_e_e_sql():
    assert SEED.exists()
    conteudo = SEED.read_text()
    assert "INSERT INTO questao" in conteudo
    assert "ON CONFLICT (id) DO NOTHING" in conteudo


async def test_o_seed_acrescenta_quatro_questoes_a_cada_subtema_de_genetica(db_session):
    novos = await _rodar_os_dois(db_session)

    por_subtema = dict(
        (
            await db_session.execute(
                select(Questao.subtema_id, func.count())
                .where(Questao.subtema_id.in_(SUBTEMAS_GENETICA))
                .group_by(Questao.subtema_id)
            )
        ).all()
    )
    assert len(novos) == 8
    assert por_subtema == {7: 6, 8: 6}


async def test_o_seed_e_idempotente_em_duas_passadas(db_session):
    await _rodar_os_dois(db_session)
    await _rodar(db_session, SEED)

    total = (await db_session.execute(select(func.count()).select_from(Questao))).scalar_one()
    assert total == QUESTOES_DA_CITOLOGIA + 8


async def test_as_faixas_de_id_nao_invadem_o_seed_de_citologia(db_session):
    """`seed_enem.sql` registra que a citologia ocupa as questões 1-38
    (medido no banco, não só no arquivo). Um id nessa faixa perderia a
    questão em silêncio pelo `ON CONFLICT DO NOTHING`."""
    novos = await _rodar_os_dois(db_session)

    assert min(novos) > 38


async def test_toda_questao_nova_tem_o_formato_das_existentes(db_session):
    novos = await _rodar_os_dois(db_session)

    for questao in await _questoes_novas(db_session, novos):
        assert questao.subtema_id in SUBTEMAS_GENETICA
        assert set(questao.alternativas) == ALTERNATIVAS, questao.id
        assert all(v.strip() for v in questao.alternativas.values()), questao.id
        assert questao.gabarito in ALTERNATIVAS, questao.id
        assert 1 <= questao.nivel_dificuldade <= 3
        assert questao.fonte == "Original (estilo ENEM)"
        assert questao.ano is None


async def test_cada_subtema_mistura_niveis_de_dificuldade(db_session):
    """O quiz de Genética só aponta lacuna se o aluno puder errar alguma:
    quatro questões do mesmo nível não distinguem quem sabe de quem não."""
    novos = await _rodar_os_dois(db_session)
    questoes = await _questoes_novas(db_session, novos)

    for subtema_id in SUBTEMAS_GENETICA:
        niveis = {q.nivel_dificuldade for q in questoes if q.subtema_id == subtema_id}
        assert len(niveis) >= 2, subtema_id
        assert 3 in niveis, subtema_id


async def test_a_sequence_fica_depois_do_ultimo_id_do_seed(db_session):
    """Sem o `setval` do fim, a próxima questão gravada pela API sairia da
    sequence da citologia e colidiria com esta faixa quando chegasse nela."""
    novos = await _rodar_os_dois(db_session)

    proximo = (await db_session.execute(text("SELECT nextval('questao_id_seq')"))).scalar_one()
    assert proximo > max(novos)
