"""Idempotent seed for the products catalog.

Mirrors the Flutter mock catalog (mock_marketplace.dart) so the connected app
shows the same data it does today with mocks. Safe to run repeatedly — products
are keyed by name and skipped if already present.

Run inside the api container:

    uv run python -m app.seeds.products
"""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.modules.products.models import Product, Review

# Sentinel author id for sample/seeded reviews (no real user owns them).
_SEED_AUTHOR_USER_ID = uuid.UUID(int=0)


def _ts(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)


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
            "Módulo avançado de Educação 5.0 com trilhas práticas de análise e "
            "síntese de dados."
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
            "Quatro provas no formato oficial, gabarito comentado e correção da "
            "redação por TRI."
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
            "Coletânea de mapas mentais de citologia, genética e ecologia para "
            "revisão rápida."
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


async def seed_products(session: AsyncSession) -> int:
    """Insert any missing catalog products (and their sample reviews).

    Returns the number of products inserted. Existing products (matched by
    name) are left untouched, so this is safe to run repeatedly.
    """
    existing_names = set(
        (await session.execute(select(Product.name))).scalars().all()
    )

    inserted = 0
    for data in SEED_PRODUCTS:
        if data["name"] in existing_names:
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
        inserted += 1

    await session.commit()
    return inserted


async def main() -> None:
    async with SessionLocal() as session:
        inserted = await seed_products(session)
        total = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
    logger.info("seed: products inserted={} catalog_total={}", inserted, total)


if __name__ == "__main__":
    asyncio.run(main())
