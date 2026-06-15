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

import asyncio
import struct
import uuid
import zlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.products.models import Product, Review

if TYPE_CHECKING:
    from app.core.storage import ObjectStorage

# Sentinel author id for sample/seeded reviews (no real user owns them).
_SEED_AUTHOR_USER_ID = uuid.UUID(int=0)


def _ts(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)


def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Generate a valid solid-color RGB PNG using only the stdlib (no Pillow).

    Used to give seeded products a real, viewable image without committing
    binary assets to the repo.
    """

    def _chunk(typ: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + typ
            + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, color type 2 (RGB)
    row = b"\x00" + bytes(rgb) * width  # filter byte 0 + RGB pixels
    raw = row * height
    idat = zlib.compress(raw)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _unsplash(photo_id: str) -> str:
    """Build a sized, cropped JPEG URL from an Unsplash photo id.

    The CDN params give us an ~800x800 JPEG directly, so seeded images are
    small and square without any image processing (no Pillow needed). Unsplash
    License: free commercial use, no attribution required.
    """
    return f"https://images.unsplash.com/{photo_id}?w=800&h=800&fit=crop&q=80&fm=jpg"


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


# rating_avg/rating_count are the "headline" aggregates carried over from the
# mock; the listed reviews are an illustrative subset (as in the current app).
SEED_PRODUCTS: list[dict] = [
    {
        "name": "Guia de Redação Nota 1000",
        "photo_url": _unsplash("photo-1455390582262-044cdead277a"),
        "type": "apostila",
        "subtype": "Apostila Digital",
        "description": (
            "Estruturas prontas e repertório sociocultural para o ENEM, com "
            "modelos comentados e checklist de revisão."
        ),
        "price": "49.90",
        "rating_avg": 4.5,
        "rating_count": 128,
        "reviews": [
            {
                "author": "Ana Beatriz",
                "rating": 5,
                "comment": "Salvou minha redação! Os repertórios são excelentes.",
                "created_at": "2025-03-12",
            },
            {
                "author": "Carlos Henrique",
                "rating": 4,
                "comment": "Material muito completo, faltou só mais exemplos de conclusão.",
                "created_at": "2025-02-28",
            },
        ],
    },
    {
        "name": "Mastering Data Synthesis",
        "photo_url": _unsplash("photo-1551288049-bebda4e38f71"),
        "type": "curso",
        "subtype": "Premium Course",
        "description": (
            "Módulo avançado de Educação 5.0 com trilhas práticas de análise e síntese de dados."
        ),
        "price": "189.90",
        "rating_avg": 4.8,
        "rating_count": 64,
        "reviews": [
            {
                "author": "Marina Lopes",
                "rating": 5,
                "comment": "Conteúdo denso e muito bem explicado. Vale cada centavo.",
                "created_at": "2025-04-02",
            },
        ],
    },
    {
        "name": "Diagnostic AI Toolkit",
        "photo_url": _unsplash("photo-1488590528505-98d2b5aba04b"),
        "type": "digital",
        "subtype": "Digital Tool",
        "description": (
            "Ferramenta de diagnóstico com IA para mapear pontos fracos e gerar "
            "planos de estudo personalizados."
        ),
        "price": "45.00",
        "rating_avg": 4.2,
        "rating_count": 30,
        "reviews": [
            {
                "author": "Pedro Alves",
                "rating": 4,
                "comment": "A análise de pontos fracos é certeira.",
                "created_at": "2025-01-19",
            },
        ],
    },
    {
        "name": "Simulado ENEM Completo",
        "photo_url": _unsplash("photo-1434030216411-0b793f4b4173"),
        "type": "apostila",
        "subtype": "Apostila",
        "description": (
            "Quatro provas no formato oficial, gabarito comentado e correção da redação por TRI."
        ),
        "price": "29.90",
        "rating_avg": 4.6,
        "rating_count": 210,
        "reviews": [
            {
                "author": "Júlia Santos",
                "rating": 5,
                "comment": "Os simulados são idênticos à prova real. Recomendo!",
                "created_at": "2025-03-30",
            },
            {
                "author": "Rafael Costa",
                "rating": 4,
                "comment": "Correção da redação foi rápida e detalhada.",
                "created_at": "2025-03-21",
            },
        ],
    },
    {
        "name": "Mapa Mental de Biologia",
        "photo_url": _unsplash("photo-1532187863486-abf9dbad1b69"),
        "type": "digital",
        "subtype": "Material Digital",
        "description": (
            "Coletânea de mapas mentais de citologia, genética e ecologia para revisão rápida."
        ),
        "price": "19.90",
        "rating_avg": 4.0,
        "rating_count": 15,
        "reviews": [],
    },
    {
        "name": "Curso de Matemática Essencial",
        "photo_url": _unsplash("photo-1509228468518-180dd4864904"),
        "type": "curso",
        "subtype": "Curso",
        "description": (
            "Do básico ao avançado: funções, geometria e estatística com "
            "exercícios resolvidos passo a passo."
        ),
        "price": "149.90",
        "rating_avg": 4.9,
        "rating_count": 302,
        "reviews": [
            {
                "author": "Beatriz Nunes",
                "rating": 5,
                "comment": "Finalmente entendi funções. Professor explica muito bem.",
                "created_at": "2025-04-10",
            },
        ],
    },
]


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


async def main() -> None:
    from app.core.storage import ObjectStorage

    storage = ObjectStorage()
    async with SessionLocal() as session:
        inserted = await seed_products(session, storage=storage)
        total = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
    logger.info("seed: products inserted={} catalog_total={}", inserted, total)


if __name__ == "__main__":
    asyncio.run(main())
