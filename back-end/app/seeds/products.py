"""Idempotent seed for the products catalog.

Mirrors the Flutter mock catalog (mock_marketplace.dart) so the connected app
shows the same data it does today with mocks. Safe to run repeatedly — products
are keyed by name and skipped if already present.

When an ObjectStorage instance is passed to seed_products(), a deterministic
solid-color placeholder PNG is generated (stdlib only, no Pillow) and uploaded
per product, and the product's image_url is set to the resulting object key.

Run inside the api container:

    uv run python -m app.seeds.products
"""

import asyncio
import struct
import uuid
import zlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


# rating_avg/rating_count are the "headline" aggregates carried over from the
# mock; the listed reviews are an illustrative subset (as in the current app).
SEED_PRODUCTS: list[dict] = [
    {
        "name": "Guia de Redação Nota 1000",
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


async def seed_products(session: AsyncSession, *, storage: "ObjectStorage | None" = None) -> int:
    """Insert any missing catalog products (and their sample reviews).

    Returns the number of products inserted. Existing products (matched by
    name) are not re-inserted, so this is safe to run repeatedly.

    When storage is provided, a deterministic solid-color PNG placeholder is
    generated and uploaded for each newly inserted product, and image_url is
    set to the resulting object key. Existing products whose image_url is still
    empty (e.g. seeded before the storage wiring) are backfilled the same way;
    products that already have an image are never overwritten.
    """
    existing = {p.name: p for p in (await session.execute(select(Product))).scalars().all()}

    def _seed_image(index: int) -> tuple[str, tuple[int, int, int]]:
        key = f"products/seed-{index}.png"
        color = ((index * 53) % 256, (index * 97) % 256, (index * 151) % 256)
        return key, color

    inserted = 0
    for index, data in enumerate(SEED_PRODUCTS):
        if data["name"] in existing:
            # Already present (matched by name) — backfill a placeholder image
            # for rows that predate the storage wiring, but never overwrite an
            # image that's already set. Keeps the seed safe to re-run.
            current = existing[data["name"]]
            if storage is not None and not current.image_url:
                key, color = _seed_image(index)
                await storage.put_object(key, _solid_png(400, 400, color), "image/png")
                current.image_url = key
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
        if storage is not None:
            key, color = _seed_image(index)
            await storage.put_object(key, _solid_png(400, 400, color), "image/png")
            product.image_url = key
        session.add(product)
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
