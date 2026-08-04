"""Consumer de eventos do serviço — instância única sobre edu-common."""

import json

import aio_pika
from edu_common.events import EventConsumer, Handler
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Subtema

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def handle_student_created(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        aluno_id = payload["aluno_id"]

        async with async_session() as db:
            result = await db.execute(select(Subtema))
            subtemas = result.scalars().all()

            for subtema in subtemas:
                db.add(AlunoTemaProgresso(aluno_id=aluno_id, subtema_id=subtema.id))
            await db.commit()


# Extraído do antigo `start_consumer` monolítico para constante de módulo —
# cada tupla é (nome da fila, routing key, handler). Hoje só um binding
# (aluno criado no Auth+Users Service -> inicializa progresso zerado em
# todos os subtemas), mas o formato já suporta N bindings sem mudar
# `start_consumer`.
BINDINGS: list[tuple[str, str, Handler]] = [
    ("learning.student_created", "student.created", handle_student_created),
]


async def start_consumer() -> None:
    await _consumer.connect()
    for queue_name, routing_key, handler in BINDINGS:
        await _consumer.bind(queue_name, [routing_key], handler)


async def close_consumer() -> None:
    await _consumer.close()
