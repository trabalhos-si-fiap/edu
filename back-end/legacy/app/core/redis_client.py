import redis.asyncio as redis

from app.core.config import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return a module-level async Redis client backed by a single connection pool."""
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def get_redis() -> redis.Redis:
    """FastAPI dependency that yields the async Redis client."""
    return get_redis_client()
