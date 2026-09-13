"""Pré-carga do modelo de embeddings ao subir o serviço.

Sem ela, o primeiro request que precisa do modelo pagava a carga inteira no
event loop — medido no ensaio da apresentação: 7 a 13 s na primeira chamada
de IA depois de um restart, e o scheduler do mesmo processo atrasava junto.
"""

import asyncio

from app import main
from app.config import settings
from app.services import embeddings


async def _nada_async() -> None:
    return None


async def test_precarregar_modelo_chama_a_carga_do_modelo(monkeypatch):
    chamadas: list[str] = []
    monkeypatch.setattr(embeddings, "_get_modelo", lambda: chamadas.append("carregou"))

    await embeddings.precarregar_modelo()

    assert chamadas == ["carregou"]


async def test_precarregar_modelo_engole_a_falha_de_carga(monkeypatch):
    """Sem internet e sem modelo no cache, a carga levanta. A pré-carga é só
    otimização: não pode derrubar a subida do serviço — o primeiro uso real
    tenta de novo e degrada como sempre degradou."""

    def _carga_que_falha():
        raise OSError("sem rede")

    monkeypatch.setattr(embeddings, "_get_modelo", _carga_que_falha)

    await embeddings.precarregar_modelo()


def _sem_infra(monkeypatch) -> None:
    monkeypatch.setattr(main, "init_publisher", _nada_async)
    monkeypatch.setattr(main, "start_consumer", _nada_async)
    monkeypatch.setattr(main, "close_consumer", _nada_async)
    monkeypatch.setattr(main, "close_publisher", _nada_async)
    monkeypatch.setattr(main, "start_scheduler", lambda: None)
    monkeypatch.setattr(main, "stop_scheduler", lambda: None)


async def test_lifespan_dispara_a_precarga_quando_habilitada(monkeypatch):
    _sem_infra(monkeypatch)
    monkeypatch.setattr(settings, "precarregar_embeddings", True)
    disparou = asyncio.Event()

    async def _precarga_falsa() -> None:
        disparou.set()

    monkeypatch.setattr(main, "precarregar_modelo", _precarga_falsa)

    async with main.lifespan(main.app):
        await asyncio.wait_for(disparou.wait(), timeout=1)


async def test_lifespan_nao_dispara_a_precarga_por_padrao(monkeypatch):
    """Default falso: a suíte e o host não carregam centenas de MB ao subir
    o app — só a imagem Docker liga a pré-carga."""
    _sem_infra(monkeypatch)
    disparou = asyncio.Event()

    async def _precarga_falsa() -> None:
        disparou.set()

    monkeypatch.setattr(main, "precarregar_modelo", _precarga_falsa)

    async with main.lifespan(main.app):
        await asyncio.sleep(0)

    assert not disparou.is_set()
