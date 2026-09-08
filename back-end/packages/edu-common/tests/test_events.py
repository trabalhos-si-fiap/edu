import json
from unittest.mock import AsyncMock, MagicMock

import aio_pika
import pytest

from edu_common.events import EventConsumer, EventPublisher

URL = "amqp://guest:guest@localhost/"
EXCHANGE = "edu.events"


@pytest.fixture
def fake_aio_pika(monkeypatch):
    exchange = AsyncMock()
    channel = AsyncMock()
    channel.declare_exchange = AsyncMock(return_value=exchange)
    queue = AsyncMock()
    channel.declare_queue = AsyncMock(return_value=queue)
    connection = AsyncMock()
    connection.channel = AsyncMock(return_value=channel)

    connect_robust = AsyncMock(return_value=connection)
    monkeypatch.setattr("edu_common.events.aio_pika.connect_robust", connect_robust)

    fake = MagicMock()
    fake.connect_robust = connect_robust
    fake.connection = connection
    fake.channel = channel
    fake.exchange = exchange
    fake.queue = queue
    return fake


async def test_publisher_declares_durable_topic_exchange(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()

    fake_aio_pika.connect_robust.assert_awaited_once_with(URL)
    name, *_ = fake_aio_pika.channel.declare_exchange.await_args.args
    kwargs = fake_aio_pika.channel.declare_exchange.await_args.kwargs
    assert name == EXCHANGE
    assert kwargs["durable"] is True


async def test_publisher_declares_exchange_type_topic(fake_aio_pika):
    """Regression guard for the exchange TYPE, not just its name/durability.

    The brief's own `test_publisher_declares_durable_topic_exchange` never
    asserts the exchange is a *topic* exchange — a direct/fanout exchange
    with the same name and `durable=True` would pass it silently. Topic
    routing is one of the four contract properties this package exists to
    guarantee for every consuming service (see events.py module docstring),
    so a dropped/mistyped exchange type must fail a test.
    """
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()

    args = fake_aio_pika.channel.declare_exchange.await_args.args
    assert args[1] == aio_pika.ExchangeType.TOPIC


async def test_publisher_sends_json_body_with_routing_key(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()
    await publisher.publish("order.created", {"pedido_id": 7, "aluno_id": "abc"})

    (message,) = fake_aio_pika.exchange.publish.await_args.args
    kwargs = fake_aio_pika.exchange.publish.await_args.kwargs
    assert kwargs["routing_key"] == "order.created"
    assert json.loads(message.body) == {"pedido_id": 7, "aluno_id": "abc"}
    assert message.content_type == "application/json"


async def test_publisher_sends_persistent_delivery_mode(fake_aio_pika):
    """The other contract property `test_publisher_sends_json_body_with_routing_key`
    never checks: a broker restart must not silently drop in-flight events.
    Non-persistent delivery would satisfy every assertion in that test while
    breaking the durability guarantee this package exists to centralize."""
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()
    await publisher.publish("order.created", {"pedido_id": 7})

    (message,) = fake_aio_pika.exchange.publish.await_args.args
    assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT


async def test_publish_before_connect_raises(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    with pytest.raises(RuntimeError, match="not connected"):
        await publisher.publish("order.created", {})


async def test_close_is_safe_when_never_connected(fake_aio_pika):
    await EventPublisher(URL, EXCHANGE).close()


async def test_close_closes_the_connection(fake_aio_pika):
    publisher = EventPublisher(URL, EXCHANGE)
    await publisher.connect()
    await publisher.close()
    fake_aio_pika.connection.close.assert_awaited_once()


async def test_consumer_binds_every_routing_key_to_one_queue(fake_aio_pika):
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    async def handler(message):
        return None

    await consumer.bind("analytics.event_log", ["order.created", "order.status_changed"], handler)

    work_queue_calls = [
        call
        for call in fake_aio_pika.channel.declare_queue.await_args_list
        if call.args[0] == "analytics.event_log"
    ]
    assert len(work_queue_calls) == 1
    assert work_queue_calls[0].kwargs["durable"] is True

    bound = [
        call.kwargs["routing_key"]
        for call in fake_aio_pika.queue.bind.await_args_list
        if "routing_key" in call.kwargs
    ]
    assert bound == ["order.created", "order.status_changed"]
    fake_aio_pika.queue.consume.assert_awaited_once_with(handler)


async def test_consumer_binds_multiple_queues_each_with_a_single_routing_key(fake_aio_pika):
    """Covers the other binding shape this package must support: the
    notification service binds five separate durable queues, each to exactly
    one routing key — as opposed to analytics's one queue bound to nine
    routing keys, already covered above. Both shapes call `bind()` the same
    way; this guards against an implementation that only handles one queue
    per consumer or that reuses/loses state across calls."""
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    async def handler(message):
        return None

    bindings = [
        ("notification.order_created", ["order.created"]),
        ("notification.order_status_changed", ["order.status_changed"]),
    ]
    for queue_name, routing_keys in bindings:
        await consumer.bind(queue_name, routing_keys, handler)

    work_queue_names = {"notification.order_created", "notification.order_status_changed"}
    work_queue_calls = [
        call
        for call in fake_aio_pika.channel.declare_queue.await_args_list
        if call.args[0] in work_queue_names
    ]
    declared_names = [call.args[0] for call in work_queue_calls]
    assert declared_names == ["notification.order_created", "notification.order_status_changed"]
    for call in work_queue_calls:
        assert call.kwargs["durable"] is True

    bound_keys = [
        call.kwargs["routing_key"]
        for call in fake_aio_pika.queue.bind.await_args_list
        if "routing_key" in call.kwargs
    ]
    assert bound_keys == ["order.created", "order.status_changed"]
    assert fake_aio_pika.queue.consume.await_count == 2


async def test_consumer_bind_before_connect_raises(fake_aio_pika):
    consumer = EventConsumer(URL, EXCHANGE)

    async def handler(message):
        return None

    with pytest.raises(RuntimeError, match="not connected"):
        await consumer.bind("q", ["k"], handler)


async def test_consumer_declares_a_durable_fanout_dead_letter_exchange(fake_aio_pika):
    """Sem DLX declarada, `requeue=False` DESCARTA a mensagem em silêncio.

    Fanout e não topic: a fila morta recebe tudo, venha de qual routing key
    vier. A chave original sobrevive no header `x-death`, então nada de
    diagnóstico se perde ao unificar o destino.
    """
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    chamadas = fake_aio_pika.channel.declare_exchange.await_args_list
    nomes = [c.args[0] for c in chamadas]
    assert f"{EXCHANGE}.dlx" in nomes, f"DLX não declarada; declaradas: {nomes}"

    dlx = next(c for c in chamadas if c.args[0] == f"{EXCHANGE}.dlx")
    assert dlx.args[1] == aio_pika.ExchangeType.FANOUT
    assert dlx.kwargs["durable"] is True


async def test_consumer_declares_a_durable_dead_letter_queue(fake_aio_pika):
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()

    chamadas = fake_aio_pika.channel.declare_queue.await_args_list
    nomes = [c.args[0] for c in chamadas]
    assert f"{EXCHANGE}.dead" in nomes, f"fila morta não declarada; declaradas: {nomes}"

    morta = next(c for c in chamadas if c.args[0] == f"{EXCHANGE}.dead")
    assert morta.kwargs["durable"] is True


async def test_bound_queues_point_at_the_dead_letter_exchange(fake_aio_pika):
    """A fila de trabalho precisa APONTAR para a DLX; declarar a DLX sozinha
    não redireciona nada."""
    consumer = EventConsumer(URL, EXCHANGE)
    await consumer.connect()
    await consumer.bind("notification.order_status_changed", ["order.status_changed"], AsyncMock())

    trabalho = next(
        c
        for c in fake_aio_pika.channel.declare_queue.await_args_list
        if c.args[0] == "notification.order_status_changed"
    )
    assert trabalho.kwargs["arguments"] == {"x-dead-letter-exchange": f"{EXCHANGE}.dlx"}
    assert trabalho.kwargs["durable"] is True
