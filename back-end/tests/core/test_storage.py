import uuid

from app.core.storage import ObjectStorage


async def test_put_get_delete_roundtrip() -> None:
    storage = ObjectStorage()
    key = f"products/{uuid.uuid4()}.txt"

    await storage.put_object(key, b"hello", "text/plain")
    url = await storage.generate_presigned_get(key, expires_in=60)
    assert key in url
    assert "X-Amz-Signature" in url or "X-Amz-Credential" in url

    await storage.delete_object(key)  # must not raise
