"""Consumer de eventos do serviço — instância única sobre edu-common."""

import json

import aio_pika
from edu_common.events import EventConsumer

from app.config import settings
from app.database import async_session
from app.models.event_log import EventLog

# Todos os eventos relevantes de coreografia são gravados como log, com as
# chaves de CHAVES_PII removidas na entrada (ver `_sem_pii` abaixo) — não é
# mais o payload bruto. Endpoints de agregação fazem a leitura/filtragem em
# cima dessa tabela.
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

# Chaves que nunca entram no log. `student.created` e `staff.created` carregam
# nome e e-mail; este serviço grava payload bruto de todo evento, com retenção
# infinita e sem nenhum endpoint que leia esses campos — era passivo puro.
#
# A lista é de CHAVES, não de eventos: um produtor futuro que mande `email`
# noutro evento também é filtrado, sem precisar lembrar de atualizar nada.
CHAVES_PII: frozenset[str] = frozenset({"nome", "email", "telefone", "documento"})


def _sem_pii(payload: dict) -> dict:
    """Remove as chaves de PII do primeiro nível do payload.

    Só o primeiro nível de propósito: nenhum evento de hoje aninha PII, e
    uma varredura recursiva sobre payload arbitrário é custo por evento sem
    ameaça correspondente. Se um produtor passar a aninhar, o teste que
    cobrir esse evento é quem tem que pegar.
    """
    return {chave: valor for chave, valor in payload.items() if chave not in CHAVES_PII}


_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def handle_event(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        tipo = message.routing_key

        async with async_session() as db:
            db.add(EventLog(tipo=tipo, payload=_sem_pii(payload)))
            await db.commit()


async def start_consumer() -> None:
    await _consumer.connect()
    await _consumer.bind("analytics.event_log", ROUTING_KEYS, handle_event)


async def close_consumer() -> None:
    await _consumer.close()
