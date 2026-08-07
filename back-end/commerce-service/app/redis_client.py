import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Cliente Redis assíncrono de módulo, sobre um pool único.

    `decode_responses=True` porque o único uso hoje guarda URL presignada
    como string — `presigned_image_url` devolve o valor do cache direto.
    """
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def get_redis() -> redis.Redis:
    """Dependência FastAPI que entrega o cliente Redis."""
    return get_redis_client()
