import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from sqlalchemy import select

from app.events import consumer as consumer_module
from app.models.notificacao import Notificacao

STUDENT_ID = "00000000-0000-0000-0000-000000000001"


def fake_message(payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


async def test_diagnostic_completed_creates_a_notification(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_diagnostic_completed(
        fake_message({"aluno_id": STUDENT_ID, "acao": "avancar", "dominio": 0.9})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "estudo"
    assert "avançar" in stored[0].descricao


async def test_order_status_changed_creates_a_notification(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"aluno_id": STUDENT_ID, "pedido_id": 7, "status": "EM_TRANSITO"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 7
    assert "entrega" in stored[0].descricao.lower()


async def test_revision_scheduled_creates_a_notification(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_revision_scheduled(fake_message({"aluno_id": STUDENT_ID}))

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "estudo"
    assert str(stored[0].aluno_id) == STUDENT_ID


async def test_stock_issue_creates_a_notification_with_pedido_and_ocorrencia(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_stock_issue(
        fake_message(
            {
                "aluno_id": STUDENT_ID,
                "pedido_id": 3,
                "ocorrencia_id": 9,
                "produtos_sugeridos": [],
            }
        )
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 3
    assert stored[0].ocorrencia_id == 9
    assert stored[0].tipo == "order_status"


async def test_delivery_delayed_creates_a_notification_with_pedido_and_ocorrencia(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_delivery_delayed(
        fake_message(
            {
                "aluno_id": STUDENT_ID,
                "pedido_id": 5,
                "ocorrencia_id": 11,
                "motivo": "Trânsito intenso",
            }
        )
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 5
    assert stored[0].ocorrencia_id == 11
    assert "Trânsito intenso" in stored[0].descricao


async def test_every_binding_points_to_a_real_handler():
    for queue_name, routing_key, handler in consumer_module.BINDINGS:
        assert queue_name and routing_key
        assert callable(handler)
