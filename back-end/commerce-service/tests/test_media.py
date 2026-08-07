import pytest
import redis.asyncio as aioredis

from app.config import settings
from app.services.media import _public_endpoint, presigned_image_url
from app.storage import ObjectStorage


async def test_presigned_image_url_empty_key_returns_empty(
    redis_client: aioredis.Redis,
) -> None:
    url = await presigned_image_url("", storage=ObjectStorage(), redis=redis_client)
    assert url == ""


async def test_presigned_image_url_is_cached(redis_client: aioredis.Redis) -> None:
    storage = ObjectStorage()
    key = "products/cache-me.png"
    first = await presigned_image_url(key, storage=storage, redis=redis_client)
    cached = await redis_client.get(f"presign:{_public_endpoint()}:{key}")
    assert cached == first
    second = await presigned_image_url(key, storage=storage, redis=redis_client)
    assert second == first


async def test_presign_cache_is_scoped_to_endpoint(
    redis_client: aioredis.Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Trocar o endpoint público (ex: novo IP LAN do host) tem que usar uma
    # chave de cache nova, para que uma URL velha assinada para o host antigo
    # nunca seja reaproveitada.
    storage = ObjectStorage()
    key = "products/scoped.png"

    monkeypatch.setattr(settings, "r2_public_endpoint_url", "http://10.0.2.2:9000")
    first = await presigned_image_url(key, storage=storage, redis=redis_client)
    first_cache_key = f"presign:{_public_endpoint()}:{key}"

    monkeypatch.setattr(settings, "r2_public_endpoint_url", "http://192.168.1.50:9000")
    second_cache_key = f"presign:{_public_endpoint()}:{key}"
    second = await presigned_image_url(key, storage=storage, redis=redis_client)

    assert first_cache_key != second_cache_key
    assert await redis_client.get(first_cache_key) == first
    assert await redis_client.get(second_cache_key) == second
    assert first != second


async def test_the_same_key_returns_the_same_url_within_the_window(redis_client, monkeypatch):
    """Sem a memoização o app rebaixa o próprio cache de imagem a cada listagem."""
    assinaturas = 0

    class _StorageQueContaAssinaturas:
        async def generate_presigned_get(self, key, *, expires_in):
            nonlocal assinaturas
            assinaturas += 1
            return f"http://minio/{key}?sig={assinaturas}"

    storage = _StorageQueContaAssinaturas()
    primeira = await presigned_image_url("products/x.jpg", storage=storage, redis=redis_client)
    segunda = await presigned_image_url("products/x.jpg", storage=storage, redis=redis_client)

    assert primeira == segunda
    assert assinaturas == 1
