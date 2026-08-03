"""Consumer de eventos do serviço — instância única sobre edu-common."""

import json

import aio_pika
from edu_common.events import EventConsumer

from app.config import settings
from app.database import async_session
from app.models.event_log import EventLog

# Todos os eventos relevantes de coreografia são gravados como log bruto.
# Endpoints de agregação fazem a leitura/filtragem em cima dessa tabela.
ROUTING_KEYS = [
    "student.created",
    "staff.created",
    "diagnostic.completed",
    "revision.scheduled",
    "order.created",
    "order.status_changed",
    "order.stock_issue",
    "order.delivery_delayed",
    "order.occurrence_resolved",
]

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def handle_event(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        tipo = message.routing_key

        async with async_session() as db:
            db.add(EventLog(tipo=tipo, payload=payload))
            await db.commit()


async def start_consumer() -> None:
    await _consumer.connect()
    await _consumer.bind("analytics.event_log", ROUTING_KEYS, handle_event)


async def close_consumer() -> None:
    await _consumer.close()
