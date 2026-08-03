"""Hash de senha e JWT compartilhados entre os serviços.

Implementação herdada do monolito (tempo constante, `jti`, timezone-aware),
com o contrato de claims dos microserviços (inclui `role`, usado para
autorização em cada serviço).
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt
from jose.exceptions import JOSEError

DEFAULT_ALGORITHM = "HS256"
DEFAULT_BCRYPT_ROUNDS = 12
MAX_PASSWORD_BYTES = 72  # limite rígido do bcrypt; exposto para validação antes da chamada


def hash_password(plain: str, rounds: int = DEFAULT_BCRYPT_ROUNDS) -> str:
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password is {len(encoded)} bytes, exceeds bcrypt's {MAX_PASSWORD_BYTES}-byte limit"
        )
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(encoded, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compara em tempo constante — `bcrypt.checkpw` já garante isso.

    Uma senha maior que `MAX_PASSWORD_BYTES` nunca pode corresponder a um hash
    armazenado (nenhum hash válido teria sido gerado a partir dela), então
    isso conta como divergência (`False`) — assimetria intencional em relação
    a `hash_password`, que rejeita essa mesma entrada com `ValueError`. Não é
    um bug: aqui não há nada para rejeitar, só uma comparação que não bate.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Hash malformado ou senha longa demais conta como divergência, não como erro.
        return False


# Hash de uma senha aleatória e não reutilizável (nunca fica hardcoded no
# código-fonte — se estivesse, seria um caminho de "plaintext conhecido" para
# qualquer chamador que confiasse no retorno de verify_password), gerado uma
# vez no import, com o mesmo custo padrão de hash_password. O login verifica
# contra ele quando o e-mail não existe, para que o tempo de resposta de um
# e-mail inexistente iguale o de uma senha errada (anti-enumeração).
#
# Atenção: essa defesa depende de DUMMY_PASSWORD_HASH ter o mesmo custo bcrypt
# do hash real comparado no fluxo de login. Chamar hash_password(..., rounds=
# <não padrão>) em qualquer lugar do sistema reabre o vazamento de tempo que
# essa constante existe para fechar.
DUMMY_PASSWORD_HASH: str = hash_password(secrets.token_urlsafe(32))


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(payload: dict, secret: str, algorithm: str) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def _base_claims(sub: str, role: str, token_type: str, expires_at: datetime) -> dict:
    now = _now()
    return {
        "sub": sub,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }


def create_access_token(
    sub: str,
    role: str,
    secret: str,
    algorithm: str = DEFAULT_ALGORITHM,
    expires_minutes: int = 60,
) -> str:
    expires_at = _now() + timedelta(minutes=expires_minutes)
    return _encode(_base_claims(sub, role, "access", expires_at), secret, algorithm)


def create_refresh_token(
    sub: str,
    role: str,
    secret: str,
    algorithm: str = DEFAULT_ALGORITHM,
    expires_days: int = 7,
) -> str:
    expires_at = _now() + timedelta(days=expires_days)
    return _encode(_base_claims(sub, role, "refresh", expires_at), secret, algorithm)


def decode_token(
    token: str,
    secret: str,
    algorithm: str = DEFAULT_ALGORITHM,
    expected_type: str | None = None,
) -> dict | None:
    """Devolve o payload, ou None se o token for inválido, expirado, adulterado,
    de tipo inesperado (quando `expected_type` é informado), ou se `secret`
    estiver mal configurado.

    Captura `JOSEError`, não apenas `JWTError`: uma chave mal configurada
    (`None`, formato PEM/assimétrico, etc.) levanta `JWKError`, que é irmã de
    `JWTError` sob `JOSEError` — não subclasse dela. Sem isso, um segredo
    ausente ou malformado vira exceção não tratada (500) em vez de uma falha
    de autenticação, que é o comportamento esperado por quem chama.

    `expected_type` deixa a checagem de tipo (`access` vs `refresh`) dentro do
    pacote, em vez de distribuir a obrigação de lembrar `payload["type"] ==
    "access"` para cada um dos serviços — um esquecimento transformaria um
    refresh token de 7 dias em credencial de acesso.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except JOSEError:
        return None
    if expected_type is not None and payload.get("type") != expected_type:
        return None
    return payload
