# Marketplace Product Photos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins upload product photos (stored in Cloudflare R2 / MinIO in dev) and have the Flutter marketplace display the real images by consuming the products API.

**Architecture:** The DB column `products_products.image_url` is repurposed to store an **object key** (e.g. `products/<uuid>.jpg`). A shared media helper turns a key into a short-lived **presigned GET URL** (memoized in Redis) at every serialization boundary that emits an image to the client (products, orders, cart). An admin-only `POST /api/products/{id}/image` validates and uploads the file. The Flutter app stops using mocks and fetches products + reviews from the API; product `id` migrates from `int` to `String` (UUID), and a `ProductImage` widget renders the network image with an icon fallback.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x / Alembic / `aioboto3` / Redis / MinIO (dev) + R2 (prod); Flutter / Dart / `http` / `cached_network_image`; pytest + `httpx.AsyncClient`; `flutter test`.

**Spec:** `docs/superpowers/specs/2026-06-13-marketplace-product-photos-design.md`

**Plan refinement vs spec:** The spec proposed renaming the column `image_url` → `image_key`. During planning we found `image_url` is read/snapshotted across 4 backend modules (products, orders, cart, bff). To avoid a multi-module rename, we **keep the column name `image_url`** but store the object key in it and convert to a presigned URL only at serialization. Functionally identical, far less churn.

---

## File Structure

**Backend — new files**
- `back-end/app/core/storage.py` — `ObjectStorage` (aioboto3 wrapper) + `get_storage` dependency.
- `back-end/app/core/media.py` — image validation (`read_validated_image`) + presign-with-cache (`presigned_image_url`, `presign_keys`).
- `back-end/tests/core/test_media.py` — tests for validation + presign cache.
- `back-end/tests/modules/products/test_image_upload.py` — upload endpoint tests.

**Backend — modified**
- `back-end/pyproject.toml` — add `python-multipart`, `aioboto3`.
- `back-end/app/core/config.py` — R2 settings.
- `back-end/app/modules/auth/dependencies.py` — `require_admin`.
- `back-end/app/modules/auth/models.py` — `User.is_admin`.
- `back-end/app/modules/products/models.py` — comment: `image_url` stores a key.
- `back-end/app/modules/products/services.py` — `set_product_image`.
- `back-end/app/modules/products/routes.py` — upload route + presign on serialization.
- `back-end/app/modules/orders/routes.py` + `back-end/app/modules/cart/routes.py` — presign on serialization (only where image is returned).
- `back-end/app/seeds/products.py` — seed image keys + upload sample images.
- `back-end/docker-compose.yml` — `minio` + `minio-init` services.
- Alembic: two new migrations (`is_admin`, no schema change for image — column reused).

**Frontend — new files**
- `front-end-flutter/lib/features/marketplace/data/products_api.dart` — `ProductsApi`, `ProductsException`.
- `front-end-flutter/lib/features/marketplace/presentation/widgets/product_image.dart` — `ProductImage`.
- `front-end-flutter/test/marketplace/product_model_test.dart`, `products_api_test.dart`, `front-end-flutter/test/cart/cart_store_test.dart`.

**Frontend — modified**
- `domain/product.dart` (id→String, fromJson), `cart/data/cart_store.dart` + `cart/domain/cart_item.dart` (String ids), `presentation/marketplace_screen.dart`, `presentation/product_detail_screen.dart`, `presentation/checkout_screen.dart`, `presentation/widgets/review_item.dart`, `pubspec.yaml`. Delete `data/mock_marketplace.dart`.

---

# PART A — BACKEND

> Run all backend commands from `back-end/`. Tests need Postgres + Redis + MinIO running (`docker compose up -d postgres redis minio`).

## Task A1: `User.is_admin` + migration

**Files:**
- Modify: `back-end/app/modules/auth/models.py`
- Create: `back-end/alembic/versions/<rev>_add_user_is_admin.py`
- Test: `back-end/tests/modules/auth/test_is_admin.py`

- [ ] **Step 1: Write the failing test**

Create `back-end/tests/modules/auth/test_is_admin.py`:

```python
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import services as auth_services
from app.modules.auth.schemas import RegisterIn


async def test_new_user_is_not_admin_by_default(db_session: AsyncSession) -> None:
    user = await auth_services.register(
        db_session,
        RegisterIn(
            name="Ana",
            email="ana@example.com",
            phone="11999990000",
            birth_date=date(1995, 1, 1),
            education_level="Vestibulando",
            password="Secret!1",
        ),
    )
    assert user.is_admin is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/modules/auth/test_is_admin.py -v`
Expected: FAIL — `AttributeError: 'User' object has no attribute 'is_admin'`.

- [ ] **Step 3: Add the column**

In `back-end/app/modules/auth/models.py`, add right after the `is_verified` line:

```python
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

(`Boolean` is already imported.)

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/modules/auth/test_is_admin.py -v`
Expected: PASS (the test DB is created from models via `Base.metadata.create_all`).

- [ ] **Step 5: Generate the migration**

Run: `uv run alembic revision --autogenerate -m "add user is_admin"`
Then open the generated file and confirm `op.add_column` uses a server default so existing rows are valid. Edit the `upgrade()` to:

```python
def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "is_admin")
```

- [ ] **Step 6: Apply and verify**

Run: `uv run alembic upgrade head`
Expected: completes without error.

- [ ] **Step 7: Commit**

```bash
git add app/modules/auth/models.py alembic/versions tests/modules/auth/test_is_admin.py
git commit -m "feat(auth): add is_admin flag to user"
```

## Task A2: `require_admin` dependency

**Files:**
- Modify: `back-end/app/modules/auth/dependencies.py`
- Test: `back-end/tests/modules/auth/test_require_admin.py`

- [ ] **Step 1: Write the failing test**

Create `back-end/tests/modules/auth/test_require_admin.py`:

```python
import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User


async def test_require_admin_allows_admin() -> None:
    user = User(name="Root", is_admin=True)
    assert await require_admin(user) is user


async def test_require_admin_rejects_non_admin() -> None:
    user = User(name="Student", is_admin=False)
    with pytest.raises(HTTPException) as exc:
        await require_admin(user)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/modules/auth/test_require_admin.py -v`
Expected: FAIL — `ImportError: cannot import name 'require_admin'`.

- [ ] **Step 3: Implement**

In `back-end/app/modules/auth/dependencies.py`, append:

```python
_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Admin privileges required",
)


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.is_admin:
        raise _FORBIDDEN
    return user
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/modules/auth/test_require_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/auth/dependencies.py tests/modules/auth/test_require_admin.py
git commit -m "feat(auth): add require_admin dependency"
```

## Task A3: dependencies + R2/MinIO config

**Files:**
- Modify: `back-end/pyproject.toml`, `back-end/app/core/config.py`

- [ ] **Step 1: Add dependencies**

Run:
```bash
uv add python-multipart aioboto3
```
Expected: both added to `pyproject.toml` `[project] dependencies` and `uv.lock` updated.

- [ ] **Step 2: Add settings**

In `back-end/app/core/config.py`, add inside `Settings` (after the tracking block, before `settings = Settings()`):

```python
    # Object storage for product images. Cloudflare R2 in prod, MinIO in dev —
    # both speak the S3 API, so only the endpoint/credentials change. The bucket
    # is private; clients read via short-lived presigned GET URLs.
    R2_ENDPOINT_URL: str = "http://minio:9000"
    R2_PUBLIC_ENDPOINT_URL: str | None = None  # used to build URLs reachable by the app
    R2_ACCESS_KEY_ID: str = "edu"
    R2_SECRET_ACCESS_KEY: str = "edu-secret"  # noqa: S105
    R2_REGION: str = "auto"
    R2_BUCKET: str = "edu-media"
    # Presigned URL lifetime, and how long we memoize a generated URL in Redis
    # (kept under the lifetime so a cached URL never hands out an almost-expired link).
    MEDIA_PRESIGN_TTL_SECONDS: int = 86400
    MEDIA_PRESIGN_CACHE_TTL_SECONDS: int = 82800
    # Max accepted upload size for a product image.
    MEDIA_MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
```

- [ ] **Step 3: Verify config loads**

Run: `uv run python -c "from app.core.config import settings; print(settings.R2_BUCKET, settings.MEDIA_MAX_UPLOAD_BYTES)"`
Expected: `edu-media 5242880`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock app/core/config.py
git commit -m "feat(config): add object storage settings for product media"
```

## Task A4: MinIO in docker-compose

**Files:**
- Modify: `back-end/docker-compose.yml`

- [ ] **Step 1: Add the MinIO services**

In `back-end/docker-compose.yml`, add under `services:` (mirror the indentation of existing services, and add `minio_data:` under the top-level `volumes:` block):

```yaml
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: edu
      MINIO_ROOT_PASSWORD: edu-secret
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 10

  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_started
    entrypoint: >
      /bin/sh -c "
      until mc alias set local http://minio:9000 edu edu-secret; do sleep 1; done;
      mc mb --ignore-existing local/edu-media;
      exit 0;
      "
```

- [ ] **Step 2: Start MinIO and verify the bucket exists**

Run:
```bash
docker compose up -d minio minio-init
docker compose run --rm minio-init
```
Expected: `Bucket created successfully local/edu-media` (or already exists, exit 0).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker): add minio object storage for dev"
```

## Task A5: `ObjectStorage` client

**Files:**
- Create: `back-end/app/core/storage.py`
- Test: `back-end/tests/core/test_storage.py`

- [ ] **Step 1: Write the failing test**

Create `back-end/tests/core/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.storage'`.

- [ ] **Step 3: Implement**

Create `back-end/app/core/storage.py`:

```python
from typing import Annotated

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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/core/test_storage.py -v`
Expected: PASS (requires MinIO up with bucket `edu-media`). For local runs set `R2_PUBLIC_ENDPOINT_URL=http://localhost:9000` in `back-end/.env`.

- [ ] **Step 5: Commit**

```bash
git add app/core/storage.py tests/core/test_storage.py
git commit -m "feat(storage): add S3-compatible object storage client"
```

## Task A6: media helpers — validation + presign cache

**Files:**
- Create: `back-end/app/core/media.py`
- Test: `back-end/tests/core/test_media.py`

- [ ] **Step 1: Write the failing tests**

Create `back-end/tests/core/test_media.py`:

```python
import pytest
import redis.asyncio as aioredis

from app.core.media import ImageValidationError, presigned_image_url, validate_image_bytes
from app.core.storage import ObjectStorage

# 1x1 PNG and JPEG magic-byte headers.
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_media.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.media'`.

- [ ] **Step 3: Implement**

Create `back-end/app/core/media.py`:

```python
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
    url = await storage.generate_presigned_get(
        key, expires_in=settings.MEDIA_PRESIGN_TTL_SECONDS
    )
    await redis.set(cache_key, url, ex=settings.MEDIA_PRESIGN_CACHE_TTL_SECONDS)
    return url
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/core/test_media.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/core/media.py tests/core/test_media.py
git commit -m "feat(media): add image validation and presigned-url cache helpers"
```

## Task A7: presign `image_url` in product serialization

**Files:**
- Modify: `back-end/app/modules/products/models.py` (comment only), `back-end/app/modules/products/routes.py`
- Test: `back-end/tests/modules/products/test_routes.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `back-end/tests/modules/products/test_routes.py`:

```python
class TestImagePresign:
    async def test_image_url_is_presigned_when_key_present(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        r = await client.get("/api/products?q=Cálculo", headers=auth_headers)
        item = r.json()["items"][0]
        # The seeded "Cálculo" product stores key "https://img/calc.png" today;
        # this test asserts the response no longer echoes the raw stored value
        # but a presigned URL containing the object key + a signature.
        assert "X-Amz-Signature" in item["image_url"] or "X-Amz-Credential" in item["image_url"]

    async def test_image_url_empty_when_no_key(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        auth_headers: dict[str, str],
    ) -> None:
        r = await client.get("/api/products?q=Física", headers=auth_headers)
        assert r.json()["items"][0]["image_url"] == ""
```

> Before running: update the `seeded_products` fixture in `back-end/tests/modules/products/conftest.py` so the Cálculo product's `image_url` is a real key — change `image_url="https://img/calc.png"` to `image_url="products/calc.png"`.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/modules/products/test_routes.py::TestImagePresign -v`
Expected: FAIL — `image_url` still equals the raw stored string `products/calc.png`.

- [ ] **Step 3: Update the model comment**

In `back-end/app/modules/products/models.py`, replace the `image_url` line's intent by adding a comment above it:

```python
    # Object key (e.g. "products/<uuid>.jpg") in the media bucket — NOT a URL.
    # Serialization turns it into a short-lived presigned GET URL.
    image_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
```

- [ ] **Step 4: Presign during serialization**

In `back-end/app/modules/products/routes.py`:

Add imports at the top:

```python
from app.core.media import presigned_image_url
from app.core.redis_client import get_redis
from app.core.storage import ObjectStorage, get_storage
```

Add a redis import type (`import redis.asyncio as aioredis`) and a helper after `_NOT_FOUND`:

```python
async def _product_out(
    product: Product, *, storage: ObjectStorage, redis: "aioredis.Redis"
) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.image_url = await presigned_image_url(product.image_url, storage=storage, redis=redis)
    return out
```

(Add `from app.modules.products.models import Product` to the imports.)

In `list_products`, add the dependencies and use the helper:

```python
async def list_products(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated["aioredis.Redis", Depends(get_redis)],
    q: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductList:
    items, total = await services.list_products(session, q=q, limit=limit, offset=offset)
    return ProductList(
        items=[await _product_out(p, storage=storage, redis=redis) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )
```

In `get_product`, add the same `storage`/`redis` dependencies and return `await _product_out(product, storage=storage, redis=redis)`.

- [ ] **Step 5: Run it to verify it passes**

Run: `uv run pytest tests/modules/products/test_routes.py -v`
Expected: PASS (whole file — confirms existing tests still pass).

- [ ] **Step 6: Commit**

```bash
git add app/modules/products/models.py app/modules/products/routes.py \
        tests/modules/products/conftest.py tests/modules/products/test_routes.py
git commit -m "feat(products): serialize image_url as presigned url"
```

## Task A8: upload endpoint + service

**Files:**
- Modify: `back-end/app/modules/products/services.py`, `back-end/app/modules/products/routes.py`
- Test: `back-end/tests/modules/products/test_image_upload.py`

- [ ] **Step 1: Write the failing tests**

Create `back-end/tests/modules/products/test_image_upload.py`:

```python
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import create_access_token
from app.modules.products.models import Product

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict[str, str]:
    from datetime import date

    from app.modules.auth import services as auth_services
    from app.modules.auth.schemas import RegisterIn

    admin = await auth_services.register(
        db_session,
        RegisterIn(
            name="Admin",
            email="admin@example.com",
            phone="11999991111",
            birth_date=date(1990, 1, 1),
            education_level="Vestibulando",
            password="Secret!1",
        ),
    )
    admin.is_admin = True
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


class TestImageUpload:
    async def test_non_admin_is_forbidden(
        self, client: AsyncClient, seeded_products: list[Product], auth_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[0].id
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=auth_headers,
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert r.status_code == 403

    async def test_admin_uploads_and_image_url_is_presigned(
        self, client: AsyncClient, seeded_products: list[Product], admin_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[1].id  # Física — starts with empty key
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=admin_headers,
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "X-Amz-Signature" in body["image_url"] or "X-Amz-Credential" in body["image_url"]

    async def test_rejects_non_image_content_type(
        self, client: AsyncClient, seeded_products: list[Product], admin_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[1].id
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=admin_headers,
            files={"file": ("p.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400

    async def test_rejects_oversized_file(
        self, client: AsyncClient, seeded_products: list[Product], admin_headers: dict[str, str]
    ) -> None:
        pid = seeded_products[1].id
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
        r = await client.post(
            f"/api/products/{pid}/image",
            headers=admin_headers,
            files={"file": ("p.png", big, "image/png")},
        )
        assert r.status_code == 413

    async def test_unknown_product_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            f"/api/products/{uuid.uuid4()}/image",
            headers=admin_headers,
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert r.status_code == 404
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/modules/products/test_image_upload.py -v`
Expected: FAIL — route `POST /api/products/{id}/image` does not exist (404/405 for all).

- [ ] **Step 3: Add the service function**

In `back-end/app/modules/products/services.py`, append:

```python
async def set_product_image(
    session: AsyncSession, product_id: uuid.UUID, *, image_key: str
) -> Product:
    """Persist a new image object key, returning the (old_key, product). Caller
    deletes the old object after commit."""
    product = await get_product(session, product_id)
    product.image_url = image_key
    await session.commit()
    await session.refresh(product)
    logger.info("products: image set product={} key={}", product_id, image_key)
    return product
```

- [ ] **Step 4: Add the route**

In `back-end/app/modules/products/routes.py`:

Add imports:

```python
from fastapi import File, UploadFile
from loguru import logger

from app.core.config import settings
from app.core.media import ImageValidationError, new_image_key, validate_image_bytes
from app.modules.auth.dependencies import require_admin
```

Add the route (after `create_review`):

```python
@router.post("/{product_id}/image", response_model=ProductOut)
async def upload_product_image(
    product_id: uuid.UUID,
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    redis: Annotated["aioredis.Redis", Depends(get_redis)],
    file: Annotated[UploadFile, File()],
) -> ProductOut:
    # Read with a hard cap so an oversized upload can't exhaust memory
    # (security rule #4: server-side size limit, never trust Content-Length).
    content = await file.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")
    try:
        ext, content_type = validate_image_bytes(content, declared_type=file.content_type or "")
    except ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Make sure the product exists before writing to storage.
    try:
        old_key = (await services.get_product(session, product_id)).image_url
    except ProductNotFound as exc:
        raise _NOT_FOUND from exc

    key = new_image_key(ext)
    await storage.put_object(key, content, content_type)
    try:
        product = await services.set_product_image(session, product_id, image_key=key)
    except ProductNotFound as exc:
        await storage.delete_object(key)
        raise _NOT_FOUND from exc

    if old_key and old_key != key:
        try:
            await storage.delete_object(old_key)
        except Exception:  # noqa: BLE001 — best-effort cleanup, never fail the request
            logger.warning("products: failed to delete old image key={}", old_key)

    return await _product_out(product, storage=storage, redis=redis)
```

- [ ] **Step 5: Run it to verify it passes**

Run: `uv run pytest tests/modules/products/test_image_upload.py -v`
Expected: PASS (MinIO must be up).

- [ ] **Step 6: Run ruff + full products tests**

Run: `uv run ruff check app/modules/products && uv run pytest tests/modules/products -v`
Expected: clean + all pass.

- [ ] **Step 7: Commit**

```bash
git add app/modules/products/services.py app/modules/products/routes.py \
        tests/modules/products/test_image_upload.py
git commit -m "feat(products): add admin product image upload endpoint"
```

## Task A9: presign image_url in orders + cart responses

**Files:**
- Modify: `back-end/app/modules/orders/routes.py`, `back-end/app/modules/cart/routes.py`
- Test: extend the respective route tests

> Orders and cart copy `product.image_url` (now a key) into their item snapshots; their responses must presign it the same way products do, otherwise clients receive a bare key.

- [ ] **Step 1: Inspect both route files**

Run: `sed -n '1,60p' app/modules/orders/routes.py app/modules/cart/routes.py`
Identify where `*Out` schemas are built from ORM objects (look for `.model_validate(` on order items / cart items).

- [ ] **Step 2: Write a failing test (orders)**

In the orders route test file (find with `ls tests/modules/orders`), add a test that creates an order from a product whose `image_url` is a key (e.g. `"products/x.png"`) and asserts the returned item's `image_url` contains `X-Amz-Signature` or `X-Amz-Credential`. Mirror the products presign test structure from Task A7. Do the same in the cart test file.

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/modules/orders tests/modules/cart -k image -v`
Expected: FAIL — bare key returned.

- [ ] **Step 4: Apply presign at each serialization point**

In each route that returns items with images, inject `storage: Annotated[ObjectStorage, Depends(get_storage)]` and `redis: Annotated["aioredis.Redis", Depends(get_redis)]`, and after building each `*Out`, set its `image_url`:

```python
out.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
```

Reuse imports from Task A7 (`presigned_image_url`, `get_storage`, `get_redis`, `ObjectStorage`, `import redis.asyncio as aioredis`).

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/modules/orders tests/modules/cart -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/modules/orders/routes.py app/modules/cart/routes.py tests/modules/orders tests/modules/cart
git commit -m "feat(orders,cart): serialize item image_url as presigned url"
```

## Task A10: seed product images

**Files:**
- Modify: `back-end/app/seeds/products.py`
- Add: a few small sample images under `back-end/app/seeds/assets/` (jpg/png ≤ 200 KB each)

- [ ] **Step 1: Add sample assets**

Place 2–3 small royalty-free images at `back-end/app/seeds/assets/<slug>.jpg`. Name them after products in `SEED_PRODUCTS`.

- [ ] **Step 2: Upload on seed + set keys**

In `back-end/app/seeds/products.py`, where each product is created, when a matching asset exists: read its bytes, derive `key = f"products/seed-{slug}.jpg"`, `await storage.put_object(key, data, "image/jpeg")` (use `ObjectStorage` from `app.core.storage`), and set `image_url=key`. Keep the seed idempotent (skip upload if the product already exists). Products without an asset keep `image_url=""`.

- [ ] **Step 3: Run the seed and verify**

Run: `uv run python -m app.seeds.products`
Then: `uv run python -c "import asyncio; ..."` or query the DB to confirm `image_url` holds keys like `products/seed-...jpg`.
Manually: `GET /api/products` with a valid token returns presigned URLs that resolve to images in the browser.

- [ ] **Step 4: Run the seed test**

Run: `uv run pytest tests/seeds/test_products_seed.py -v`
Expected: PASS (update the test if it asserts on `image_url`).

- [ ] **Step 5: Commit**

```bash
git add app/seeds/products.py app/seeds/assets tests/seeds/test_products_seed.py
git commit -m "feat(seeds): populate product image keys with sample uploads"
```

## Task A11: backend full-suite gate

- [ ] **Step 1: Run everything**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pytest`
Expected: lint clean, format clean, all tests pass. Fix anything red before moving to Part B.

---

# PART B — FRONTEND

> Run all Flutter commands from `front-end-flutter/`.

## Task B1: add `cached_network_image`

**Files:**
- Modify: `front-end-flutter/pubspec.yaml`

- [ ] **Step 1: Add the dependency**

Run: `flutter pub add cached_network_image`
Expected: `cached_network_image` appears under `dependencies` and `flutter pub get` succeeds.

- [ ] **Step 2: Commit**

```bash
git add pubspec.yaml pubspec.lock
git commit -m "build(flutter): add cached_network_image"
```

## Task B2: `Product`/`Review` → String id + `fromJson`

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/domain/product.dart`
- Test: `front-end-flutter/test/marketplace/product_model_test.dart`

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/marketplace/product_model_test.dart`:

```dart
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Product.fromJson maps snake_case fields', () {
    final p = Product.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'name': 'Guia',
      'type': 'apostila',
      'subtype': 'Digital',
      'description': 'desc',
      'price': '49.90',
      'image_url': 'https://signed/url',
      'rating_avg': 4.5,
      'rating_count': 128,
    });
    expect(p.id, '11111111-1111-1111-1111-111111111111');
    expect(p.price, 49.90);
    expect(p.imageUrl, 'https://signed/url');
    expect(p.ratingCount, 128);
  });

  test('Review.fromJson maps fields', () {
    final r = Review.fromJson({
      'id': '22222222-2222-2222-2222-222222222222',
      'author': 'Ana',
      'rating': 5,
      'comment': 'ótimo',
      'created_at': '2025-03-12T10:00:00Z',
    });
    expect(r.id, '22222222-2222-2222-2222-222222222222');
    expect(r.rating, 5);
  });
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `flutter test test/marketplace/product_model_test.dart`
Expected: FAIL — `Product.fromJson`/`Review.fromJson` undefined; `id` is `int`.

- [ ] **Step 3: Update the models**

In `front-end-flutter/lib/features/marketplace/domain/product.dart`, change `Product.id` and `Review.id` to `String` and add factories. Product:

```dart
class Product {
  final String id;
  final String name;
  final String type;
  final String subtype;
  final String description;
  final double price;
  final String imageUrl;
  final double ratingAvg;
  final int ratingCount;

  const Product({
    required this.id,
    required this.name,
    required this.type,
    required this.subtype,
    required this.description,
    required this.price,
    this.imageUrl = '',
    this.ratingAvg = 0.0,
    this.ratingCount = 0,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      id: json['id'] as String,
      name: json['name'] as String? ?? '',
      type: json['type'] as String? ?? '',
      subtype: json['subtype'] as String? ?? '',
      description: json['description'] as String? ?? '',
      price: double.tryParse('${json['price']}') ?? 0.0,
      imageUrl: json['image_url'] as String? ?? '',
      ratingAvg: (json['rating_avg'] as num?)?.toDouble() ?? 0.0,
      ratingCount: (json['rating_count'] as num?)?.toInt() ?? 0,
    );
  }

  String get categoryLabel =>
      subtype.trim().isNotEmpty ? subtype.toUpperCase() : type.toUpperCase();
}
```

For `Review`, change `final int id;` to `final String id;` and add:

```dart
  factory Review.fromJson(Map<String, dynamic> json) {
    return Review(
      id: json['id'] as String,
      author: json['author'] as String? ?? '',
      rating: (json['rating'] as num?)?.toInt() ?? 0,
      comment: json['comment'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
    );
  }
```

- [ ] **Step 4: Run it to verify it passes**

Run: `flutter test test/marketplace/product_model_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/domain/product.dart test/marketplace/product_model_test.dart
git commit -m "feat(marketplace): add fromJson and string ids to product/review"
```

## Task B3: migrate `CartStore`/`CartItem` to String ids

**Files:**
- Modify: `front-end-flutter/lib/features/cart/data/cart_store.dart`, `front-end-flutter/lib/features/cart/domain/cart_item.dart`
- Test: `front-end-flutter/test/cart/cart_store_test.dart`

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/cart/cart_store_test.dart`:

```dart
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id) => Product(
      id: id,
      name: 'P$id',
      type: 't',
      subtype: 's',
      description: 'd',
      price: 10.0,
    );

void main() {
  test('add/decrement/removeAll work with string ids', () {
    final store = CartStore();
    store.add(_p('a'));
    store.add(_p('a'));
    store.add(_p('b'));
    expect(store.totalQuantity, 3);

    store.decrement('a');
    expect(store.totalQuantity, 2);

    store.removeAll('b');
    expect(store.items.length, 1);
    expect(store.items.first.product.id, 'a');
  });
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `flutter test test/cart/cart_store_test.dart`
Expected: FAIL — `decrement`/`removeAll`/`_indexOf` take `int`.

- [ ] **Step 3: Change the id type**

In `front-end-flutter/lib/features/cart/data/cart_store.dart`, change every `int productId` to `String productId`:

```dart
  int _indexOf(String productId) =>
      _items.indexWhere((i) => i.product.id == productId);
```
```dart
  void decrement(String productId) {
```
```dart
  void removeAll(String productId) {
```

(`add(Product product, ...)` already uses `product.id`, now a String — no signature change.) If `CartItem` stores or compares an `int` id anywhere, update it to `String` too.

- [ ] **Step 4: Run it to verify it passes**

Run: `flutter test test/cart/cart_store_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/features/cart test/cart/cart_store_test.dart
git commit -m "refactor(cart): use string product ids"
```

## Task B4: `ProductsApi`

**Files:**
- Create: `front-end-flutter/lib/features/marketplace/data/products_api.dart`
- Test: `front-end-flutter/test/marketplace/products_api_test.dart`

> Follow the existing `AddressesApi`/`NotificationsApi` pattern: `http.Client` + `TokenStore`, `Authorization: Bearer`, feature-specific exception. Confirm the `TokenStore` import path with `grep -rn "class TokenStore" lib/`.

- [ ] **Step 1: Write the failing test**

Create `front-end-flutter/test/marketplace/products_api_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/products_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore implements TokenStore {
  @override
  Future<String?> readAccessToken() async => 'tkn';
  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('list parses products envelope', () async {
    final client = MockClient((req) async {
      expect(req.headers['Authorization'], 'Bearer tkn');
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 'p1',
              'name': 'Guia',
              'type': 'apostila',
              'subtype': '',
              'description': '',
              'price': '49.90',
              'image_url': '',
              'rating_avg': 0.0,
              'rating_count': 0,
            }
          ],
          'total': 1,
          'limit': 20,
          'offset': 0,
        }),
        200,
      );
    });
    final api = ProductsApi(client: client, tokenStore: _FakeTokenStore());
    final products = await api.list();
    expect(products.length, 1);
    expect(products.first.id, 'p1');
  });

  test('list throws ProductsException on error status', () async {
    final client = MockClient((req) async => http.Response('boom', 500));
    final api = ProductsApi(client: client, tokenStore: _FakeTokenStore());
    expect(api.list(), throwsA(isA<ProductsException>()));
  });
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `flutter test test/marketplace/products_api_test.dart`
Expected: FAIL — `products_api.dart` does not exist.

- [ ] **Step 3: Implement**

Create `front-end-flutter/lib/features/marketplace/data/products_api.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/api_config.dart';
import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:http/http.dart' as http;

class ProductsException implements Exception {
  final String message;
  ProductsException(this.message);
  @override
  String toString() => message;
}

class ProductsApi {
  final http.Client _client;
  final TokenStore _tokenStore;

  ProductsApi({http.Client? client, TokenStore? tokenStore})
      : _client = client ?? http.Client(),
        _tokenStore = tokenStore ?? TokenStore();

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw ProductsException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }

  Future<List<Product>> list({String? q, int limit = 20, int offset = 0}) async {
    final headers = await _headers();
    final query = {
      'limit': '$limit',
      'offset': '$offset',
      if (q != null && q.trim().isNotEmpty) 'q': q.trim(),
    };
    final uri = Uri.parse('${ApiConfig.baseUrl}/products').replace(queryParameters: query);
    final http.Response res;
    try {
      res = await _client.get(uri, headers: headers);
    } on Exception {
      throw ProductsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ProductsException('Falha ao carregar produtos (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final items = body['items'] as List<dynamic>;
    return items.map((e) => Product.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Review>> reviews(String productId) async {
    final headers = await _headers();
    final uri = Uri.parse('${ApiConfig.baseUrl}/products/$productId/reviews');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: headers);
    } on Exception {
      throw ProductsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ProductsException('Falha ao carregar avaliações (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final items = body['items'] as List<dynamic>;
    return items.map((e) => Review.fromJson(e as Map<String, dynamic>)).toList();
  }
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `flutter test test/marketplace/products_api_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/data/products_api.dart test/marketplace/products_api_test.dart
git commit -m "feat(marketplace): add products api client"
```

## Task B5: `ProductImage` widget

**Files:**
- Create: `front-end-flutter/lib/features/marketplace/presentation/widgets/product_image.dart`

- [ ] **Step 1: Implement the widget**

Create `front-end-flutter/lib/features/marketplace/presentation/widgets/product_image.dart`:

```dart
import 'package:cached_network_image/cached_network_image.dart';
import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_visuals.dart';
import 'package:flutter/material.dart';

/// Renders a product image from a (presigned) network URL, falling back to the
/// type icon placeholder when the URL is empty or fails to load.
class ProductImage extends StatelessWidget {
  final String imageUrl;
  final String type;
  final double iconSize;

  const ProductImage({
    super.key,
    required this.imageUrl,
    required this.type,
    this.iconSize = 48,
  });

  Widget _placeholder() => Container(
        color: AppColors.imagePlaceholder,
        alignment: Alignment.center,
        child: Icon(
          iconForProduct(type),
          size: iconSize,
          color: AppColors.textSecondary.withValues(alpha: 0.6),
        ),
      );

  @override
  Widget build(BuildContext context) {
    if (imageUrl.isEmpty) return _placeholder();
    return CachedNetworkImage(
      imageUrl: imageUrl,
      fit: BoxFit.cover,
      placeholder: (_, __) => Container(
        color: AppColors.imagePlaceholder,
        alignment: Alignment.center,
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      errorWidget: (_, __, ___) => _placeholder(),
    );
  }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `flutter analyze lib/features/marketplace/presentation/widgets/product_image.dart`
Expected: No issues.

- [ ] **Step 3: Commit**

```bash
git add lib/features/marketplace/presentation/widgets/product_image.dart
git commit -m "feat(marketplace): add product image widget with icon fallback"
```

## Task B6: marketplace screen consumes the API

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/marketplace_screen.dart`

> Mirror the `AddressesScreen` async pattern: `_loading`/`_error`/`_products` state, `_load()` in `initState`, loading/error(retry)/empty states, `RefreshIndicator`. Replace the `mockProducts` references.

- [ ] **Step 1: Replace mock source with API load**

In `marketplace_screen.dart`:
- Remove `import '.../data/mock_marketplace.dart';`; add `import '.../data/products_api.dart';`.
- Convert the State to hold `final _api = ProductsApi();`, `bool _loading = true;`, `String? _error;`, `List<Product> _products = const [];`.
- Add `_load()` (set loading, `try { _products = await _api.list(); } on ProductsException catch (e) { _error = e.message; }`, guard `mounted`), call it in `initState`.
- Derive `_types` from `_products` (after load) instead of from `mockProducts`; the search filter now runs over `_products`.
- In `build`, show `CircularProgressIndicator` while `_loading`, an error widget with a retry button when `_error != null`, an empty state when no products, else the list wrapped in `RefreshIndicator(onRefresh: _load, ...)`.
- In each product card, replace the placeholder `Container(color: AppColors.imagePlaceholder, child: Center(child: Icon(...)))` with:

```dart
ClipRRect(
  borderRadius: BorderRadius.circular(10),
  child: AspectRatio(
    aspectRatio: 1,
    child: ProductImage(imageUrl: product.imageUrl, type: product.type),
  ),
),
```
(add `import '.../widgets/product_image.dart';`)
- The navigation `arguments: product.id` now passes a `String`.

- [ ] **Step 2: Update the `/product` route handler**

Find where `/product` is registered (`grep -rn "'/product'" lib/`). Change the argument cast from `int` to `String` and the product lookup to use the API/passed product instead of `productById(int)`.

- [ ] **Step 3: Verify**

Run: `flutter analyze lib/features/marketplace`
Expected: no analyzer errors in `marketplace_screen.dart` (errors remaining in `product_detail_screen.dart` are fixed in Task B7).

- [ ] **Step 4: Commit**

```bash
git add lib/features/marketplace/presentation/marketplace_screen.dart lib/<route file>
git commit -m "feat(marketplace): load products from api with loading and error states"
```

## Task B7: product detail consumes API (product + reviews)

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/product_detail_screen.dart`, `front-end-flutter/lib/features/marketplace/presentation/widgets/review_item.dart`

- [ ] **Step 1: Load reviews from the API**

In `product_detail_screen.dart`:
- Remove `reviewsForProduct(...)` (mock) usage; add `final _api = ProductsApi();` and load reviews for `product.id` via `_api.reviews(product.id)` using the same `_loading`/`_error`/`_reviews` pattern as Task B6.
- Replace the `_HeroImage`'s placeholder `Container(... Icon ...)` body with:

```dart
ClipRRect(
  borderRadius: BorderRadius.circular(20),
  child: SizedBox(
    height: 280,
    width: double.infinity,
    child: ProductImage(imageUrl: product.imageUrl, type: product.type, iconSize: 72),
  ),
)
```
(add the `product_image.dart` import.)

- [ ] **Step 2: Fix `review_item.dart`**

Where `review_item.dart` calls `reviewsForProduct(product.id)`, change it to accept the already-loaded `List<Review>` from the detail screen (pass it in) rather than reading the mock.

- [ ] **Step 3: Verify**

Run: `flutter analyze lib/features/marketplace`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add lib/features/marketplace/presentation/product_detail_screen.dart \
        lib/features/marketplace/presentation/widgets/review_item.dart
git commit -m "feat(marketplace): load product reviews from api"
```

## Task B8: checkout screen + delete mock

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart`
- Delete: `front-end-flutter/lib/features/marketplace/data/mock_marketplace.dart`

- [ ] **Step 1: Fix checkout id usages**

`checkout_screen.dart` calls `context.read<CartStore>().removeAll(product.id)` and `.decrement(product.id)` — these now pass `String`, which matches Task B3. Confirm no remaining `int`-typed product id locals.

- [ ] **Step 2: Delete the mock**

Run: `git rm lib/features/marketplace/data/mock_marketplace.dart`
Then `grep -rn "mock_marketplace\|mockProducts\|mockReviews\|reviewsForProduct\|productById" lib/` — expect **no matches**. Fix any stragglers.

- [ ] **Step 3: Analyze + test the whole app**

Run: `flutter analyze && flutter test`
Expected: no analyzer issues; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(marketplace): retire product mock data"
```

## Task B9: manual end-to-end verification

- [ ] **Step 1: Bring up the backend**

Run (from `back-end/`): `docker compose up -d postgres redis minio minio-init && uv run alembic upgrade head && uv run python -m app.seeds.products`

- [ ] **Step 2: Make a user admin and upload an image**

Register/login a user, set `is_admin=true` for it in the DB, then `POST /api/products/{id}/image` with a real image and confirm 200 + a presigned `image_url`. Open the URL in a browser — the image renders.

- [ ] **Step 3: Run the app and confirm**

Launch the Flutter app (emulator). The marketplace list and product detail show real photos (seeded + uploaded), with the icon fallback for products without an image. Add to cart / checkout still work.

---

## Notes / known limitations (from spec)

- `OrderItem` references the product's object key; replacing a product image can break thumbnails of past orders (copy-on-purchase is out of scope).
- No upload UI in the app — admins upload via the API.
- Single image per product; no thumbnails/resizing.
