"""Testa `buscar_contexto_questao` diretamente contra um transporte HTTP
falso (`httpx.MockTransport`) — sem subir servidor nenhum, sem rede real.

Complementa `test_chat_routes.py`: lá o alvo é o CONTRATO da rota (o
Chatbot Service repassa o token certo); aqui o alvo é a lógica interna
deste cliente (a URL exata que ele monta, e o mapeamento de cada status de
resposta do Learning Service para `DiagnosticoContextoError`), que nenhum
teste de rota exercita porque todos stubam esta função no nível do
chamador (`app.main.buscar_contexto_questao`).
"""

import httpx
import pytest

from app.config import settings
from app.services.diagnostico_client import DiagnosticoContextoError, buscar_contexto_questao

_RealAsyncClient = httpx.AsyncClient  # captured BEFORE any patch, to avoid self-recursion below


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Substitui `httpx.AsyncClient(timeout=...)` por um cliente real
    plugado num `MockTransport` — nenhum socket é aberto. O alvo é
    `app.services.diagnostico_client.httpx.AsyncClient`: `import httpx`
    nesse módulo vincula o nome ao MÓDULO `httpx` de verdade (não uma
    cópia de função como `AsyncGroq`/`publish_event`), então isso também
    afeta o `httpx` real pela duração do teste — `monkeypatch` desfaz
    automaticamente no teardown. A factory usa `_RealAsyncClient` (capturado
    ANTES do patch), não `httpx.AsyncClient`: chamar o nome já remendado de
    dentro dele mesmo recursaria infinitamente.
    """

    def factory(*args, **kwargs):
        return _RealAsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.services.diagnostico_client.httpx.AsyncClient", factory, raising=True)


async def test_it_requests_the_exact_current_learning_service_path(monkeypatch):
    """Trava a URL real: `/diagnostic/questions/{id}/context`, renomeada
    pela task 9 do plano de migração — confirmado contra o código real em
    back-end/learning-service/app/routers/diagnostico.py:247
    (`@router.get("/questions/{questao_id}/context")` sob
    `router = APIRouter(prefix="/diagnostic", ...)`). A URL antiga
    (`/diagnostico/questoes/{id}/contexto`) que o zip original montava não
    existe mais no Learning Service.
    """
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["auth_header"] = request.headers.get("authorization")
        return httpx.Response(200, json={"questao_id": 5, "acertou": True})

    _patch_transport(monkeypatch, handler)

    await buscar_contexto_questao(5, "um-token-de-teste")

    assert captured["url"] == f"{settings.learning_service_url}/diagnostic/questions/5/context"
    assert captured["method"] == "GET"
    assert captured["auth_header"] == "Bearer um-token-de-teste"


async def test_it_returns_the_parsed_json_on_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"questao_id": 5, "acertou": True})

    _patch_transport(monkeypatch, handler)

    contexto = await buscar_contexto_questao(5, "token")
    assert contexto == {"questao_id": 5, "acertou": True}


async def test_it_maps_upstream_403_to_a_403(monkeypatch):
    """403 do Learning Service = "esse aluno ainda não respondeu essa
    questão" — precisa continuar sendo um 403 no Chatbot Service, não um
    502/500 genérico que esconderia o motivo real da recusa."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "..."})

    _patch_transport(monkeypatch, handler)

    with pytest.raises(DiagnosticoContextoError) as exc_info:
        await buscar_contexto_questao(5, "token")
    assert exc_info.value.status_code == 403


async def test_it_maps_upstream_404_to_a_404(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "..."})

    _patch_transport(monkeypatch, handler)

    with pytest.raises(DiagnosticoContextoError) as exc_info:
        await buscar_contexto_questao(5, "token")
    assert exc_info.value.status_code == 404


async def test_it_maps_an_unexpected_upstream_status_to_a_502(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    _patch_transport(monkeypatch, handler)

    with pytest.raises(DiagnosticoContextoError) as exc_info:
        await buscar_contexto_questao(5, "token")
    assert exc_info.value.status_code == 502


async def test_it_maps_a_connection_failure_to_a_503(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused (simulado no teste)", request=request)

    _patch_transport(monkeypatch, handler)

    with pytest.raises(DiagnosticoContextoError) as exc_info:
        await buscar_contexto_questao(5, "token")
    assert exc_info.value.status_code == 503
