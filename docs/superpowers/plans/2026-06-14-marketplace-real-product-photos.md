# Marketplace Real Product Photos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the solid-color placeholder images of the 6 marketplace catalog products with real, free-license (Unsplash) photos downloaded at seed time and uploaded to the existing object storage (MinIO dev / R2 prod).

**Architecture:** Extend the existing idempotent product seed (`app/seeds/products.py`). Each `SEED_PRODUCTS` entry gains a curated `photo_url`. At seed time, a download helper (`_fetch_image`, thin httpx wrapper) fetches the JPEG and `ObjectStorage.put_object` stores it under `products/seed-{index}.jpg`; the product's `image_url` (the object key) is updated. The seed **always overwrites** the image of the 6 products and deletes any superseded object key (best-effort). Download failures are caught and leave the current image untouched. The download function is injected (`fetch_image=`) so tests exercise the business logic without network.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x async, `httpx` (already a project dep), `aioboto3` (via `ObjectStorage`), pytest (async), loguru, ruff.

**Spec:** `docs/superpowers/specs/2026-06-14-marketplace-real-product-photos-design.md`

---

## File Structure

- **Modify:** `back-end/app/seeds/products.py`
  - Add `_unsplash(photo_id)` URL builder and `photo_url` to each `SEED_PRODUCTS` entry.
  - Add `_fetch_image(url)` httpx download helper (timeout + size cap).
  - Change `seed_products()` signature to accept `fetch_image=` and rework the per-product image logic (download → upload `.jpg` → delete old key → set `image_url`; always overwrite; failure-safe).
  - Remove the now-unused `_seed_image()` helper. Keep `_solid_png()` (still covered by a test; harmless fallback).
  - Update the module docstring.
- **Modify:** `back-end/tests/seeds/test_products_seed.py`
  - Extend `_RecordingStorage` (record deletes + add `delete_object`).
  - Add `_JPEG_BYTES` + `_fake_fetch` helpers.
  - Update/replace the storage tests to assert `.jpg` / `image/jpeg`, always-overwrite, old-object deletion, and download-failure safety.

All work is in the `back-end/` package. Run commands from `back-end/`.

---

## Task 1: Curated photo URLs on every seed product

**Files:**
- Modify: `back-end/app/seeds/products.py`
- Test: `back-end/tests/seeds/test_products_seed.py`

- [ ] **Step 1: Write the failing test**

Add to `back-end/tests/seeds/test_products_seed.py` (top-level function, after the existing imports):

```python
def test_every_seed_product_has_a_unique_unsplash_photo_url() -> None:
    from app.seeds.products import SEED_PRODUCTS

    urls = [data["photo_url"] for data in SEED_PRODUCTS]
    for url in urls:
        assert url.startswith("https://images.unsplash.com/")
        assert "fm=jpg" in url
        assert "fit=crop" in url
    assert len(set(urls)) == len(urls)  # one distinct photo per product
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/seeds/test_products_seed.py::test_every_seed_product_has_a_unique_unsplash_photo_url -v`
Expected: FAIL with `KeyError: 'photo_url'`.

- [ ] **Step 3: Add the URL builder and `photo_url` fields**

In `back-end/app/seeds/products.py`, add this helper just above the `SEED_PRODUCTS` list (after the `_solid_png` function):

```python
def _unsplash(photo_id: str) -> str:
    """Build a sized, cropped JPEG URL from an Unsplash photo id.

    The CDN params give us an ~800x800 JPEG directly, so seeded images are
    small and square without any image processing (no Pillow needed). Unsplash
    License: free commercial use, no attribution required.
    """
    return f"https://images.unsplash.com/{photo_id}?w=800&h=800&fit=crop&q=80&fm=jpg"
```

Then add a `"photo_url"` key to each of the 6 dicts in `SEED_PRODUCTS`, matched by name (add the key anywhere inside each dict, e.g. right after `"name"`):

```python
# "Guia de Redação Nota 1000"
"photo_url": _unsplash("photo-1455390582262-044cdead277a"),
# "Mastering Data Synthesis"
"photo_url": _unsplash("photo-1551288049-bebda4e38f71"),
# "Diagnostic AI Toolkit"
"photo_url": _unsplash("photo-1488590528505-98d2b5aba04b"),
# "Simulado ENEM Completo"
"photo_url": _unsplash("photo-1434030216411-0b793f4b4173"),
# "Mapa Mental de Biologia"
"photo_url": _unsplash("photo-1532187863486-abf9dbad1b69"),
# "Curso de Matemática Essencial"
"photo_url": _unsplash("photo-1509228468518-180dd4864904"),
```

(These 6 ids were verified to return `200 image/jpeg` at plan time.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/seeds/test_products_seed.py::test_every_seed_product_has_a_unique_unsplash_photo_url -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/seeds/products.py back-end/tests/seeds/test_products_seed.py
git commit -m "feat(seeds): add curated unsplash photo urls to catalog products"
```

---

## Task 2: Download + always-overwrite real photos in the seed

**Files:**
- Modify: `back-end/app/seeds/products.py`
- Test: `back-end/tests/seeds/test_products_seed.py`

- [ ] **Step 1: Update the test scaffolding**

In `back-end/tests/seeds/test_products_seed.py`, replace the existing `_RecordingStorage` class with this version (adds delete recording) and add the fetch fakes just below it:

```python
class _RecordingStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str]] = []
        self.deletes: list[str] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        self.puts.append((key, content_type))

    async def delete_object(self, key: str) -> None:
        self.deletes.append(key)


# Minimal valid-looking JPEG payload for the fake downloader.
_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64 + b"\xff\xd9"


async def _fake_fetch(url: str) -> bytes:
    return _JPEG_BYTES
```

- [ ] **Step 2: Update the existing storage test to expect JPEG keys**

Replace `test_seed_uploads_image_and_sets_key_when_storage_given` with:

```python
async def test_seed_uploads_image_and_sets_key_when_storage_given(
    db_session: AsyncSession,
) -> None:
    storage = _RecordingStorage()
    inserted = await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)
    assert inserted == len(SEED_PRODUCTS)
    assert len(storage.puts) == len(SEED_PRODUCTS)
    assert all(
        k.startswith("products/seed-") and k.endswith(".jpg") and ct == "image/jpeg"
        for k, ct in storage.puts
    )

    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    assert product.image_url.startswith("products/seed-")
    assert product.image_url.endswith(".jpg")
```

- [ ] **Step 3: Update the backfill test to use the fake fetcher**

Replace `test_seed_backfills_images_for_existing_products_without_one` with:

```python
async def test_seed_backfills_images_for_existing_products_without_one(
    db_session: AsyncSession,
) -> None:
    # Products inserted before the storage wiring have an empty image_url.
    # Re-running with storage must backfill them (download + upload).
    await seed_products(db_session)
    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    assert product.image_url == ""

    storage = _RecordingStorage()
    inserted = await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)
    assert inserted == 0  # nothing new inserted
    assert len(storage.puts) == len(SEED_PRODUCTS)  # but every product got an image

    await db_session.refresh(product)
    assert product.image_url.startswith("products/seed-")
    assert product.image_url.endswith(".jpg")
```

- [ ] **Step 4: Replace the no-overwrite test with always-overwrite + delete-old + failure tests**

Delete `test_seed_does_not_overwrite_existing_images` entirely and add these three tests:

```python
async def test_seed_always_overwrites_images(db_session: AsyncSession) -> None:
    storage = _RecordingStorage()
    await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)

    # A second run re-uploads every product's image (always overwrite). Keys are
    # already .jpg, so there is no superseded object to delete.
    storage2 = _RecordingStorage()
    await seed_products(db_session, storage=storage2, fetch_image=_fake_fetch)
    assert len(storage2.puts) == len(SEED_PRODUCTS)
    assert storage2.deletes == []


async def test_seed_replaces_legacy_png_and_deletes_old_object(
    db_session: AsyncSession,
) -> None:
    # Simulate a product that still carries a legacy solid-color .png key.
    await seed_products(db_session)
    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    product.image_url = "products/seed-0.png"
    await db_session.commit()

    storage = _RecordingStorage()
    await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)

    await db_session.refresh(product)
    assert product.image_url == "products/seed-0.jpg"
    assert "products/seed-0.png" in storage.deletes


async def test_seed_download_failure_keeps_existing_image(
    db_session: AsyncSession,
) -> None:
    storage = _RecordingStorage()
    await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)
    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    before = product.image_url
    assert before.endswith(".jpg")

    async def _boom(url: str) -> bytes:
        raise RuntimeError("network down")

    storage2 = _RecordingStorage()
    await seed_products(db_session, storage=storage2, fetch_image=_boom)
    assert storage2.puts == []

    await db_session.refresh(product)
    assert product.image_url == before
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `uv run pytest tests/seeds/test_products_seed.py -v`
Expected: FAIL — `seed_products()` has no `fetch_image` keyword (`TypeError`), and current keys end in `.png` / content-type `image/png`.

- [ ] **Step 6: Implement the download helper and reworked seed**

In `back-end/app/seeds/products.py`:

6a. Add imports near the top (with the other imports):

```python
from collections.abc import Awaitable, Callable

import httpx

from app.core.config import settings
```

(Keep the existing imports; `from loguru import logger` is already present.)

6b. Add the download helper just below `_unsplash`:

```python
_FETCH_TIMEOUT_SECONDS = 15.0


async def _fetch_image(url: str) -> bytes:
    """Download a curated product photo as bytes.

    Thin httpx wrapper (I/O glue, exercised by the real seed run). Raises on
    network/HTTP error or when the body exceeds the configured upload cap.
    seed_products() catches failures and keeps the product's current image, so a
    transient error never erases a good photo.
    """
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        body = resp.content
    if len(body) > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValueError(f"image exceeds max upload bytes: {len(body)}")
    return body
```

6c. Delete the now-unused `_seed_image` nested helper and replace the body of `seed_products` with the version below. Update the signature and the per-product loop:

```python
async def seed_products(
    session: AsyncSession,
    *,
    storage: "ObjectStorage | None" = None,
    fetch_image: Callable[[str], Awaitable[bytes]] = _fetch_image,
) -> int:
    """Insert any missing catalog products (and their sample reviews).

    Returns the number of products inserted. Existing products (matched by
    name) are not re-inserted, so this is safe to run repeatedly.

    When storage is provided, each product's curated photo is downloaded via
    fetch_image and uploaded under products/seed-{index}.jpg, and image_url is
    set to that key. Images are ALWAYS overwritten (the seed runs manually, not
    on boot); any superseded object key is deleted best-effort. A download
    failure is logged and leaves the product's current image untouched.
    """
    existing = {p.name: p for p in (await session.execute(select(Product))).scalars().all()}

    async def _apply_image(product: Product, index: int, photo_url: str | None) -> None:
        if storage is None or not photo_url:
            return
        key = f"products/seed-{index}.jpg"
        try:
            body = await fetch_image(photo_url)
        except Exception as exc:  # network/HTTP/timeout/oversize
            logger.warning("seed: failed to download photo for {!r}: {}", product.name, exc)
            return
        await storage.put_object(key, body, "image/jpeg")
        if product.image_url and product.image_url != key:
            try:
                await storage.delete_object(product.image_url)
            except Exception as exc:  # best-effort cleanup of the old object
                logger.warning(
                    "seed: failed to delete superseded object {!r}: {}", product.image_url, exc
                )
        product.image_url = key

    inserted = 0
    for index, data in enumerate(SEED_PRODUCTS):
        photo_url = data.get("photo_url")
        if data["name"] in existing:
            await _apply_image(existing[data["name"]], index, photo_url)
            continue
        product = Product(
            name=data["name"],
            type=data["type"],
            subtype=data["subtype"],
            description=data["description"],
            price=Decimal(data["price"]),
            rating_avg=data["rating_avg"],
            rating_count=data["rating_count"],
        )
        for review in data["reviews"]:
            product.reviews.append(
                Review(
                    user_id=_SEED_AUTHOR_USER_ID,
                    author=review["author"],
                    rating=review["rating"],
                    comment=review["comment"],
                    created_at=_ts(review["created_at"]),
                )
            )
        session.add(product)
        await _apply_image(product, index, photo_url)
        inserted += 1

    await session.commit()
    return inserted
```

6d. Update the module docstring (lines describing the solid-color placeholder) to describe the real-photo behavior:

```python
"""Idempotent seed for the products catalog.

Mirrors the Flutter mock catalog (mock_marketplace.dart) so the connected app
shows the same data it does today with mocks. Safe to run repeatedly — products
are keyed by name and skipped if already present.

When an ObjectStorage instance is passed to seed_products(), each product's
curated free-license (Unsplash) photo is downloaded and uploaded under
products/seed-{index}.jpg, and the product's image_url is set to that key.
Images are always overwritten on each run. _solid_png() is kept as a stdlib-only
fallback for any future entry that has no photo_url.

Run inside the api container:

    uv run python -m app.seeds.products
"""
```

- [ ] **Step 7: Run the full seed test file to verify it passes**

Run: `uv run pytest tests/seeds/test_products_seed.py -v`
Expected: PASS — all tests, including `test_solid_png_is_a_valid_image`, `test_inserts_full_catalog`, `test_is_idempotent`.

- [ ] **Step 8: Lint and format**

Run: `uv run ruff check app/seeds/products.py tests/seeds/test_products_seed.py && uv run ruff format app/seeds/products.py tests/seeds/test_products_seed.py`
Expected: no errors; formatting clean (or auto-applied with no logical change).

- [ ] **Step 9: Commit**

```bash
git add back-end/app/seeds/products.py back-end/tests/seeds/test_products_seed.py
git commit -m "feat(seeds): download and store real product photos in object storage"
```

---

## Task 3: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the complete backend test suite**

Run (from `back-end/`): `uv run pytest -q`
Expected: PASS (no regressions from the seed changes).

- [ ] **Step 2: Sanity-check the curated URLs still resolve (optional, requires network)**

Run (from `back-end/`):
```bash
uv run python -c "
import asyncio
from app.seeds.products import SEED_PRODUCTS, _fetch_image
async def main():
    for d in SEED_PRODUCTS:
        b = await _fetch_image(d['photo_url'])
        print(d['name'], len(b), 'bytes')
asyncio.run(main())
"
```
Expected: each product prints a non-zero byte count (tens of KB). If any URL fails, swap its Unsplash id in `SEED_PRODUCTS` for an equivalent and re-run.

- [ ] **Step 3: (Manual, when the dev stack is up) apply to the running environment**

Not part of this plan's automated work, but documented for the operator:
```bash
make back-up        # brings up postgres + minio + api with LAN-derived R2_PUBLIC_ENDPOINT_URL
docker compose exec api uv run python -m app.seeds.products
```
The 6 products' `image_url` keys become `products/seed-{index}.jpg`; the app receives presigned URLs and renders the real photos.

---

## Self-Review

**Spec coverage:**
- Curated Unsplash URLs in seed → Task 1. ✅
- Download at seed time via httpx (`_fetch_image`) → Task 2 step 6b. ✅
- `.jpg` key + `image/jpeg` content-type → Task 2 steps 2, 6c. ✅
- Always overwrite the 6 products → Task 2 steps 4 (`test_seed_always_overwrites_images`), 6c. ✅
- Delete superseded object key best-effort → Task 2 steps 4 (`test_seed_replaces_legacy_png_and_deletes_old_object`), 6c. ✅
- Download failure keeps current image + warning → Task 2 steps 4 (`test_seed_download_failure_keeps_existing_image`), 6c. ✅
- `fetch_image` dependency injection for testability → Task 2 (signature in 6c, fakes in step 1). ✅
- `_solid_png` kept as fallback → Task 2 (not removed; `test_solid_png_is_a_valid_image` retained). ✅
- No model/route/Flutter changes, no repo binaries → none touched. ✅
- URL validation → Task 1 step 3 note + Task 3 step 2. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; the 6 Unsplash ids are concrete and verified.

**Type consistency:** `seed_products(session, *, storage=None, fetch_image=_fetch_image)`, `_fetch_image(url) -> bytes`, `_unsplash(photo_id) -> str`, `_RecordingStorage.put_object/delete_object`, object key `products/seed-{index}.jpg` — names and signatures match across all tasks.
