import httpx
import pytest
from loguru import logger

from app.services.email import EmailNaoEnviadoError, enviar_email


async def test_the_console_backend_never_logs_the_body(monkeypatch):
    """O corpo carrega a senha do carregamento. Regra 5 do CLAUDE.md.

    `caplog` do pytest captura o `logging` da stdlib — este projeto loga com
    `loguru`, que não propaga para lá por padrão. Um teste com `caplog`
    passaria vazio (`registrado == ""`), vacuamente, sem provar nada sobre o
    que o backend `console` realmente loga. Em vez disso, um sink `loguru`
    próprio captura as mensagens de verdade.
    """
    monkeypatch.setattr("app.services.email.settings.email_backend", "console")

    registros: list[str] = []
    handler_id = logger.add(registros.append, level="INFO")
    try:
        await enviar_email(
            para="operacao@expresso.example",
            assunto="Carregamento #12",
            texto="Código ABCD2345, senha SEGREDO123",
        )
    finally:
        logger.remove(handler_id)

    registrado = "\n".join(registros)
    assert "operacao@expresso.example" in registrado
    assert "SEGREDO123" not in registrado


async def test_the_resend_backend_posts_to_the_api(monkeypatch):
    chamadas = []

    async def _fake_post(self, url, **kwargs):
        chamadas.append((url, kwargs))
        return httpx.Response(200, json={"id": "re_1"})

    monkeypatch.setattr("app.services.email.settings.email_backend", "resend")
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "re_test")
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    await enviar_email(para="a@b.example", assunto="Assunto", texto="Corpo")

    url, kwargs = chamadas[0]
    assert url == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_test"
    assert kwargs["json"]["from"] == "no-reply@svemlab.com"


async def test_the_resend_backend_refuses_to_run_without_a_key(monkeypatch):
    monkeypatch.setattr("app.services.email.settings.email_backend", "resend")
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "")

    with pytest.raises(EmailNaoEnviadoError):
        await enviar_email(para="a@b.example", assunto="x", texto="y")


async def test_the_resend_backend_never_logs_the_provider_response_body(monkeypatch):
    """Regra desta task: o provedor pode ecoar o payload de volta no corpo da
    resposta de erro, e o payload tem a senha. Só o status code pode ir pro
    log."""

    async def _fake_post(self, url, **kwargs):
        return httpx.Response(422, json={"message": "senha SEGREDO123 apareceu aqui"})

    monkeypatch.setattr("app.services.email.settings.email_backend", "resend")
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "re_test")
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    registros: list[str] = []
    handler_id = logger.add(registros.append, level="INFO")
    try:
        with pytest.raises(EmailNaoEnviadoError) as excinfo:
            await enviar_email(para="a@b.example", assunto="x", texto="senha SEGREDO123")
    finally:
        logger.remove(handler_id)

    registrado = "\n".join(registros)
    assert "SEGREDO123" not in registrado
    assert "SEGREDO123" not in str(excinfo.value)
    assert "422" in str(excinfo.value)


async def test_an_unknown_backend_raises(monkeypatch):
    monkeypatch.setattr("app.services.email.settings.email_backend", "carrier-pigeon")

    with pytest.raises(EmailNaoEnviadoError):
        await enviar_email(para="a@b.example", assunto="x", texto="y")
