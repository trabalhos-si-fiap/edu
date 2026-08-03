import hmac
import secrets
import uuid
from hashlib import sha256

import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.auth.security import compare_secret


def _code_key(user_id: uuid.UUID) -> str:
    return f"pwreset:code:{user_id}"


def _attempts_key(user_id: uuid.UUID) -> str:
    return f"pwreset:attempts:{user_id}"


def generate_otp() -> str:
    """Cryptographically-random 6-digit code, zero-padded (uniform 000000-999999)."""
    return f"{secrets.randbelow(10**6):06d}"


def hash_otp(code: str) -> str:
    """HMAC-SHA256 of the code under SECRET_KEY. The plaintext OTP is never stored."""
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), code.encode("utf-8"), sha256).hexdigest()


async def store_reset_code(redis: aioredis.Redis, user_id: uuid.UUID, code: str) -> None:
    """Store the hashed OTP with TTL and reset the attempt counter. One active code per user."""
    await redis.set(_code_key(user_id), hash_otp(code), ex=settings.PASSWORD_RESET_CODE_TTL_SECONDS)
    await redis.delete(_attempts_key(user_id))


async def _register_attempt(redis: aioredis.Redis, user_id: uuid.UUID) -> None:
    key = _attempts_key(user_id)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, settings.PASSWORD_RESET_CODE_TTL_SECONDS, nx=True)
        await pipe.execute()


async def verify_reset_code(redis: aioredis.Redis, user_id: uuid.UUID, code: str) -> bool:
    """Constant-time check of the OTP. Counts failed attempts and locks out after the cap.

    Does NOT consume the code on success — the caller clears it after the password
    is updated, so a failed downstream step doesn't burn the user's only code.
    """
    attempts = await redis.get(_attempts_key(user_id))
    if attempts is not None and int(attempts) >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
        return False

    stored = await redis.get(_code_key(user_id))
    if stored is None:
        await _register_attempt(redis, user_id)
        return False

    if not compare_secret(stored, hash_otp(code)):
        await _register_attempt(redis, user_id)
        return False

    return True


async def clear_reset_code(redis: aioredis.Redis, user_id: uuid.UUID) -> None:
    await redis.delete(_code_key(user_id), _attempts_key(user_id))
