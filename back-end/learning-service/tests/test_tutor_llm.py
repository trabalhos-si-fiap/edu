"""O tutor por LLM (Groq) nunca faz chamada real de rede nesta suíte: a
classe `AsyncGroq` é sempre substituída por um dublê."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services import tutor_llm

CONTEXTO = {
    "tema_nome": "Genética Básica",
    "acao": "retroceder",
    "tema_recomendado": None,
    "subtemas": [
        {"nome": "Leis de Mendel", "classificacao": "dominado"},
        {"nome": "Herança e Genótipo/Fenótipo", "classificacao": "estudar_do_zero"},
    ],
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


async def test_sem_api_key_nao_toca_no_groq(monkeypatch):
    monkeypatch.setattr(tutor_llm.settings, "groq_api_key", "")

    with patch("app.services.tutor_llm.AsyncGroq") as groq_cls:
        resultado = await tutor_llm.gerar_mensagem_tutor(CONTEXTO)

    groq_cls.assert_not_called()
    assert resultado is None


async def test_chamada_usa_modelo_disponivel_com_raciocinio_baixo(monkeypatch):
    """`llama-3.1-8b-instant` saiu do Groq — medido em 2026-09-13: 404
    `model_not_found`, engolido pelo `except`, e o relatório mostrava a
    mensagem de template. `openai/gpt-oss-20b` é modelo de raciocínio: sem
    `reasoning_effort="low"` o raciocínio consome o `max_tokens` e o
    conteúdo volta vazio."""
    monkeypatch.setattr(tutor_llm.settings, "groq_api_key", "fake-key-never-sent-to-groq")
    monkeypatch.setattr(tutor_llm, "_client", None)
    cliente = _cliente_falso("Mensagem do tutor.")

    with patch("app.services.tutor_llm.AsyncGroq", return_value=cliente):
        resultado = await tutor_llm.gerar_mensagem_tutor(CONTEXTO)

    assert resultado == "Mensagem do tutor."
    kwargs = cliente.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "openai/gpt-oss-20b"
    assert kwargs["reasoning_effort"] == "low"
