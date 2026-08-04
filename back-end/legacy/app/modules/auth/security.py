import hmac
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt using the configured cost factor."""
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash in constant time.

    ``bcrypt.checkpw`` performs the comparison in constant time internally,
    preventing timing side-channels on the hash comparison itself.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash — treat as a mismatch rather than raising.
        return False


# Hash of a random password generated once at import time. Used by the login
# flow to keep timing constant when the supplied email does not exist — a real
# verify_password call against this hash matches the cost of a real miss and
# prevents user enumeration via response-time analysis.
DUMMY_PASSWORD_HASH: str = hash_password("dummy-password-for-timing-defense")


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(payload: dict[str, object]) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    user_id: uuid.UUID | str,
    expires_at: datetime | None = None,
) -> str:
    now = _now()
    exp = expires_at or (now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, object] = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return _encode(payload)


def create_refresh_token(
    user_id: uuid.UUID | str,
    expires_at: datetime | None = None,
) -> str:
    now = _now()
    exp = expires_at or (now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    payload: dict[str, object] = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return _encode(payload)


def decode_token(token: str) -> dict[str, object]:
    """Decode and verify a JWT. Raises ``jose.JWTError`` on any failure.

    Signature verification inside python-jose uses HMAC with constant-time
    comparison, so this call does not leak timing information.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def compare_secret(a: str | None, b: str | None) -> bool:
    """Constant-time equality check for secrets (tokens, API keys, HMAC digests).

    Returns False if either side is None or the lengths differ — without
    leaking which condition failed.
    """
    if a is None or b is None:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
