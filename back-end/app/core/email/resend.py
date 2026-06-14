import httpx

from app.core.email.base import EmailDeliveryError, EmailMessage


class ResendEmailAdapter:
    """Adapter for the Resend HTTP API (https://resend.com/docs)."""

    _ENDPOINT = "https://api.resend.com/emails"

    def __init__(
        self,
        api_key: str | None,
        sender: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("RESEND_API_KEY is required for the resend email backend")
        self._api_key = api_key
        self._sender = sender
        # Injectable client for tests (httpx.MockTransport); None => own client.
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        payload = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(self._ENDPOINT, json=payload, headers=headers)
        finally:
            if self._client is None:
                await client.aclose()

        if response.status_code >= 400:
            raise EmailDeliveryError(
                f"resend returned {response.status_code}: {response.text}"
            )
