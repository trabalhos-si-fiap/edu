"""Cliente HTTP para o auth-users-service.

Espelha `chatbot-service/app/services/diagnostico_client.py`: repassa o
MESMO bearer do aluno, em vez de o commerce ter credencial própria. Assim a
autorização continua sendo do serviço de destino, e o commerce não vira um
principal com poderes que o aluno não tem.

O `raw_token` NUNCA vai para log nem para corpo de erro — ele é a credencial
viva de quem chamou.
"""

import httpx
from loguru import logger

from app.config import settings

_TIMEOUT_SECONDS = 10.0


class AuthServiceUnavailableError(Exception):
    """auth-users-service inalcançável ou respondendo 5xx. Vira 503.

    Nome com sufixo `Error` (não `AuthServiceUnavailable`, como o rascunho
    do brief tinha) pelo mesmo motivo de `ProductNotFoundError`: `ruff`
    regra N818 barra exceção sem sufixo `Error`, medido com
    `uv run ruff check .` contra o nome do rascunho.
    """


async def get_me(raw_token: str) -> dict:
    """`GET /auth/me` — devolve `{id, name, email, role}`.

    O JWT carrega `sub`, `role`, `type`, `iat`, `exp`, `jti` e nada mais.
    `name` não está lá de propósito: pôr o nome no token o colocaria em todo
    header `Authorization`, que vai para log de acesso.
    """
    url = f"{settings.auth_service_url}/auth/me"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {raw_token}"})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        # Nem a exceção nem o log carregam o token — só a URL e o status.
        # `from None` de propósito: `from exc` anexaria a exceção original ao
        # traceback, e o `repr` de um `httpx.HTTPStatusError` inclui a
        # requisição — com o header `Authorization`. Isso vazaria o token
        # para o log de erro do FastAPI.
        logger.warning("auth_client: /auth/me respondeu {}", exc.response.status_code)
        raise AuthServiceUnavailableError("auth-users-service indisponível") from None
    except httpx.HTTPError:
        logger.warning("auth_client: /auth/me inalcançável em {}", url)
        raise AuthServiceUnavailableError("auth-users-service indisponível") from None
