"""Testes do consumer de eventos do learning-service.

B8: este módulo não existia. `app/events/consumer.py` era o único consumer
dos três serviços que consomem eventos sem teste nenhum — nem do handler,
nem do pareamento de `BINDINGS`, que notification e analytics já tinham.
Segue o formato de `notification-service/tests/test_consumer.py`.
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from edu_common.contracts import StudentCreated
from sqlalchemy import select

from app.events import consumer as consumer_module
from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Materia, Subtema, Tema

STUDENT_ID = "00000000-0000-0000-0000-000000000001"


def fake_message(payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


def student_created_payload(aluno_id: str) -> dict:
    """Construído pela MESMA definição que o produtor usa para publicar
    (`edu_common.contracts.StudentCreated`, montada em
    `auth-users-service/app/routers/auth.py`) — não por um literal local, que
    é justamente o padrão que deixou os consumidores cegos a uma renomeação
    do produtor (achado B8)."""
    return StudentCreated(
        aluno_id=aluno_id,
        nome="Maria Teste",
        email="maria@teste.com",
    ).to_payload()


async def _seed_subtemas(db_session, quantidade: int) -> None:
    materia = Materia(nome="Biologia")
    db_session.add(materia)
    await db_session.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db_session.add(tema)
    await db_session.flush()
    for i in range(quantidade):
        db_session.add(Subtema(tema_id=tema.id, nome=f"Subtema {i}", ordem=i))
    await db_session.commit()


async def test_student_created_initializes_progress_on_every_subtopic(
    db_session, test_session_factory, monkeypatch
):
    """O handler existe para dar ao aluno recém-criado uma linha de progresso
    zerada em TODO subtema do catálogo — é o que faz `/reviews/today` e as
    recomendações terem o que consultar no primeiro acesso."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _seed_subtemas(db_session, 3)

    await consumer_module.handle_student_created(fake_message(student_created_payload(STUDENT_ID)))

    stored = (await db_session.execute(select(AlunoTemaProgresso))).scalars().all()
    assert len(stored) == 3
    assert {str(p.aluno_id) for p in stored} == {STUDENT_ID}


async def test_student_created_with_an_empty_catalog_creates_nothing(
    db_session, test_session_factory, monkeypatch
):
    """Sem subtemas cadastrados o handler não pode inventar linhas — e também
    não pode estourar: o evento chega de outro serviço e uma exceção aqui
    deixaria a mensagem em loop de redelivery."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_student_created(fake_message(student_created_payload(STUDENT_ID)))

    stored = (await db_session.execute(select(AlunoTemaProgresso))).scalars().all()
    assert stored == []


async def test_every_binding_points_to_a_real_handler():
    """Compara `BINDINGS` contra o pareamento exato esperado — nome da fila,
    routing key e handler. Os dois testes acima chamam o handler direto e
    nunca passam por `BINDINGS`, então sem esta asserção nada pegaria uma
    routing key trocada: o serviço subiria ligado à chave errada e apenas
    deixaria de receber eventos, em silêncio.

    Fila e routing key vão como literais de propósito — importar a constante
    da própria implementação faria o teste seguir a mudança em vez de
    detectá-la.
    """
    expected = [
        ("learning.student_created", "student.created", consumer_module.handle_student_created),
    ]
    assert expected == consumer_module.BINDINGS
