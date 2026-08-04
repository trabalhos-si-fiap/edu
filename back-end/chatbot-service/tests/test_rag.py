"""Testa `app/rag.py` diretamente: o caminho de falha do índice/encoder
(`inicializar_index`/`buscar_contexto`) que os testes de rota não
exercitam, porque lá o encoder é sempre o `_FakeEncoder` que funciona.
"""

import pytest

import app.rag as rag_module


async def test_buscar_contexto_raises_rag_indisponivel_when_the_encoder_fails(monkeypatch):
    """`inicializar_index` nunca propaga exceção (documentado em
    app/rag.py) — uma falha ao carregar o modelo vira `_indisponivel =
    True`, e é só `buscar_contexto` quem converte isso num
    `RagIndisponivelError` explícito para quem chama (`responder` →
    `app.main.chat_ask`, que mapeia pra um 503 limpo)."""

    def encoder_quebrado():
        raise RuntimeError("modelo indisponível (simulado no teste)")

    monkeypatch.setattr(rag_module, "_get_modelo_embeddings", encoder_quebrado)
    monkeypatch.setattr(rag_module, "_index", None)
    monkeypatch.setattr(rag_module, "_indisponivel", False)

    with pytest.raises(rag_module.RagIndisponivelError):
        rag_module.buscar_contexto("qualquer pergunta")

    assert rag_module._indisponivel is True
