from collections.abc import Iterable

import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.auth.exceptions import RateLimitExceeded


async def _enforce(
    redis: aioredis.Redis,
    *,
    keys: Iterable[str],
    limit: int,
    window: int,
) -> None:
    """Atomic sliding-window check over one or more counters.

    Counts are incremented via a MULTI/EXEC pipeline; the first increment in a
    window sets the TTL via ``EXPIRE ... NX`` so later increments don't slide it.
    Raises :class:`RateLimitExceeded` (with ``retry_after``) past the threshold.
    """
    for key in keys:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            pipe.ttl(key)
            count, _expire_set, ttl = await pipe.execute()

        if count > limit:
            raise RateLimitExceeded(retry_after=max(int(ttl), 1))


async def check_login_rate_limit(redis: aioredis.Redis, *, ip: str, email: str) -> None:
    """Enforce the login rate limit for the given IP and email."""
    await _enforce(
        redis,
        keys=(f"login:ip:{ip}", f"login:email:{email.lower()}"),
        limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


async def check_password_reset_rate_limit(redis: aioredis.Redis, *, ip: str, email: str) -> None:
    """Enforce the password-reset request rate limit for the given IP and email."""
    await _enforce(
        redis,
        keys=(f"pwreset:req:ip:{ip}", f"pwreset:req:email:{email.lower()}"),
        limit=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS,
        window=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS,
    )
