"""Publisher de eventos do serviço — instância única sobre edu-common."""

from edu_common.events import EventPublisher

from app.config import settings

_publisher = EventPublisher(settings.rabbitmq_url, settings.exchange_name)


async def init_publisher() -> None:
    await _publisher.connect()


async def publish_event(routing_key: str, payload: dict) -> None:
    await _publisher.publish(routing_key, payload)


async def close_publisher() -> None:
    await _publisher.close()
