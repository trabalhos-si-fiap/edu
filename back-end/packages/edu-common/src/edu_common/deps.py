"""Dependências FastAPI de autenticação, parametrizadas pelo segredo do serviço.

Cada serviço chama `build_auth_deps(settings.jwt_secret)` uma vez e usa o
resultado nos seus routers — assim a validação de JWT vive num lugar só, mas
nenhum serviço precisa importar a config de outro.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from edu_common.security import DEFAULT_ALGORITHM, decode_token

# `auto_error=False`: nas versões atuais do FastAPI, `HTTPBearer()` com
# `auto_error=True` responde 401 quando o header `Authorization` está
# ausente — não 403. Fazemos a checagem manualmente logo abaixo para manter
# a distinção esperada por quem consome este pacote: 403 "não autenticado"
# (sem credencial nenhuma) vs. 401 "credencial inválida" (token presente mas
# rejeitado por decode_token). Não depender do default da lib evita que uma
# atualização do FastAPI mude esse contrato de novo, silenciosamente.
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthDeps:
    get_current_user: Callable
    get_current_user_id: Callable
    require_role: Callable


def build_auth_deps(secret: str, algorithm: str = DEFAULT_ALGORITHM) -> AuthDeps:
    # `Depends(...)` as a default value is FastAPI's own dependency-injection
    # idiom, not the mutable-default footgun B008 guards against — FastAPI
    # resolves it once per request, not once at def time. Suppressed below
    # wherever it appears.
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
    ) -> dict:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Não autenticado",
            )
        # `expected_type="access"` faz o próprio decode_token recusar um refresh
        # token — a checagem não fica espalhada por serviço.
        payload = decode_token(credentials.credentials, secret, algorithm, expected_type="access")
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
            )
        # O token bruto acompanha o payload porque chamadas serviço-a-serviço
        # (chatbot -> learning) repassam o MESMO token do aluno.
        return {**payload, "raw_token": credentials.credentials}

    async def get_current_user_id(user: dict = Depends(get_current_user)) -> str:  # noqa: B008
        return user["sub"]

    def require_role(*allowed_roles: str) -> Callable:
        async def verifier(user: dict = Depends(get_current_user)) -> dict:  # noqa: B008
            if user.get("role") not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Sem permissão para esta ação",
                )
            return user

        return verifier

    return AuthDeps(
        get_current_user=get_current_user,
        get_current_user_id=get_current_user_id,
        require_role=require_role,
    )
