import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.events import consumer as consumer_module
from app.models.event_log import EventLog


def headers_for(role: str) -> dict[str, str]:
    token = create_access_token("00000000-0000-0000-0000-000000000001", role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_analytics_requires_authentication(client):
    assert (await client.get("/analytics/anomalies")).status_code == 403


async def test_analytics_forbids_students(client):
    response = await client.get("/analytics/anomalies", headers=headers_for("student"))
    assert response.status_code == 403


async def test_analytics_allows_admin(client):
    response = await client.get("/analytics/anomalies", headers=headers_for("admin"))
    assert response.status_code == 200


async def test_public_paths_are_english(client):
    """O contrato público é em inglês (design doc, "Regra de contrato").
    Literais aqui de propósito: importar as rotas do router faria o teste
    concordar com qualquer renomeação futura em vez de barrá-la."""
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert sorted(p for p in paths if p.startswith("/analytics")) == [
        "/analytics/anomalies",
        "/analytics/deliveries",
        "/analytics/executive-summary",
        "/analytics/students/{aluno_id}",
        "/analytics/summary",
    ]


async def test_every_analytics_route_is_admin_only(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    for path in paths:
        if not path.startswith("/analytics"):
            continue
        response = await client.get(path, headers=headers_for("student"))
        assert response.status_code in (403, 405), f"{path} não é admin-only"


def fake_message(routing_key: str, payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = routing_key

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


async def test_consumer_logs_the_raw_event(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_event(fake_message("order.created", {"pedido_id": 7}))

    stored = (await db_session.execute(select(EventLog))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "order.created"
    assert stored[0].payload == {"pedido_id": 7}
