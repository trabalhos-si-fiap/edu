import aioboto3
from botocore.config import Config

from app.core.config import settings


class ObjectStorage:
    """Thin async S3-compatible client (R2 in prod, MinIO in dev).

    Only the endpoint/credentials differ between environments, so callers stay
    storage-agnostic. The bucket is private; reads happen through presigned GETs.
    """

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._bucket = settings.R2_BUCKET
        self._config = Config(signature_version="s3v4", s3={"addressing_style": "path"})

    def _client(self, *, public: bool = False):
        endpoint = settings.R2_PUBLIC_ENDPOINT_URL if public else settings.R2_ENDPOINT_URL
        return self._session.client(
            "s3",
            endpoint_url=endpoint or settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name=settings.R2_REGION,
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
        # Sign with the public endpoint so the URL host is reachable by the app
        # (e.g. the emulator), not the internal docker hostname.
        async with self._client(public=True) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )


_storage = ObjectStorage()


def get_storage() -> ObjectStorage:
    return _storage
