"""Prova de que a suíte PRECISA da fixture `_stub_publish_event`
(tests/conftest.py) e de que ela remenda o alvo certo.

`ASGITransport` nunca roda o lifespan do app, então `init_publisher()` nunca
é chamado e a instância real de `EventPublisher` (`app/events/publisher.py`)
nunca conecta — qualquer rota que aguarde `publish_event` sem o stub
estouraria `RuntimeError` depois de já ter gravado no banco (ver docstring
da fixture). Sem este teste, um alvo de monkeypatch errado (ex.: remendar
`app.events.publisher.publish_event`, que não afeta as cópias importadas por
`from app.events.publisher import publish_event` em cada router) passaria
despercebido até a próxima task exercitar essas rotas.
"""

import pytest

from app.routers import ocorrencias, pedidos, separacao


async def test_publish_event_without_stub_raises_when_publisher_never_connected():
    """Sem a fixture (chamada direta, fora do `client`), confirma o "antes":
    a instância real nunca conectou nesta suíte, então publicar estoura.
    """
    with pytest.raises(RuntimeError, match="not connected"):
        await pedidos.publish_event("test.key", {})


async def test_stub_publish_event_patches_all_three_router_call_sites(_stub_publish_event):
    """Com o stub ativo, os três pontos de import — pedidos, ocorrencias,
    separacao — não estouram mais. Os três são chamados explicitamente
    (não só `pedidos`) porque cada `from app.events.publisher import
    publish_event` copia a referência para o namespace do módulo que
    importa; remendar só `app.events.publisher.publish_event` não afetaria
    nenhuma dessas cópias.
    """
    await pedidos.publish_event("test.key", {})
    await ocorrencias.publish_event("test.key", {})
    await separacao.publish_event("test.key", {})
