"""Testa `get_me` diretamente, sem subir servidor nenhum e sem rede real —
espelha `chatbot-service/tests/test_diagnostico_client.py`: lá o alvo é a
lógica interna do cliente (URL exata montada, mapeamento de status para
exceção), que nenhum teste de rota exercita porque as rotas stubam esta
função no nível do chamador (`app.routers.produtos.get_me`, ver Constraint 14
do task-B7-brief.md).

Diferença em relação ao diagnostico_client: `get_me` não distingue 403/404 do
upstream — QUALQUER status de erro ou falha de conexão vira o mesmo
`AuthServiceUnavailableError` (503), porque não há "aluno não respondeu essa
questão" aqui, só "consegui falar com o auth-users-service" ou não.
"""

import uuid

import httpx
import pytest

from app.services.auth_client import AuthServiceUnavailableError, get_address, get_me


async def test_get_me_forwards_the_students_bearer(monkeypatch):
    capturado = {}

    class _RespostaFalsa:
        status_code = 200

        def json(self):
            return {"id": "x", "name": "Ana", "email": "a@b.c", "role": "student"}

        def raise_for_status(self):
            pass

    class _ClienteFalso:
        def __init__(self, **kwargs):
            capturado["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            capturado["url"] = url
            capturado["headers"] = headers
            return _RespostaFalsa()

    monkeypatch.setattr("app.services.auth_client.httpx.AsyncClient", _ClienteFalso)

    resultado = await get_me("token-do-aluno")

    assert resultado["name"] == "Ana"
    assert capturado["headers"]["Authorization"] == "Bearer token-do-aluno"
    assert capturado["url"].endswith("/auth/me")
    assert capturado["timeout"] == 10.0


async def test_get_me_never_puts_the_raw_token_in_the_error(monkeypatch):
    """O token bruto não pode aparecer em corpo de erro nem em log.

    Cobre o `except httpx.HTTPError` (o mais genérico, atrás do
    `except httpx.HTTPStatusError` — `ConnectError` não é `HTTPStatusError`,
    então cai aqui). `assert "segredo..." not in str(exc.value)` sozinho NÃO
    trava o `from None` daquele `except`: a mensagem da exceção é a string
    estática `"auth-users-service indisponível"`, nunca contém o token,
    então esse assert passa mesmo com `from exc` — medido na Rodada de
    correção 1 (ver task-B7-report.md). `exc.value.__cause__ is None` é o
    que de fato falha se `from None` virar `from exc`.
    """

    class _ClienteQueFalha:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            raise httpx.ConnectError("recusado")

    monkeypatch.setattr("app.services.auth_client.httpx.AsyncClient", _ClienteQueFalha)

    with pytest.raises(AuthServiceUnavailableError) as exc:
        await get_me("segredo-nao-pode-vazar")

    assert "segredo-nao-pode-vazar" not in str(exc.value)
    assert exc.value.__cause__ is None


async def test_get_me_raises_when_auth_service_responds_with_an_error_status(monkeypatch):
    """Cobre o ramo `except httpx.HTTPStatusError`, que o teste de conexão
    recusada acima não exercita (`ConnectError` é `HTTPError`, não
    `HTTPStatusError` — sobe direto para o segundo `except`).

    `exc.value.__cause__ is None` trava o `from None` DESTE `except`
    especificamente — é um caminho distinto do `except httpx.HTTPError` que
    o teste acima cobre, e cada um precisa da sua própria trava (Rodada de
    correção 1, ver task-B7-report.md)."""

    class _RespostaComErro:
        status_code = 500

        def raise_for_status(self):
            request = httpx.Request("GET", "http://auth-users-service:8000/auth/me")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("erro upstream", request=request, response=response)

    class _ClienteComErro:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return _RespostaComErro()

    monkeypatch.setattr("app.services.auth_client.httpx.AsyncClient", _ClienteComErro)

    with pytest.raises(AuthServiceUnavailableError) as exc:
        await get_me("outro-segredo-nao-pode-vazar")

    assert "outro-segredo-nao-pode-vazar" not in str(exc.value)
    assert exc.value.__cause__ is None


# Os testes de `get_address` abaixo usam um dublê genérico (`_cliente_falso` /
# `_Resposta`) em vez do dublê próprio de cada teste de `get_me` acima. Não é
# inconsistência para "limpar": o dublê do ramo `HTTPStatusError` de `get_me`
# constrói `httpx.Request`/`httpx.Response` reais de propósito (garante que o
# código sob teste funciona contra objetos httpx de verdade), enquanto
# `_Resposta` aqui passa `request=None` — mais simples, mas não trocável pelo
# dublê de `get_me` sem perder o que aquele garante. Duas formas no mesmo
# arquivo, cada uma pagando por algo diferente.
def _cliente_falso(resposta=None, erro=None, capturado=None):
    """Dublê de `httpx.AsyncClient` no mesmo formato do teste de `get_me`.

    Um só helper para os três testes abaixo: ou devolve `resposta`, ou
    levanta `erro`, e registra url/headers em `capturado`.
    """

    class _Cliente:
        def __init__(self, **kwargs):
            if capturado is not None:
                capturado["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            if capturado is not None:
                capturado["url"] = url
                capturado["headers"] = headers
            if erro is not None:
                raise erro
            return resposta

    return _Cliente


class _Resposta:
    def __init__(self, status_code, corpo=None):
        self.status_code = status_code
        self._corpo = corpo or {}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(str(self.status_code), request=None, response=self)


async def test_get_address_returns_none_on_404(monkeypatch):
    """404 é "endereço inválido" (400 no checkout), não "auth fora do ar"."""
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient",
        _cliente_falso(resposta=_Resposta(404, {"detail": "Endereço não encontrado"})),
    )
    assert await get_address("token", uuid.uuid4()) is None


async def test_get_address_raises_when_auth_is_down(monkeypatch):
    """Cobre o `except httpx.HTTPError` de `get_address` — mesmo caminho de
    `test_get_me_never_puts_the_raw_token_in_the_error`, `__cause__ is None`
    é o que de fato trava o `from None`, já que a mensagem da exceção é uma
    string estática e passaria mesmo com `from exc`."""
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient",
        _cliente_falso(erro=httpx.ConnectError("recusado")),
    )
    with pytest.raises(AuthServiceUnavailableError) as exc:
        await get_address("token", uuid.uuid4())
    assert exc.value.__cause__ is None


async def test_get_address_raises_on_a_server_error(monkeypatch):
    """5xx do auth não pode virar "endereço inválido" — o endereço pode
    existir perfeitamente.

    Cobre o `except httpx.HTTPStatusError` de `get_address`, caminho distinto
    do teste acima — `__cause__ is None` trava o `from None` deste ramo
    especificamente."""
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient", _cliente_falso(resposta=_Resposta(500))
    )
    with pytest.raises(AuthServiceUnavailableError) as exc:
        await get_address("token", uuid.uuid4())
    assert exc.value.__cause__ is None


async def test_get_address_forwards_the_bearer(monkeypatch):
    capturado: dict = {}
    address_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient",
        _cliente_falso(
            resposta=_Resposta(200, {"street": "Av. Paulista", "city": "São Paulo"}),
            capturado=capturado,
        ),
    )

    resultado = await get_address("token-do-aluno", address_id)

    assert resultado["street"] == "Av. Paulista"
    assert capturado["headers"]["Authorization"] == "Bearer token-do-aluno"
    assert capturado["url"].endswith(f"/auth/addresses/{address_id}")
    assert capturado["timeout"] == 10.0
