"""Testes de paridade da camada de serviço de produtos — porte de
`legacy/tests/modules/products/test_services.py` (9 testes, 4 classes), o
buraco que o portão do bloco B (task B11) mediu: nenhum dos nove nomes
existia no commerce sob nome nenhum
(`grep -rn <nome> back-end/commerce-service/tests/` sai 1 para os nove).

Duas propriedades que este arquivo trava não tinham NENHUMA guarda antes
dele — medido por mutação contra a árvore commitada em `90a8aed`:

- `Product.name.ilike` → `Product.name.like` em `app/services/produtos.py`
  deixava a suíte inteira verde (`177 passed`). A busca `?q=` deixava de ser
  case-insensitive sem nenhum teste vermelho.
- `total` → `len(items)` em `listar_produtos` deixava a suíte inteira verde
  (`177 passed`). O `total` da paginação deixava de reportar a contagem
  completa sem nenhum teste vermelho.

Adaptações em relação ao legacy, além da troca de imports:

- Nomes dos serviços em português, convenção do commerce-service (mesma troca
  que a task B6 já fez ao portar as rotas): `services.list_products` →
  `listar_produtos`, `list_categories` → `listar_categorias`, `get_product` →
  `buscar_produto`, `create_review` → `criar_review`.
- `ProductNotFound` → `ProductNotFoundError` (`app/exceptions.py`; o sufixo
  `Error` é exigido pela regra N818 do ruff — ver a docstring da própria
  exceção).
- O legacy usa `created_user` (um `User` real criado por
  `auth_services.register`) porque no monólito o usuário mora no mesmo banco.
  Aqui não existe tabela de usuários — auth é outro microserviço, outro banco,
  e `Review.user_id` é FK lógica sem constraint física (ver
  `app/models/review.py`). Um `uuid.uuid4()` solto e o nome literal
  `"Maria Silva"` (o mesmo nome do `created_user` do legacy, em
  `legacy/tests/modules/products/conftest.py:17`) servem exatamente ao mesmo
  propósito, sem criar linha nenhuma. Mesma decisão já tomada na task B8, em
  `test_cart_services_parity.py`.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ProductNotFoundError
from app.models.produto import Product
from app.schemas.review import ReviewIn
from app.services import produtos as services

# Nome do `created_user` do legacy (`legacy/tests/modules/products/
# conftest.py:17`), preservado literalmente para o teste de propagação de
# autor continuar afirmando a mesma coisa que afirmava lá.
USER_NAME = "Maria Silva"


@pytest.fixture
def user_id() -> uuid.UUID:
    """Substitui o `created_user` do legacy — ver a docstring do módulo."""
    return uuid.uuid4()


@pytest.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
    """Porte de `legacy/tests/modules/products/conftest.py::seeded_products`,
    adaptando só o import de `Product` (`app.modules.products.models` →
    `app.models.produto`). Idêntica à fixture homônima de
    `test_products_parity.py` — cada arquivo de paridade mantém a sua, como
    o legacy mantém uma por módulo."""
    products = [
        Product(
            name="Cálculo Volume 1",
            type="Livro",
            subtype="Matemática",
            description="Cálculo diferencial e integral",
            price=Decimal("129.90"),
            image_url="products/calc.png",
        ),
        Product(
            name="Física para Cientistas",
            type="Livro",
            subtype="Física",
            description="Mecânica e termodinâmica",
            price=Decimal("99.00"),
        ),
        Product(
            name="Caderno Universitário",
            type="Material",
            subtype="Papelaria",
            description="200 folhas",
            price=Decimal("24.50"),
        ),
    ]
    db_session.add_all(products)
    await db_session.commit()
    for p in products:
        await db_session.refresh(p)
    return products


class TestListProducts:
    async def test_returns_all_with_total(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        items, total = await services.listar_produtos(db_session, limit=20, offset=0)
        assert total == 3
        assert len(items) == 3

    async def test_q_filters_by_name_case_insensitive(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        """`q="física"` em minúsculas contra `"Física para Cientistas"`: só o
        `F`/`f` difere de caixa (ASCII), então este teste é vermelho com
        `like` e verde com `ilike` independentemente do collation do banco
        para acentos."""
        items, total = await services.listar_produtos(db_session, q="física", limit=20, offset=0)
        assert total == 1
        assert items[0].name == "Física para Cientistas"

    async def test_pagination_limits_and_reports_full_total(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        """`total` é a contagem do filtro inteiro, não do recorte devolvido —
        é o que o app usa para saber que existe uma próxima página."""
        items, total = await services.listar_produtos(db_session, limit=2, offset=0)
        assert len(items) == 2
        assert total == 3


class TestListCategories:
    async def test_groups_by_type_with_counts(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        rows = await services.listar_categorias(db_session)
        as_dict = dict(rows)
        assert as_dict == {"Livro": 2, "Material": 1}


class TestGetProduct:
    async def test_returns_product(
        self, db_session: AsyncSession, seeded_products: list[Product]
    ) -> None:
        target = seeded_products[0]
        product = await services.buscar_produto(db_session, target.id)
        assert product.id == target.id

    async def test_missing_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(ProductNotFoundError):
            await services.buscar_produto(db_session, uuid.uuid4())


class TestCreateReview:
    async def test_creates_and_updates_aggregates(
        self,
        db_session: AsyncSession,
        seeded_products: list[Product],
        user_id: uuid.UUID,
    ) -> None:
        product = seeded_products[0]

        await services.criar_review(
            db_session,
            product.id,
            user_id=user_id,
            author=USER_NAME,
            data=ReviewIn(rating=4, comment="Bom"),
        )
        await services.criar_review(
            db_session,
            product.id,
            user_id=user_id,
            author=USER_NAME,
            data=ReviewIn(rating=2, comment="Ok"),
        )

        refreshed = await services.buscar_produto(db_session, product.id)
        assert refreshed.rating_count == 2
        assert float(refreshed.rating_avg) == pytest.approx(3.0)

    async def test_review_carries_author_and_user(
        self,
        db_session: AsyncSession,
        seeded_products: list[Product],
        user_id: uuid.UUID,
    ) -> None:
        product = seeded_products[1]
        review = await services.criar_review(
            db_session,
            product.id,
            user_id=user_id,
            author=USER_NAME,
            data=ReviewIn(rating=5),
        )
        assert review.author == USER_NAME
        assert review.user_id == user_id
        assert review.comment == ""

    async def test_missing_product_raises(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        with pytest.raises(ProductNotFoundError):
            await services.criar_review(
                db_session,
                uuid.uuid4(),
                user_id=user_id,
                author=USER_NAME,
                data=ReviewIn(rating=5),
            )
