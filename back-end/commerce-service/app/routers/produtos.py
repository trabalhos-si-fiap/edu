import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, requer_papel
from app.exceptions import (
    EstoqueNegativoError,
    EstoqueNotFoundError,
    ParceiroNotFoundError,
    ProductNotFoundError,
    SkuDuplicadoError,
)
from app.models.produto import Product
from app.redis_client import get_redis
from app.schemas.estoque import AjusteEstoqueIn, EstoqueAjusteList, EstoqueAjusteOut
from app.schemas.produto import (
    CategoryList,
    CategoryOut,
    ProductIn,
    ProductList,
    ProductOut,
    ProductPatch,
)
from app.schemas.review import ReviewIn, ReviewList, ReviewOut
from app.services import estoque as estoque_services
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
    # `le=2_147_483_647` (int32 max): `Fornecedor.id`/`Estoque.fornecedor_id`
    # são `Integer` (int32). Sem teto, um `partner_id` fora da faixa (ex.: 3
    # bilhões) passaria da validação do Pydantic direto para o `WHERE` do
    # join e estouraria `asyncpg.exceptions.DataError` não tratado (500) —
    # mesma classe de bug que a task 3 corrigiu em `AjusteEstoqueIn.delta`.
    partner_id: int | None = Query(default=None, ge=1, le=2_147_483_647),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductList:
    """Catálogo. Exige autenticação (qualquer papel) — não restringe por papel
    porque não há razão de negócio: o aluno monta carrinho, e separador,
    entregador e admin também precisam consultar o catálogo.

    `limit` 1-100 com default 20, `q` até 160 caracteres, envelope com
    `total`/`limit`/`offset`: os quatro são contrato, medidos contra o
    legacy. Mudar qualquer um quebra o app na fase 4.

    `partner_id` filtra o catálogo pelo parceiro DONO do estoque (task 7,
    spec B) — produto pertence ao parceiro através de `Estoque.fornecedor_id`,
    não por coluna direta em `products`. Parceiro inativo ou inexistente
    devolve lista vazia, nunca 404: ver app/services/produtos.py.
    """
    items, total = await services.listar_produtos(
        db, q=q, partner_id=partner_id, limit=limit, offset=offset
    )
    return ProductList(
        items=[await _product_out(p, storage=storage, redis=redis) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def criar_produto(
    payload: ProductIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProductOut:
    """Cria o produto E a linha de estoque no mesmo ato — admin-only. Ver
    app/services/produtos.py::criar_produto."""
    try:
        product = await services.criar_produto(db, payload)
    except ParceiroNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found"
        ) from exc
    except SkuDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um produto com este SKU"
        ) from exc
    return await _product_out(product, storage=storage, redis=redis)


@router.get("/categories", response_model=CategoryList)
async def listar_categorias(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryList:
    rows = await services.listar_categorias(db)
    return CategoryList(items=[CategoryOut(type=t, count=c) for t, c in rows])


@router.post(
    "/{product_id}/stock-adjustments",
    response_model=EstoqueAjusteOut,
    status_code=status.HTTP_201_CREATED,
)
async def ajustar_estoque(
    product_id: uuid.UUID,
    payload: AjusteEstoqueIn,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> EstoqueAjusteOut:
    """Ajuste por DELTA, com auditoria, atômico. Ver app/services/estoque.py."""
    try:
        estoque_id = await estoque_services.obter_estoque_do_produto(db, product_id)
        _, ajuste = await estoque_services.aplicar_ajuste(
            db,
            estoque_id=estoque_id,
            delta=payload.delta,
            motivo=payload.motivo,
            autor_id=uuid.UUID(user["sub"]),
        )
    except EstoqueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock record not found"
        ) from exc
    except EstoqueNegativoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O ajuste deixaria o estoque negativo",
        ) from exc
    return EstoqueAjusteOut.model_validate(ajuste)


@router.get("/{product_id}/stock-adjustments", response_model=EstoqueAjusteList)
async def listar_ajustes_estoque(
    product_id: uuid.UUID,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EstoqueAjusteList:
    try:
        items, total = await estoque_services.listar_ajustes(
            db, produto_id=product_id, limit=limit, offset=offset
        )
    except EstoqueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock record not found"
        ) from exc
    return EstoqueAjusteList(
        items=[EstoqueAjusteOut.model_validate(a) for a in items],
        total=total,
        limit=limit,
        offset=offset,
    )


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


@router.put("/{product_id}", response_model=ProductOut)
async def atualizar_produto(
    product_id: uuid.UUID,
    payload: ProductPatch,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProductOut:
    """Edita o catálogo — admin-only. NÃO toca em estoque; quantidade só
    muda pelo ajuste auditado. Ver app/services/produtos.py::atualizar_produto."""
    try:
        product = await services.atualizar_produto(db, product_id, payload)
    except ProductNotFoundError as exc:
        raise _NOT_FOUND from exc
    except SkuDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um produto com este SKU"
        ) from exc
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
