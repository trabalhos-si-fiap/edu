import httpx
import pytest

from app.core.email.base import EmailDeliveryError, EmailMessage
from app.core.email.resend import ResendEmailAdapter

_MSG = EmailMessage(to="user@example.com", subject="Code", html="<p>123456</p>", text="123456")


async def test_resend_posts_expected_payload_and_headers() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "email_123"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ResendEmailAdapter(api_key="re_test_key", sender="Edu <no-reply@edu.app>", client=client)

    await adapter.send(_MSG)
    await client.aclose()

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["auth"] == "Bearer re_test_key"
    body = captured["body"]
    assert body["from"] == "Edu <no-reply@edu.app>"
    assert body["to"] == ["user@example.com"]
    assert body["subject"] == "Code"
    assert body["html"] == "<p>123456</p>"
    assert body["text"] == "123456"


async def test_resend_raises_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "invalid"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ResendEmailAdapter(api_key="re_test_key", sender="Edu <no-reply@edu.app>", client=client)

    with pytest.raises(EmailDeliveryError):
        await adapter.send(_MSG)
    await client.aclose()


def test_resend_requires_api_key() -> None:
    with pytest.raises(ValueError):
        ResendEmailAdapter(api_key=None, sender="Edu <no-reply@edu.app>")
