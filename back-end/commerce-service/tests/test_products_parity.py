"""Testes de paridade de `/products`, `/products/categories` e
`/products/{id}` — porte de `legacy/tests/modules/products/test_routes.py`
(task B6 do bloco B). Ver `task-B6-report.md` para a lista completa de
asserções adaptadas e de testes removidos.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.produto import Product
from app.services.auth_client import AuthServiceUnavailableError


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_products(db_session) -> list[Product]:
    """Porte de `legacy/tests/modules/products/conftest.py::seeded_products`,
    adaptando só o import de `Product` (`app.modules.products.models` →
    `app.models.produto`)."""
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


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/products")
        # 403, não 401: ver a divergência registrada na task B0 do plano do bloco B.
        # O `edu-common` responde 403 para header ausente e 401 para token
        # inválido/expirado; o legacy responde 401 nos dois.
        assert r.status_code == 403

    async def test_create_review_requires_auth(self, client: AsyncClient) -> None:
        # Portado de volta pela B7 (CONTEXTO DO CONTROLADOR do task-B7-brief.md):
        # a B6 removeu este teste porque `POST /products/{id}/reviews` ainda
        # não existia (404 medido, não 401/403) — um dos dois casos "products"
        # do N=5 que a task B0 mediu. Sem ele, um POST de review sem token
        # não tinha nenhum teste travando 403.
        r = await client.post(f"/products/{uuid.uuid4()}/reviews", json={"rating": 5})
        # 403, não 401: mesma divergência edu-common vs legacy de
        # test_list_requires_auth acima.
        assert r.status_code == 403


class TestListProducts:
    async def test_returns_items_and_pagination_envelope(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 3
        assert body["limit"] == 20
        assert body["offset"] == 0
        assert len(body["items"]) == 3

    async def test_price_serialized_as_string(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products?q=Cálculo", headers=headers_for("student"))
        item = r.json()["items"][0]
        assert item["price"] == "129.90"
        assert isinstance(item["price"], str)

    async def test_limit_over_max_returns_422(self, client: AsyncClient) -> None:
        r = await client.get("/products?limit=500", headers=headers_for("student"))
        assert r.status_code == 422


class TestCategories:
    async def test_lists_categories(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products/categories", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        items = {c["type"]: c["count"] for c in r.json()["items"]}
        assert items == {"Livro": 2, "Material": 1}


class TestProductDetail:
    async def test_returns_product(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        target = seeded_products[0]
        r = await client.get(f"/products/{target.id}", headers=headers_for("student"))
        assert r.status_code == 200
        assert r.json()["name"] == target.name

    async def test_unknown_returns_404(self, client: AsyncClient) -> None:
        r = await client.get(f"/products/{uuid.uuid4()}", headers=headers_for("student"))
        assert r.status_code == 404


class TestImagePresign:
    async def test_image_url_is_presigned_when_key_present(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products?q=Cálculo", headers=headers_for("student"))
        item = r.json()["items"][0]
        assert "X-Amz-Signature" in item["image_url"] or "X-Amz-Credential" in item["image_url"]

    async def test_image_url_empty_when_no_key(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        r = await client.get("/products?q=Física", headers=headers_for("student"))
        assert r.json()["items"][0]["image_url"] == ""


class TestReviews:
    """Porte de `legacy/tests/modules/products/test_routes.py::TestReviews`
    (task B7). Adaptações: sem `/api`, `headers_for("student")`, e o nome do
    autor sai de `GET /auth/me` (monkeypatch de `app.routers.produtos.get_me`,
    Constraint 14 do task-B7-brief.md) em vez de vir do usuário no banco —
    aqui não há usuário no banco do commerce."""

    @staticmethod
    def _stub_get_me(monkeypatch: pytest.MonkeyPatch, name: str = "Maria Silva") -> None:
        async def _me_falsa(raw_token: str) -> dict:
            return {"id": str(uuid.uuid4()), "name": name, "email": "m@s.com", "role": "student"}

        monkeypatch.setattr("app.routers.produtos.get_me", _me_falsa)

    async def test_create_then_list_reflects_aggregate(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._stub_get_me(monkeypatch)
        product = seeded_products[0]

        r = await client.post(
            f"/products/{product.id}/reviews",
            json={"rating": 5, "comment": "Excelente"},
            headers=headers_for("student"),
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["author"] == "Maria Silva"
        assert created["rating"] == 5

        r = await client.get(f"/products/{product.id}/reviews", headers=headers_for("student"))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["rating_count"] == 1
        assert body["rating_avg"] == 5.0
        assert body["items"][0]["comment"] == "Excelente"

    async def test_invalid_rating_returns_422(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
    ) -> None:
        # Body inválido é rejeitado pelo FastAPI antes do endpoint rodar
        # (validação de `payload: ReviewIn` acontece antes da função ser
        # chamada) — `get_me` nunca é chamado aqui, sem necessidade de stub.
        product = seeded_products[0]
        r = await client.post(
            f"/products/{product.id}/reviews",
            json={"rating": 9},
            headers=headers_for("student"),
        )
        assert r.status_code == 422

    async def test_reviews_for_unknown_product_returns_404(self, client: AsyncClient) -> None:
        r = await client.get(f"/products/{uuid.uuid4()}/reviews", headers=headers_for("student"))
        assert r.status_code == 404

    async def test_review_author_comes_from_the_auth_service(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O JWT não carrega `name` — pôr o nome no token o colocaria em todo
        header Authorization, que vai para log de acesso."""
        produto = Product(name="Guia", type="apostila", price=Decimal("49.90"))
        db_session.add(produto)
        await db_session.commit()

        async def _me_falso(raw_token: str) -> dict:
            return {
                "id": str(uuid.uuid4()),
                "name": "Ana Souza",
                "email": "a@b.c",
                "role": "student",
            }

        monkeypatch.setattr("app.routers.produtos.get_me", _me_falso)

        response = await client.post(
            f"/products/{produto.id}/reviews",
            json={"rating": 5, "comment": "Excelente"},
            headers=headers_for("student"),
        )

        assert response.status_code == 201
        assert response.json()["author"] == "Ana Souza"

    async def test_review_returns_503_when_auth_is_unreachable(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        produto = Product(name="Guia", type="apostila", price=Decimal("49.90"))
        db_session.add(produto)
        await db_session.commit()

        async def _me_que_falha(raw_token: str) -> dict:
            raise AuthServiceUnavailableError()

        monkeypatch.setattr("app.routers.produtos.get_me", _me_que_falha)

        response = await client.post(
            f"/products/{produto.id}/reviews",
            json={"rating": 5},
            headers=headers_for("student"),
        )
        assert response.status_code == 503

    async def test_rating_avg_matches_legacy_arithmetic_after_three_reviews(
        self,
        client: AsyncClient,
        seeded_products: list[Product],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Trava a aritmética de `criar_review`
        (`app/services/produtos.py`) contra
        `legacy/app/modules/products/services.py::create_review` (medido
        idêntico linha a linha: `new_avg = (float(rating_avg) * rating_count
        + rating) / new_count`, depois `round(new_avg, 2)`, na mesma ordem).

        Três notas DIFERENTES (4, 2, 5), não uma média redonda: o terceiro
        passo dá 11/3 = 3.6666...→3.67, o único jeito de expor um
        arredondamento ou uma ordem de operações errados — uma média inteira
        passaria tanto com a fórmula certa quanto com uma trocada."""
        self._stub_get_me(monkeypatch)
        product = seeded_products[0]

        for rating in (4, 2, 5):
            r = await client.post(
                f"/products/{product.id}/reviews",
                json={"rating": rating},
                headers=headers_for("student"),
            )
            assert r.status_code == 201, r.text

        r = await client.get(f"/products/{product.id}/reviews", headers=headers_for("student"))
        body = r.json()
        assert body["rating_count"] == 3
        assert body["rating_avg"] == 3.67


class TestReviewConcurrency:
    """Prova o `.with_for_update()` de `criar_review` (Step 9 do
    task-B7-brief.md; regra 3 do CLAUDE.md do repositório: read->write em
    recurso compartilhado tem que ser atômico).

    O legado não tem teste de concorrência para reviews — medido com
    `grep -rn concurrent legacy/tests/modules/products/`, sem resultado —
    este teste é novo, escrito para esta task."""

    async def test_concurrent_reviews_do_not_lose_a_rating_increment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Duas reviews SIMULTÂNEAS no mesmo produto não podem perder um
        incremento de `rating_count`.

        Tentativa anterior (descartada, ver task-B7-report.md): sinal em
        `get_me` stubado + espera em `AsyncSession.add`. MEDIDO com prints
        instrumentados que essa versão não força nada — a segunda requisição
        só chegava ao seu próprio SELECT depois que a primeira já tinha
        commitado por inteiro (a primeira roda de ponta a ponta sem ceder o
        loop entre `db.add` e `await db.commit()`, e devolver do `get_me`
        remendado da segunda até o `db.execute` dela custa hops de mais).

        Versão que funciona (medida): remenda `AsyncSession.execute` e
        `AsyncSession.commit` na CLASSE (cada requisição usa sua própria
        `AsyncSession` — ver a fixture `client` em conftest.py, que abre uma
        sessão nova por `get_db()`).

        * O SINAL sai de `execute`: dispara quando a SEGUNDA chamada a
          `db.execute` é DISPARADA (antes do `await` real resolver) —
          garantido pela ordem sequencial dentro de cada `criar_review`
          (SELECT sempre vem antes do commit), então nenhuma das duas
          requisições alcança seu commit antes de as duas terem ao menos
          disparado o próprio SELECT.
        * A ESPERA fica em `commit`: o PRIMEIRO commit a ser chamado espera
          o sinal acima antes de seguir para o commit de verdade — reforça a
          garantia estrutural com um `wait_for` explícito, e não trava com o
          lock: sob `.with_for_update()`, o commit da primeira nunca depende
          de a segunda ter TERMINADO seu SELECT, só de ela ter DISPARADO —
          e ela dispara ainda que vá bloquear no servidor.

        SEM lock: as duas SELECTs (sem `FOR UPDATE`) disparam antes de
        qualquer commit, então as duas leem `rating_count=0` sob READ
        COMMITTED (nenhuma commitou ainda). As duas calculam `new_count=1`;
        a que commitar por último sobrescreve a outra: `rating_count` fica
        1, não 2.

        COM lock: o SELECT ... FOR UPDATE da segunda dispara, mas bloqueia
        no próprio Postgres até a primeira commitar — commit que não
        depende de a segunda ter terminado, só de ter disparado, então sem
        deadlock — e só então lê `rating_count=1` e calcula 2 corretamente.

        Limitação declarada (mesma do bloco A): isto prova a ORDEM LÓGICA
        das operações e exercita um lock de linha real do Postgres entre
        duas conexões distintas (duas `AsyncSession`, duas conexões do pool
        asyncpg) — mas continua sendo um único processo/event loop. Não
        reproduz contenção entre processos ou réplicas distintas do
        serviço.
        """
        produto = Product(name="Guia Concorrente", type="apostila", price=Decimal("49.90"))
        db_session.add(produto)
        await db_session.commit()

        async def _me_falsa(raw_token: str) -> dict:
            return {
                "id": str(uuid.uuid4()),
                "name": "Concorrente",
                "email": "c@c.c",
                "role": "student",
            }

        monkeypatch.setattr("app.routers.produtos.get_me", _me_falsa)

        segunda_select_disparada = asyncio.Event()
        estado = {"selects": 0, "commits": 0}

        execute_real = AsyncSession.execute
        commit_real = AsyncSession.commit

        async def _execute_que_avisa(self: AsyncSession, *args: object, **kwargs: object):
            estado["selects"] += 1
            if estado["selects"] == 2:
                segunda_select_disparada.set()
            return await execute_real(self, *args, **kwargs)

        async def _commit_que_espera(self: AsyncSession, *args: object, **kwargs: object):
            estado["commits"] += 1
            if estado["commits"] == 1:
                # `wait_for`, não `wait`: se o ponto de encontro deixar de
                # ser alcançável, o teste falha alto em vez de pendurar a
                # suíte.
                await asyncio.wait_for(segunda_select_disparada.wait(), timeout=5)
                # Margem medida, pragmática (não puramente lógica — registrada
                # como tal no relatório): o sinal acima garante a ORDEM DE
                # DISPARO (Python já CHAMOU `db.execute` da segunda antes
                # deste commit prosseguir), mas não garante que o pacote da
                # segunda já CHEGOU ao Postgres — isso é rede/SO, fora do
                # controle do event loop. Medido: sem nenhuma margem, 5
                # vermelhos em 7 execuções (~71%); com `sleep(0)` (só cede o
                # loop, sem tempo de parede), 1 vermelho em 2; com este
                # `sleep(0.01)`, 10 vermelhos em 10 execuções consecutivas.
                await asyncio.sleep(0.01)
            return await commit_real(self, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "execute", _execute_que_avisa)
        monkeypatch.setattr(AsyncSession, "commit", _commit_que_espera)

        body = {"rating": 5, "comment": "Bom"}
        r1, r2 = await asyncio.gather(
            client.post(
                f"/products/{produto.id}/reviews", json=body, headers=headers_for("student")
            ),
            client.post(
                f"/products/{produto.id}/reviews", json=body, headers=headers_for("student")
            ),
        )
        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text

        await db_session.refresh(produto)
        assert produto.rating_count == 2, (
            f"perdeu um incremento: rating_count={produto.rating_count} "
            "(as duas leram 0 e gravaram 1)"
        )
