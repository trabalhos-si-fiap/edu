"""Envio de e-mail — duas implementações atrás de uma função.

`console` escreve no log que um e-mail SERIA enviado, com destinatário e
assunto e **sem o corpo**; `resend` faz um POST na API do Resend. O corpo fica
de fora do log nos dois porque ele carrega a senha do carregamento (regra 5 do
CLAUDE.md).

Trocar de provedor é acrescentar um ramo aqui. Nenhum chamador conhece o
Resend.
"""

import httpx
from loguru import logger

from app.config import settings

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SEGUNDOS = 10.0


class EmailNaoEnviadoError(Exception):
    """O envio não aconteceu: backend desconhecido, chave ausente, ou o
    provedor recusou. Quem chama decide o que fazer — no consumer, deixar a
    exceção subir manda a mensagem para a dead-letter exchange, que é onde ela
    deve ficar até alguém drenar.

    Sufixo `Error` por N818.
    """


async def enviar_email(*, para: str, assunto: str, texto: str) -> None:
    if settings.email_backend == "console":
        logger.info("email[console]: para={} assunto={}", para, assunto)
        return

    if settings.email_backend != "resend":
        raise EmailNaoEnviadoError(f"backend de e-mail desconhecido: {settings.email_backend}")

    if not settings.resend_api_key:
        raise EmailNaoEnviadoError("RESEND_API_KEY não configurada")

    async with httpx.AsyncClient(timeout=_TIMEOUT_SEGUNDOS) as client:
        resposta = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": [para],
                "subject": assunto,
                "text": texto,
            },
        )
    if resposta.status_code >= 400:
        # Sem o corpo da resposta no log nem na mensagem da exceção: o
        # provedor pode ecoar o payload de volta, e o payload tem a senha. Só
        # o status code é seguro.
        raise EmailNaoEnviadoError(f"provedor recusou o envio ({resposta.status_code})")
    logger.info("email[resend]: enviado para={} assunto={}", para, assunto)
