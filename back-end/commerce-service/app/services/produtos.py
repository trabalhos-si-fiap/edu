import uuid

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ParceiroNotFoundError, ProductNotFoundError, SkuDuplicadoError
from app.models.produto import Estoque, Fornecedor, Product
from app.models.review import Review
from app.schemas.produto import ProductIn, ProductPatch
from app.schemas.review import ReviewIn


async def listar_produtos(
    db: AsyncSession,
    *,
    q: str | None = None,
    partner_id: int | None = None,
    include_inactive: bool = False,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    if not include_inactive:
        # `products.active` era escrito pelo painel (switch "STATUS DO
        # PRODUTO"), round-trippado pelo schema e lido por NADA: produto
        # desativado continuava no catálogo, no filtro de parceiro, no
        # carrinho e no pedido. Um controle que persiste e não faz efeito é
        # pior que controle nenhum.
        #
        # `include_inactive` é a escotilha do PAINEL, não do app: o admin
        # precisa enxergar a linha inativa para reativá-la, e a rota exige
        # papel `admin` para aceitar o parâmetro (ver
        # app/routers/produtos.py). Filtro no serviço e não na tela para
        # valer nas duas portas — catálogo e filtro por parceiro — de uma vez.
        stmt = stmt.where(Product.active.is_(True))
        count_stmt = count_stmt.where(Product.active.is_(True))

    if partner_id is not None:
        # Produto pertence ao parceiro ATRAVÉS do estoque — não há coluna de
        # fornecedor em `products`, e não deve haver: um produto pode ser
        # estocado por mais de um fornecedor (a unicidade de `estoque` é do
        # PAR produto+fornecedor, `uq_produto_fornecedor`). Por isso o filtro
        # é um subselect de `produto_id` (`WHERE id IN (...)`), não um
        # `join(Estoque)` direto na listagem: um join duplicaria a linha do
        # produto uma vez por fornecedor que o estoca — inflando `items` E
        # `total`, e fazendo a paginação repetir linha entre páginas.
        #
        # O join com `fornecedores` dentro do subselect é o que faz do
        # "ativo" uma REGRA em vez de um `if` na tela: parceiro inativo
        # simplesmente não casa, e a listagem sai vazia — sem 404, sem ramo
        # especial, sem nome de parceiro em lugar nenhum do código.
        vinculo = (
            select(Estoque.produto_id)
            .join(Fornecedor, Fornecedor.id == Estoque.fornecedor_id)
            .where(Estoque.fornecedor_id == partner_id, Fornecedor.ativo.is_(True))
        )
        stmt = stmt.where(Product.id.in_(vinculo))
        count_stmt = count_stmt.where(Product.id.in_(vinculo))

    if q:
        # `ilike` com parâmetro bound — o pattern vai como valor, nunca
        # concatenado na string SQL (regra 1 do CLAUDE.md).
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))

    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def listar_categorias(db: AsyncSession) -> list[tuple[str, int]]:
    stmt = (
        select(Product.type, func.count().label("count"))
        .group_by(Product.type)
        .order_by(Product.type)
    )
    return [(row.type, row.count) for row in (await db.execute(stmt)).all()]


async def buscar_produto(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError()
    return product


async def criar_produto(db: AsyncSession, data: ProductIn) -> Product:
    """Cria o produto e a linha de estoque na MESMA transação.

    `sku` é único por um índice PARCIAL do banco (`uq_products_sku`, `WHERE
    sku <> ''`) — a detecção de duplicata é pelo `IntegrityError` do INSERT,
    não por um SELECT prévio: SELECT-então-INSERT é uma corrida (regra 3 do
    CLAUDE.md), e o índice é a única coisa que resolve duas criações
    concorrentes do mesmo sku.
    """
    fornecedor = await db.get(Fornecedor, data.fornecedor_id)
    if fornecedor is None:
        raise ParceiroNotFoundError()

    product = Product(
        name=data.name,
        type=data.type,
        subtype=data.subtype,
        description=data.description,
        price=data.price,
        sku=data.sku,
        active=data.active,
    )
    db.add(product)
    try:
        # Flush, não commit: o produto e o estoque sobem na MESMA transação.
        # Um produto sem linha de estoque quebraria a invariante da spec
        # ("todo produto tem estoque") no intervalo entre os dois commits.
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SkuDuplicadoError() from exc

    db.add(
        Estoque(
            produto_id=product.id,
            fornecedor_id=fornecedor.id,
            quantidade=data.quantidade_inicial,
            estoque_minimo=data.estoque_minimo,
        )
    )
    await db.commit()
    await db.refresh(product)
    logger.info("products: produto criado id={} sku={}", product.id, product.sku)
    return product


async def atualizar_produto(db: AsyncSession, product_id: uuid.UUID, data: ProductPatch) -> Product:
    """Edita o catálogo. NÃO toca em estoque — quantidade só muda pelo ajuste
    auditado (`app/services/estoque.py`); um PUT que mexesse no saldo
    contornaria a trilha que a task 3 existe para garantir.

    Mesma detecção de duplicata de `criar_produto`: `IntegrityError` do
    commit, não SELECT prévio.
    """
    product = await buscar_produto(db, product_id)  # levanta ProductNotFoundError
    for campo, valor in data.model_dump().items():
        setattr(product, campo, valor)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SkuDuplicadoError() from exc
    await db.refresh(product)
    return product


async def listar_reviews(
    db: AsyncSession, product_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Review], int]:
    # Valida que o produto existe (404 caso contrário) antes de listar.
    await buscar_produto(db, product_id)

    stmt = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count()).select_from(Review).where(Review.product_id == product_id)
        )
    ).scalar_one()
    return items, total


async def criar_review(
    db: AsyncSession,
    product_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    author: str,
    data: ReviewIn,
) -> Review:
    # Lock na linha do produto para que reviews concorrentes atualizem os
    # agregados desnormalizados atomicamente (regra 3 do CLAUDE.md). O
    # SELECT ... FOR UPDATE e o UPDATE dividem a transação da sessão e
    # commitam juntos; o lock vale até o commit.
    product = (
        await db.execute(select(Product).where(Product.id == product_id).with_for_update())
    ).scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError()

    review = Review(
        product_id=product_id,
        user_id=user_id,
        author=author,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)

    new_count = product.rating_count + 1
    new_avg = (float(product.rating_avg) * product.rating_count + data.rating) / new_count
    product.rating_count = new_count
    product.rating_avg = round(new_avg, 2)

    await db.commit()
    await db.refresh(review)
    logger.info("products: review criada id={} product={}", review.id, product_id)
    return review
