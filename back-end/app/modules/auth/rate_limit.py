import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.auth.exceptions import RateLimitExceeded


async def check_login_rate_limit(
    redis: aioredis.Redis,
    *,
    ip: str,
    email: str,
) -> None:
    """Enforce the login rate limit for the given IP and email.

    Counts are incremented atomically via a MULTI/EXEC pipeline. The first
    increment in a window also sets the TTL via ``EXPIRE ... NX`` so that
    subsequent increments within the window do not slide the expiration.
    Raises :class:`RateLimitExceeded` (carrying ``retry_after`` seconds) when
    either the IP or email counter crosses the configured threshold.
    """
    limit = settings.LOGIN_RATE_LIMIT_ATTEMPTS
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS

    for key in (f"login:ip:{ip}", f"login:email:{email.lower()}"):
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            pipe.ttl(key)
            count, _expire_set, ttl = await pipe.execute()

        if count > limit:
            raise RateLimitExceeded(retry_after=max(int(ttl), 1))
