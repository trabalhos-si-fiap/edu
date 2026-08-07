import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from sqlalchemy import select

from app.events import consumer as consumer_module
from app.models.event_log import EventLog


def _fake_message(routing_key: str, payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = routing_key

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


async def test_student_created_is_logged_without_name_or_email(
    db_session, test_session_factory, monkeypatch
):
    # app/database.py liga `async_session` ao banco real (settings.database_url);
    # sem este patch o handler grava no analytics_db de dev e a leitura abaixo,
    # feita na sessão de teste, nunca encontra a linha.
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_event(
        _fake_message(
            "student.created",
            {
                "aluno_id": "00000000-0000-0000-0000-000000000001",
                "nome": "Ana Souza",
                "email": "ana@example.com",
            },
        )
    )

    result = await db_session.execute(select(EventLog))
    registro = result.scalar_one()
    assert registro.payload == {"aluno_id": "00000000-0000-0000-0000-000000000001"}
    assert "nome" not in registro.payload
    assert "email" not in registro.payload


async def test_non_pii_payloads_are_stored_untouched(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    payload = {
        "pedido_id": 7,
        "aluno_id": "00000000-0000-0000-0000-000000000001",
        "valor_total": 199.9,
    }
    await consumer_module.handle_event(_fake_message("order.created", payload))

    result = await db_session.execute(select(EventLog))
    registro = result.scalar_one()
    assert registro.payload == payload


async def test_staff_created_is_logged_without_name(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_event(
        _fake_message(
            "staff.created",
            {
                "user_id": "00000000-0000-0000-0000-000000000002",
                "nome": "Bruno",
                "role": "separador",
            },
        )
    )

    result = await db_session.execute(select(EventLog))
    registro = result.scalar_one()
    assert registro.payload == {
        "user_id": "00000000-0000-0000-0000-000000000002",
        "role": "separador",
    }
