"""Publisher e consumer da exchange de eventos, compartilhados entre serviços.

Substitui as cópias idênticas de `events/publisher.py` que existiam em auth,
commerce e learning, e o boilerplate de conexão dos consumers de notification
e analytics. O contrato da exchange vive aqui — mudá-lo num lugar só passa a
valer para todos os serviços que dependem deste pacote:

- exchange do tipo **topic**, **durável** (sobrevive a restart do broker);
- mensagens publicadas com **delivery_mode PERSISTENT** e corpo **JSON**;
- filas de consumo também **duráveis**, ligadas à exchange por routing key.

Nenhuma dessas quatro propriedades é opcional — são a razão de existir desta
classe em vez de cada serviço declarar sua própria exchange/fila.
"""

import json
from collections.abc import Awaitable, Callable

import aio_pika
from loguru import logger

Handler = Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[None]]


class _RabbitConnection:
    """Conexão robusta compartilhada por publisher e consumer.

    `rabbitmq_url` contém credenciais (`amqp://user:pass@host/`) — nunca é
    logada, nem aqui nem nas subclasses; só o nome da exchange/fila aparece
    nos logs.
    """

    def __init__(self, rabbitmq_url: str, exchange_name: str) -> None:
        self._url = rabbitmq_url
        self._exchange_name = exchange_name
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        logger.info("Conectado à exchange {}", self._exchange_name)

    async def close(self) -> None:
        # Seguro chamar mesmo sem nunca ter conectado (self._connection
        # continua None do __init__) — nenhum serviço precisa lembrar de
        # checar se connect() foi chamado antes de fazer cleanup.
        if self._connection is not None:
            await self._connection.close()
            self._connection = None


class EventPublisher(_RabbitConnection):
    async def publish(self, routing_key: str, payload: dict) -> None:
        if self._exchange is None:
            raise RuntimeError("EventPublisher not connected — call connect() first")
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key)


class EventConsumer(_RabbitConnection):
    async def bind(self, queue_name: str, routing_keys: list[str], handler: Handler) -> None:
        """Declara `queue_name` (durável) e liga cada routing key em `routing_keys`
        a ela antes de começar a consumir.

        Uma lista com um único elemento e chamadas repetidas com nomes de fila
        distintos são o mesmo caminho de código — funciona tanto para o
        analytics (uma fila, nove routing keys) quanto para o notification
        (cinco filas, uma routing key cada).
        """
        if self._channel is None or self._exchange is None:
            raise RuntimeError("EventConsumer not connected — call connect() first")
        queue = await self._channel.declare_queue(queue_name, durable=True)
        for routing_key in routing_keys:
            await queue.bind(self._exchange, routing_key=routing_key)
        await queue.consume(handler)
        logger.info("Fila {} ligada a {}", queue_name, routing_keys)
