"""A explicação de questão por LLM (Groq) nunca faz chamada real de rede
nesta suíte: o cliente é sempre um dublê."""

from unittest.mock import AsyncMock, MagicMock, patch

from app import rag
from app.services import explicacao_questao

CONTEXTO = {
    "subtema_nome": "Leis de Mendel",
    "enunciado": "Qual a proporção fenotípica esperada em F2?",
    "alternativas": {"A": "1:1", "B": "3:1", "C": "9:3:3:1", "D": "1:2:1"},
    "gabarito": "B",
    "alternativa_escolhida": "A",
    "acertou": False,
}


def _cliente_falso(conteudo: str) -> MagicMock:
    mensagem = MagicMock()
    mensagem.content = conteudo
    escolha = MagicMock()
    escolha.message = mensagem
    resposta = MagicMock()
    resposta.choices = [escolha]
    cliente = MagicMock()
    cliente.chat.completions.create = AsyncMock(return_value=resposta)
    return cliente


async def test_explicacao_usa_modelo_disponivel_com_raciocinio_baixo(monkeypatch):
    """`llama-3.1-8b-instant` saiu do Groq (medido em 2026-09-13: 404
    `model_not_found`). `openai/gpt-oss-20b` é modelo de raciocínio: sem
    `reasoning_effort="low"` o conteúdo volta vazio e esta função levanta."""
    monkeypatch.setattr(explicacao_questao, "_client", None)
    cliente = _cliente_falso("Explicação.")

    with patch("app.services.explicacao_questao.AsyncGroq", return_value=cliente):
        resultado = await explicacao_questao.explicar_questao(CONTEXTO)

    assert resultado == "Explicação."
    kwargs = cliente.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "openai/gpt-oss-20b"
    assert kwargs["reasoning_effort"] == "low"


async def test_rag_usa_modelo_disponivel_com_raciocinio_baixo(monkeypatch):
    monkeypatch.setattr(rag, "buscar_contexto", lambda pergunta: ["Troca em até 7 dias."])
    cliente = _cliente_falso("Resposta.")

    with patch("app.rag.AsyncGroq", return_value=cliente):
        resultado = await rag.responder("Qual o prazo de troca?")

    assert resultado == "Resposta."
    kwargs = cliente.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "openai/gpt-oss-20b"
    assert kwargs["reasoning_effort"] == "low"
