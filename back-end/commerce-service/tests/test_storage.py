import uuid

from app.storage import ObjectStorage


async def test_generate_presigned_get_returns_a_signed_url() -> None:
    """`generate_presigned_get` assina localmente (SigV4), sem round-trip de
    rede — não depende do objeto existir no bucket nem de um servidor S3
    alcançável (medido no relatório da B2). O teste legacy portado combinava
    put_object + generate_presigned_get + delete_object num único caso;
    put_object/delete_object são carve-out fase 3 (upload — ver brief), então
    este teste isola só a leitura que esta task porta."""
    storage = ObjectStorage()
    key = f"products/{uuid.uuid4()}.txt"

    url = await storage.generate_presigned_get(key, expires_in=60)

    assert key in url
    assert "X-Amz-Signature" in url or "X-Amz-Credential" in url
