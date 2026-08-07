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


async def test_oversized_body_is_rejected_before_reaching_a_service(client, monkeypatch):
    """O gateway bufferiza o corpo inteiro antes de qualquer auth. Sem teto,
    um POST não autenticado de megabytes já custa a memória.

    Usa `_patch_upstream_request` e não um `monkeypatch.setattr` direto em
    `httpx.AsyncClient.request`: o fixture `client` é um AsyncClient também,
    então o patch cru intercepta a chamada DO TESTE e o gateway nunca roda.
    """
    chamou = False

    async def fake_upstream_request(method, url, **kwargs):
        nonlocal chamou
        chamou = True
        raise AssertionError("o gateway repassou um corpo acima do teto")

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    # Literal de propósito (constraint 12): se alguém mudar o default da
    # config por engano, este teste avisa em vez de acompanhar a mudança.
    corpo = b"x" * (2 * 1024 * 1024 + 1)
    response = await client.post(
        "/api/auth/login", content=corpo, headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    assert not chamou


async def test_a_body_under_the_cap_still_passes_through(client, monkeypatch):
    recebido = {}

    async def fake_upstream_request(method, url, **kwargs):
        recebido["content"] = kwargs.get("content")
        return httpx.Response(200, json={"ok": True})

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    response = await client.post(
        "/api/auth/login", content=b"x" * 1024, headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
    # Prova que a requisição chegou de fato ao upstream, em vez de o stub ter
    # interceptado a chamada do próprio teste e devolvido 200 por engano.
    assert recebido["content"] == b"x" * 1024


async def test_a_chunked_body_without_content_length_is_capped_too(client, monkeypatch):
    """A segunda checagem é a que realmente vale.

    `Content-Length` é uma dica do cliente: pode faltar (corpo chunked) ou
    mentir. Com só a primeira checagem, este caso atravessava — medido.
    """
    chamou = False

    async def fake_upstream_request(method, url, **kwargs):
        nonlocal chamou
        chamou = True
        raise AssertionError("o gateway repassou um corpo chunked acima do teto")

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    async def corpo_em_pedacos():
        # 2 MiB + 1 em pedaços: sem Content-Length, o httpx manda chunked.
        for _ in range(2048):
            yield b"x" * 1024
        yield b"x"

    response = await client.post(
        "/api/auth/login",
        content=corpo_em_pedacos(),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert not chamou


async def test_the_cap_aborts_the_stream_instead_of_reading_the_whole_body(client, monkeypatch):
    """413 e "não repassou" não provam nada sobre o CUSTO da rejeição.

    O teste acima já passava contra a versão que fazia `await
    request.body()`: o corpo inteiro chegava à memória do processo e SÓ
    ENTÃO virava 413 — que é justamente o custo que o teto existe para
    evitar. A única afirmação que separa as duas implementações é quantos
    pedaços do corpo o gateway chegou a puxar.

    Este teste mede isso contando o que o gerador cedeu. O `ASGITransport`
    do httpx 0.28.1 puxa cada pedaço sob demanda, um `receive()` por
    `__anext__()` (`httpx/_transports/asgi.py`), então um gerador que não
    for consumido até o fim é observável daqui.
    """
    chamou = False

    async def fake_upstream_request(method, url, **kwargs):
        nonlocal chamou
        chamou = True
        raise AssertionError("o gateway repassou um corpo acima do teto")

    _patch_upstream_request(monkeypatch, fake_upstream_request)

    # 20 x 200_000 = 4 MB, quase o dobro do teto de 2 MiB. O teto é
    # ultrapassado no 11o pedaço (11 x 200_000 = 2_200_000 > 2_097_152),
    # então uma implementação incremental para bem antes do fim.
    pedacos_totais = 20
    cedidos = 0

    async def corpo_grande():
        nonlocal cedidos
        for _ in range(pedacos_totais):
            cedidos += 1
            yield b"x" * 200_000

    response = await client.post(
        "/api/auth/login",
        content=corpo_grande(),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert not chamou
    assert cedidos < pedacos_totais, (
        f"o gateway puxou o corpo inteiro ({cedidos} de {pedacos_totais} pedaços) "
        "antes de devolver o 413"
    )
