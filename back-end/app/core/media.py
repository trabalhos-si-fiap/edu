import uuid

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.storage import ObjectStorage

# Allowed image types -> canonical extension and the magic-byte prefix that must
# match the actual file content (never trust the client-declared content type).
_ALLOWED: dict[str, tuple[str, bytes]] = {
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/webp": ("webp", b"RIFF"),
}


class ImageValidationError(Exception):
    """Uploaded file is not an accepted image."""


def validate_image_bytes(content: bytes, *, declared_type: str) -> tuple[str, str]:
    """Return (extension, content_type) or raise ImageValidationError."""
    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared not in _ALLOWED:
        raise ImageValidationError(f"Unsupported image type: {declared!r}")
    ext, magic = _ALLOWED[declared]
    if not content.startswith(magic):
        raise ImageValidationError("File content does not match an image of the declared type")
    return ext, declared


def new_image_key(ext: str) -> str:
    return f"products/{uuid.uuid4()}.{ext}"


async def presigned_image_url(
    key: str,
    *,
    storage: ObjectStorage,
    redis: aioredis.Redis,
) -> str:
    """Turn an object key into a presigned GET URL, memoized in Redis so the
    same key returns a stable URL within the cache window (keeps client-side
    image caching effective and avoids re-signing on every list request)."""
    if not key:
        return ""
    cache_key = f"presign:{key}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return cached
    url = await storage.generate_presigned_get(key, expires_in=settings.MEDIA_PRESIGN_TTL_SECONDS)
    await redis.set(cache_key, url, ex=settings.MEDIA_PRESIGN_CACHE_TTL_SECONDS)
    return url
