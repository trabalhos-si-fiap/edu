"""Prova de que o resumo executivo por LLM (Groq) nunca faz chamada real de
rede nesta suíte: a classe `AsyncGroq` é sempre substituída por um dublê.

Cobre a exigência do contexto da task 14 — Groq é uma API paga externa;
nenhum teste pode chamá-la de verdade, e a ausência de `GROQ_API_KEY` tem
que degradar para o fallback local por template, não falhar.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services import resumo_ia

CONTEXTO = {
    "periodo_dias": 7,
    "pedidos_criados": 10,
    "pedidos_por_status": {"ENTREGUE": 5},
    "ocorrencias_abertas": 1,
    "ocorrencias_resolvidas": 2,
    "diagnosticos_por_acao": {"avancar": 3},
}


async def test_missing_api_key_returns_none_and_never_touches_groq(monkeypatch):
    monkeypatch.setattr(resumo_ia.settings, "groq_api_key", "")

    with patch("app.services.resumo_ia.AsyncGroq") as mock_groq_cls:
        resultado = await resumo_ia.gerar_resumo_executivo(CONTEXTO)

    mock_groq_cls.assert_not_called()
    assert resultado is None


def test_fallback_template_uses_the_computed_metrics():
    """O template determinístico é o que garante que `resumo_executivo`
    nunca fica vazio quando o Groq não está configurado."""
    resumo = resumo_ia.gerar_resumo_fallback(CONTEXTO)
    assert "10 pedidos" in resumo
    assert "1 ocorrência(s)" in resumo


async def test_groq_call_is_stubbed_not_a_real_network_call(monkeypatch):
    """Mesmo com uma key presente, `AsyncGroq` é substituído por um dublê —
    nenhuma chamada HTTP real sai desta suíte."""
    monkeypatch.setattr(resumo_ia.settings, "groq_api_key", "fake-key-never-sent-to-groq")
    monkeypatch.setattr(resumo_ia, "_client", None)

    fake_message = MagicMock()
    fake_message.content = "Resumo gerado pelo dublê."
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_completion = MagicMock()
    fake_completion.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_completion)

    with patch("app.services.resumo_ia.AsyncGroq", return_value=fake_client) as mock_groq_cls:
        resultado = await resumo_ia.gerar_resumo_executivo(CONTEXTO)

    mock_groq_cls.assert_called_once()
    fake_client.chat.completions.create.assert_awaited_once()
    assert resultado == "Resumo gerado pelo dublê."
