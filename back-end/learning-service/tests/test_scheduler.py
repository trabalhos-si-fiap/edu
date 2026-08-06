import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Materia, Subtema, Tema
from app.scheduler import verificar_revisoes_pendentes


@pytest.fixture(autouse=True)
def _scheduler_no_banco_de_teste(test_session_factory, monkeypatch: pytest.MonkeyPatch):
    """Aponta o job para o banco de teste.

    `verificar_revisoes_pendentes` NÃO usa `get_db` — ela abre a própria
    sessão com `async_session`, que `app/database.py` liga a
    `settings.database_url` (o `learning_db` de desenvolvimento), não a
    `database_url_test`. Sem este remendo o job consulta o banco errado e
    não enxerga nada do que o teste semeou, então até o caso feliz falha
    com "publicou 0 eventos".

    O alvo é `app.scheduler.async_session` e não `app.database.async_session`
    (constraint 14): o `from app.database import async_session` do módulo já
    copiou a referência para o namespace do scheduler.
    """
    monkeypatch.setattr("app.scheduler.async_session", test_session_factory)


async def _seed_progresso_vencido(db_session, aluno_id: uuid.UUID) -> AlunoTemaProgresso:
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db_session.add(subtema)
    await db_session.flush()

    progresso = AlunoTemaProgresso(
        aluno_id=aluno_id,
        subtema_id=subtema.id,
        nivel_dominio=0.4,
        intervalo_dias=1.0,
        streak_acertos=0,
        proxima_revisao=datetime.now(UTC) - timedelta(hours=2),
        total_respondidas=5,
    )
    db_session.add(progresso)
    await db_session.commit()
    await db_session.refresh(progresso)
    return progresso


async def test_scheduler_publishes_a_due_revision(db_session, _stub_publish_event):
    aluno_id = uuid.uuid4()
    await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()

    assert len(_stub_publish_event) == 1
    routing_key, payload = _stub_publish_event[0]
    assert routing_key == "revision.scheduled"
    assert payload["aluno_id"] == str(aluno_id)


async def test_scheduler_does_not_republish_the_same_revision_the_next_day(
    db_session, _stub_publish_event
):
    """Sem marcar `ultima_revisao`, a mesma linha volta a casar todo dia."""
    aluno_id = uuid.uuid4()
    await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()
    await verificar_revisoes_pendentes()

    assert len(_stub_publish_event) == 1, "a segunda passada renotificou a mesma revisão"


async def test_scheduler_marks_the_revision_as_notified(db_session, _stub_publish_event):
    aluno_id = uuid.uuid4()
    progresso = await _seed_progresso_vencido(db_session, aluno_id)
    # Guardado ANTES do expire_all: depois dele, ler `progresso.id` dispara
    # um refresh preguiçoso fora do greenlet e estoura `MissingGreenlet`.
    progresso_id = progresso.id

    await verificar_revisoes_pendentes()

    # `expire_on_commit=False` na factory de teste: sem expirar, o re-SELECT
    # devolveria o objeto que já está no identity map desta sessão, com o
    # `ultima_revisao=None` de antes do job — verde ou vermelho por engano,
    # sem nunca olhar para o banco.
    db_session.expire_all()
    result = await db_session.execute(
        select(AlunoTemaProgresso).where(AlunoTemaProgresso.id == progresso_id)
    )
    atualizado = result.scalar_one()
    assert atualizado.ultima_revisao is not None
    assert atualizado.ultima_revisao >= atualizado.proxima_revisao


async def test_a_new_due_date_makes_the_revision_eligible_again(db_session, _stub_publish_event):
    """Responder de novo reabre a revisão, sem ninguém precisar zerar nada.

    A data nova tem que ser POSTERIOR ao `ultima_revisao` que o job acabou
    de carimbar — é isso que `/diagnostic/answer` faz ao gravar um
    `proxima_revisao` no futuro. Uma data anterior ao carimbo (ex.: "há um
    minuto") continua contando como já notificada, e é assim que se quer:
    é a mesma revisão de antes, não uma nova.
    """
    aluno_id = uuid.uuid4()
    progresso = await _seed_progresso_vencido(db_session, aluno_id)

    await verificar_revisoes_pendentes()
    assert len(_stub_publish_event) == 1

    progresso.proxima_revisao = datetime.now(UTC)
    await db_session.commit()

    await verificar_revisoes_pendentes()
    assert len(_stub_publish_event) == 2
