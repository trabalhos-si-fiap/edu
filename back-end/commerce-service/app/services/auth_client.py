"""Cliente HTTP para o auth-users-service.

Espelha `chatbot-service/app/services/diagnostico_client.py`: repassa o
MESMO bearer do aluno, em vez de o commerce ter credencial própria. Assim a
autorização continua sendo do serviço de destino, e o commerce não vira um
principal com poderes que o aluno não tem.

O `raw_token` NUNCA vai para log nem para corpo de erro — ele é a credencial
viva de quem chamou.
"""

import uuid

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
        #
        # `from None` de propósito. Medido contra httpx==0.28.1 (instalado
        # aqui): NEM `repr(exc)` NEM `repr(exc.request)` mostram o header —
        # `repr(exc)` é só a mensagem (`HTTPStatusError` não sobrescreve
        # `__repr__`, herda o de `Exception`, que só imprime os args
        # passados a `super().__init__(message)`); `Request.__repr__`
        # (`httpx/_models.py`) é hardcoded para `<Request(method, url)>`,
        # nunca headers. Mesmo assim, `exc.request` continua sendo o objeto
        # `Request` de verdade (`exc.request is request` → `True`), e
        # `exc.request.headers["authorization"]` devolve o token em texto
        # claro — é só `repr()`/`str()` que não olham para lá. `from exc`
        # prenderia esse objeto a `__cause__`, alcançável por qualquer coisa
        # que percorra a cadeia de exceções além de repr/str (ex.: um error
        # tracker que serializa atributos/variáveis de frame) — superfície
        # que não precisa existir.
        logger.warning("auth_client: /auth/me respondeu {}", exc.response.status_code)
        raise AuthServiceUnavailableError("auth-users-service indisponível") from None
    except httpx.HTTPError:
        logger.warning("auth_client: /auth/me inalcançável em {}", url)
        raise AuthServiceUnavailableError("auth-users-service indisponível") from None


async def get_address(raw_token: str, address_id: uuid.UUID) -> dict | None:
    """`GET /auth/addresses/{id}` — devolve o endereço, ou `None` se ele não
    existe / não é do aluno.

    A distinção importa: o checkout traduz `None` em 400 "Invalid delivery
    address" (é assim que o legacy trata id obsoleto, não 404) e
    `AuthServiceUnavailableError` em 503. Um único tipo de erro obrigaria o
    chamador a inspecionar mensagem para decidir o status.

    A URL do log **não** inclui o `address_id` porque ele é um identificador
    do aluno — a mensagem genérica basta para diagnosticar. `from None` pelo
    mesmo motivo medido no `except httpx.HTTPStatusError` de `get_me` acima
    (não repetido aqui para não envelhecer em duas cópias).
    """
    url = f"{settings.auth_service_url}/auth/addresses/{address_id}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {raw_token}"})
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("auth_client: /auth/addresses respondeu {}", exc.response.status_code)
        raise AuthServiceUnavailableError("auth-users-service indisponível") from None
    except httpx.HTTPError:
        logger.warning("auth_client: /auth/addresses inalcançável")
        raise AuthServiceUnavailableError("auth-users-service indisponível") from None
