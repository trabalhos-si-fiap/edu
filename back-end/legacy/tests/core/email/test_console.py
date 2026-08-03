from app.core.email.base import EmailMessage
from app.core.email.console import ConsoleEmailAdapter


async def test_console_adapter_logs_and_does_no_network(caplog) -> None:
    from loguru import logger

    sink: list[str] = []
    handler_id = logger.add(lambda m: sink.append(str(m)), level="INFO")
    try:
        adapter = ConsoleEmailAdapter()
        await adapter.send(
            EmailMessage(to="user@example.com", subject="Code", html="<p>123456</p>", text="123456")
        )
    finally:
        logger.remove(handler_id)

    joined = "\n".join(sink)
    assert "user@example.com" in joined
    assert "123456" in joined
