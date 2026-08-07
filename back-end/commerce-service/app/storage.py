import aioboto3
from botocore.config import Config

from app.config import settings


class ObjectStorage:
    """Cliente S3-compatível assíncrono (MinIO em dev, R2 em prod).

    Porte de `legacy/app/core/storage.py`. O bucket é privado; a leitura
    acontece por GET presignado, nunca por URL pública.

    O `put_object`/`delete_object` existem porque o seed do catálogo (B10)
    os usa. O endpoint de upload de imagem é fase 3.
    """

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._bucket = settings.r2_bucket
        self._config = Config(signature_version="s3v4", s3={"addressing_style": "path"})

    def _client(self, *, public: bool = False):
        endpoint = settings.r2_public_endpoint_url if public else settings.r2_endpoint_url
        return self._session.client(
            "s3",
            endpoint_url=endpoint or settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region,
            config=self._config,
        )

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
            )

    async def delete_object(self, key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def generate_presigned_get(self, key: str, *, expires_in: int) -> str:
        # Assina contra o endpoint público para que o host da URL seja
        # alcançável pelo app (emulador, aparelho na LAN), e não o hostname
        # interno do docker.
        async with self._client(public=True) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )


_storage = ObjectStorage()


def get_storage() -> ObjectStorage:
    return _storage
