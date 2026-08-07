import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import ProductNotFoundError
from app.models.produto import Product
from app.redis_client import get_redis
from app.schemas.produto import (
    CategoryList,
    CategoryOut,
    ProductList,
    ProductOut,
)
from app.schemas.review import ReviewIn, ReviewList, ReviewOut
from app.services import produtos as services
from app.services.auth_client import AuthServiceUnavailableError, get_me
from app.services.media import presigned_image_url
from app.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/products", tags=["products"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


async def _product_out(
    product: Product, *, storage: ObjectStorage, redis: aioredis.Redis
) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.image_url = await presigned_image_url(product.image_url, storage=storage, redis=redis)
    return out


@router.get("", response_model=ProductList)
async def listar_produtos(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductList:
    """Catálogo. Exige autenticação (qualquer papel) — não restringe por papel
    porque não há razão de negócio: o aluno monta carrinho, e separador,
    entregador e admin também precisam consultar o catálogo.

    `limit` 1-100 com default 20, `q` até 160 caracteres, envelope com
    `total`/`limit`/`offset`: os quatro são contrato, medidos contra o
    legacy. Mudar qualquer um quebra o app na fase 4.
    """
    items, total = await services.listar_produtos(db, q=q, limit=limit, offset=offset)
    return ProductList(
        items=[await _product_out(p, storage=storage, redis=redis) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/categories", response_model=CategoryList)
async def listar_categorias(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryList:
    rows = await services.listar_categorias(db)
    return CategoryList(items=[CategoryOut(type=t, count=c) for t, c in rows])


@router.get("/{product_id}", response_model=ProductOut)
async def detalhe_produto(
    product_id: uuid.UUID,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProductOut:
    try:
        product = await services.buscar_produto(db, product_id)
    except ProductNotFoundError as exc:
        raise _NOT_FOUND from exc
    return await _product_out(product, storage=storage, redis=redis)


@router.get("/{product_id}/reviews", response_model=ReviewList)
async def listar_reviews(
    product_id: uuid.UUID,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewList:
    """`rating_avg` e `rating_count` vêm do PRODUTO, não da página de reviews:
    são o agregado do catálogo inteiro, e a página é só um recorte. Trocar um
    pelo outro faria a nota cair conforme o usuário paginasse."""
    try:
        product = await services.buscar_produto(db, product_id)
        items, total = await services.listar_reviews(db, product_id, limit=limit, offset=offset)
    except ProductNotFoundError as exc:
        raise _NOT_FOUND from exc
    return ReviewList(
        items=[ReviewOut.model_validate(r) for r in items],
        total=total,
        rating_avg=float(product.rating_avg),
        rating_count=product.rating_count,
    )


@router.post("/{product_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def criar_review(
    product_id: uuid.UUID,
    payload: ReviewIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewOut:
    try:
        me = await get_me(user["raw_token"])
    except AuthServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de usuários indisponível",
        ) from exc

    try:
        review = await services.criar_review(
            db,
            product_id,
            user_id=uuid.UUID(user["sub"]),
            author=me["name"],
            data=payload,
        )
    except ProductNotFoundError as exc:
        raise _NOT_FOUND from exc
    return ReviewOut.model_validate(review)
