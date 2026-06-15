from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models import Product, Review
from app.seeds.products import SEED_PRODUCTS, seed_products


def test_every_seed_product_has_a_unique_unsplash_photo_url() -> None:
    from app.seeds.products import SEED_PRODUCTS

    urls = [data["photo_url"] for data in SEED_PRODUCTS]
    for url in urls:
        assert url.startswith("https://images.unsplash.com/")
        assert "fm=jpg" in url
        assert "fit=crop" in url
    assert len(set(urls)) == len(urls)  # one distinct photo per product


class TestProductsSeed:
    async def test_inserts_full_catalog(self, db_session: AsyncSession) -> None:
        inserted = await seed_products(db_session)
        assert inserted == len(SEED_PRODUCTS)

        total = (await db_session.execute(select(func.count()).select_from(Product))).scalar_one()
        assert total == len(SEED_PRODUCTS)

    async def test_seeds_sample_reviews_and_headline_aggregates(
        self, db_session: AsyncSession
    ) -> None:
        await seed_products(db_session)

        product = (
            await db_session.execute(
                select(Product).where(Product.name == "Guia de Redação Nota 1000")
            )
        ).scalar_one()
        assert product.rating_count == 128
        assert float(product.rating_avg) == 4.5

        review_count = (
            await db_session.execute(
                select(func.count()).select_from(Review).where(Review.product_id == product.id)
            )
        ).scalar_one()
        assert review_count == 2

    async def test_is_idempotent(self, db_session: AsyncSession) -> None:
        first = await seed_products(db_session)
        second = await seed_products(db_session)
        assert first == len(SEED_PRODUCTS)
        assert second == 0

        total = (await db_session.execute(select(func.count()).select_from(Product))).scalar_one()
        assert total == len(SEED_PRODUCTS)


def test_solid_png_is_a_valid_image() -> None:
    from app.core.media import validate_image_bytes
    from app.seeds.products import _solid_png

    png = _solid_png(8, 8, (10, 20, 30))
    ext, content_type = validate_image_bytes(png, declared_type="image/png")
    assert ext == "png"
    assert content_type == "image/png"


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
