import pytest
import redis.asyncio as aioredis

from app.core.media import ImageValidationError, presigned_image_url, validate_image_bytes
from app.core.storage import ObjectStorage

# Magic-byte headers.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def test_validate_accepts_png() -> None:
    ext, content_type = validate_image_bytes(PNG, declared_type="image/png")
    assert ext == "png"
    assert content_type == "image/png"


def test_validate_rejects_disallowed_type() -> None:
    with pytest.raises(ImageValidationError):
        validate_image_bytes(PNG, declared_type="image/gif")


def test_validate_rejects_content_not_matching_magic_bytes() -> None:
    with pytest.raises(ImageValidationError):
        validate_image_bytes(b"not an image", declared_type="image/png")


def test_validate_accepts_real_webp() -> None:
    webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16
    ext, content_type = validate_image_bytes(webp, declared_type="image/webp")
    assert ext == "webp"
    assert content_type == "image/webp"


def test_validate_rejects_riff_that_is_not_webp() -> None:
    # A RIFF container that is NOT WebP (e.g. a WAV) declared as webp must be rejected.
    not_webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 16
    with pytest.raises(ImageValidationError):
        validate_image_bytes(not_webp, declared_type="image/webp")


async def test_presigned_image_url_empty_key_returns_empty(
    redis_client: aioredis.Redis,
) -> None:
    url = await presigned_image_url("", storage=ObjectStorage(), redis=redis_client)
    assert url == ""


async def test_presigned_image_url_is_cached(redis_client: aioredis.Redis) -> None:
    storage = ObjectStorage()
    key = "products/cache-me.png"
    first = await presigned_image_url(key, storage=storage, redis=redis_client)
    cached = await redis_client.get(f"presign:{key}")
    assert cached == first
    second = await presigned_image_url(key, storage=storage, redis=redis_client)
    assert second == first
