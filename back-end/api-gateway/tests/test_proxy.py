import httpx
import pytest


def _patch_upstream_request(monkeypatch, fake_upstream_request):
    """Substitui `httpx.AsyncClient.request` só para o cliente que o gateway
    cria internamente para chamar o serviço de destino.

    `httpx.AsyncClient.request` é um método de classe: o fixture `client`
    (Cap. tests/conftest.py) também é um `httpx.AsyncClient`, só que ligado
    a `ASGITransport` para bater direto na nossa app. Substituir o método
    sem essa checagem intercepta as DUAS chamadas — a do teste para o
    gateway e a do gateway para o serviço de destino — e a primeira nunca
    chega a executar a rota. Só o cliente sem `ASGITransport` (a chamada de
    saída de verdade) usa o fake; o resto segue intacto.
    """
    real_request = httpx.AsyncClient.request

    async def request(self, method, url, **kwargs):
        if isinstance(self._transport, httpx.ASGITransport):
            return await real_request(self, method, url, **kwargs)
        return await fake_upstream_request(method, url, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "request", request)


async def test_health_does_not_need_a_backend(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unmapped_path_returns_404_from_the_gateway(client):
    response = await client.get("/api/rota-inexistente")
    assert response.status_code == 404
    assert "Nenhum serviço mapeado" in response.json()["detail"]


async def test_proxy_forwards_method_body_and_query(client, monkeypatch):
    captured = {}

    async def fake_upstream_request(method, url, **kwargs):
        captured.update(method=method, url=url, content=kwargs["content"], params=kwargs["params"])
        return httpx.Response(201, json={"id": 1}, request=httpx.Request(method, url))

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    response = await client.post("/api/orders?dry_run=1", json={"total": "10.00"})

    assert response.status_code == 201
    assert response.json() == {"id": 1}
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/orders")
    assert b"total" in captured["content"]
    assert dict(captured["params"])["dry_run"] == "1"


async def test_proxy_returns_503_when_service_is_down(client, monkeypatch):
    async def fake_upstream_request(method, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    response = await client.get("/api/products")
    assert response.status_code == 503


async def test_proxy_returns_504_on_timeout(client, monkeypatch):
    async def fake_upstream_request(method, url, **kwargs):
        raise httpx.TimeoutException("too slow")

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    response = await client.get("/api/products")
    assert response.status_code == 504


@pytest.mark.parametrize("origin", ["http://localhost:3000", "https://app.edu.com"])
async def test_cors_allows_only_configured_origins(client, origin):
    from app.config import settings

    response = await client.options(
        "/api/products",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    allowed = response.headers.get("access-control-allow-origin")
    if origin in settings.cors_origins:
        assert allowed == origin
    else:
        assert allowed is None


async def test_cors_is_not_a_wildcard():
    from app.main import app as gateway_app

    cors = [m for m in gateway_app.user_middleware if "CORSMiddleware" in str(m)]
    assert cors, "CORS middleware ausente"
    assert "*" not in cors[0].kwargs["allow_origins"]
