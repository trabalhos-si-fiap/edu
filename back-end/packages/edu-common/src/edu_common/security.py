"""Hash de senha e JWT compartilhados entre os serviços.

Implementação herdada do monolito (tempo constante, `jti`, timezone-aware),
com o contrato de claims dos microserviços (inclui `role`, usado para
autorização em cada serviço).
"""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

DEFAULT_ALGORITHM = "HS256"


def hash_password(plain: str, rounds: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compara em tempo constante — `bcrypt.checkpw` já garante isso."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Hash malformado conta como divergência, não como erro.
        return False


# Hash de uma senha aleatória, gerado uma vez no import. O login verifica
# contra ele quando o e-mail não existe, para que o tempo de resposta de um
# e-mail inexistente iguale o de uma senha errada (anti-enumeração).
DUMMY_PASSWORD_HASH: str = hash_password("dummy-password-for-timing-defense")


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


def decode_token(token: str, secret: str, algorithm: str = DEFAULT_ALGORITHM) -> dict | None:
    """Devolve o payload, ou None se o token for inválido, expirado ou adulterado."""
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError:
        return None
