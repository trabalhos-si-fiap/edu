"""`GET /products?partner_id=` — o catálogo de um parceiro.

Produto pertence ao parceiro ATRAVÉS do estoque (`Estoque.fornecedor_id`),
não por chave direta em `products`. Não há coluna nova em `products`; o
filtro é um join.

Parceiro inativo devolve LISTA VAZIA, não 404: um parceiro desativado
enquanto o aluno navega não pode virar tela de erro.
"""

from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Product


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed(db_session, *, parceiro: str, produto: str, ativo: bool = True) -> Fornecedor:
    fornecedor = (
        await db_session.execute(
            __import__("sqlalchemy").select(Fornecedor).where(Fornecedor.nome == parceiro)
        )
    ).scalar_one_or_none()
    if fornecedor is None:
        fornecedor = Fornecedor(nome=parceiro, ativo=ativo, origem_rotulo="São Paulo, SP")
        db_session.add(fornecedor)
        await db_session.commit()
        await db_session.refresh(fornecedor)

    p = Product(name=produto, type="mobiliario", price=Decimal("10.00"), sku=produto[:60])
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    db_session.add(Estoque(produto_id=p.id, fornecedor_id=fornecedor.id, quantidade=5))
    await db_session.commit()
    return fornecedor


async def test_without_the_filter_the_catalog_is_whole(client, db_session):
    edu = await _seed(db_session, parceiro="Edu", produto="Apostila")
    await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária")
    response = await client.get("/products", headers=headers_for("student"))
    assert response.json()["total"] == 2
    assert edu.id


async def test_the_filter_returns_only_that_partner_catalog(client, db_session):
    edu = await _seed(db_session, parceiro="Edu", produto="Apostila")
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária")

    do_edu = await client.get(f"/products?partner_id={edu.id}", headers=headers_for("student"))
    do_leroy = await client.get(f"/products?partner_id={leroy.id}", headers=headers_for("student"))

    assert [p["name"] for p in do_edu.json()["items"]] == ["Apostila"]
    assert do_edu.json()["total"] == 1
    assert [p["name"] for p in do_leroy.json()["items"]] == ["Luminária"]


async def test_a_disabled_partner_yields_an_empty_list_not_a_404(client, db_session):
    """Regra explícita da spec: "Parceiro inativo em GET /products?partner_id=:
    lista vazia, não 404". Desativar no painel esvazia a seção sem quebrar a
    navegação de quem já estava com a tela aberta."""
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária", ativo=False)
    response = await client.get(f"/products?partner_id={leroy.id}", headers=headers_for("student"))
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_an_unknown_partner_also_yields_an_empty_list(client):
    response = await client.get("/products?partner_id=999999", headers=headers_for("student"))
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_the_filter_composes_with_the_search_and_the_pagination(client, db_session):
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária de mesa")
    await _seed(db_session, parceiro="Leroy Merlin", produto="Cadeira ergonômica")

    combinado = await client.get(
        f"/products?partner_id={leroy.id}&q=lumin&limit=1", headers=headers_for("student")
    )
    assert combinado.json()["total"] == 1
    assert combinado.json()["items"][0]["name"] == "Luminária de mesa"


async def test_a_product_with_no_stock_row_never_shows_under_any_partner(client, db_session):
    """Um produto sem estoque não pertence a parceiro nenhum — e é por isso
    que a spec exige que todo produto nasça com estoque (task 6). Este teste
    documenta a consequência de quebrar essa invariante."""
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária")
    orfao = Product(name="Órfão", type="apostila", price=Decimal("1.00"), sku="ORFAO-1")
    db_session.add(orfao)
    await db_session.commit()

    do_leroy = await client.get(f"/products?partner_id={leroy.id}", headers=headers_for("student"))
    assert [p["name"] for p in do_leroy.json()["items"]] == ["Luminária"]

    todos = await client.get("/products", headers=headers_for("student"))
    assert todos.json()["total"] == 2


async def test_a_product_stocked_by_two_suppliers_still_appears_once_under_either(
    client, db_session
):
    """`Estoque`'s unique constraint (`uq_produto_fornecedor`) is on the PAIR
    (produto_id, fornecedor_id), not on produto_id alone — a product can have
    a stock row with more than one supplier. A naive `join(Estoque)` would
    return the same product once per matching stock row, inflating both the
    `items` list and `total` for the very partner being filtered on, and
    silently duplicating rows across pages of a paginated result."""
    leroy = await _seed(db_session, parceiro="Leroy Merlin", produto="Luminária compartilhada")
    edu = (
        await db_session.execute(
            __import__("sqlalchemy").select(Fornecedor).where(Fornecedor.nome == "Edu")
        )
    ).scalar_one_or_none()
    if edu is None:
        edu = Fornecedor(nome="Edu", ativo=True, origem_rotulo="São Paulo, SP")
        db_session.add(edu)
        await db_session.commit()
        await db_session.refresh(edu)

    produto = (
        await db_session.execute(
            __import__("sqlalchemy")
            .select(Product)
            .where(Product.name == "Luminária compartilhada")
        )
    ).scalar_one()
    # Second supplier for the SAME product — the pair (produto_id,
    # fornecedor_id) differs from the row `_seed` already created, so the
    # unique constraint allows it.
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=edu.id, quantidade=3))
    await db_session.commit()

    response = await client.get(f"/products?partner_id={leroy.id}", headers=headers_for("student"))
    body = response.json()
    assert [p["name"] for p in body["items"]] == ["Luminária compartilhada"]
    assert body["total"] == 1


async def test_partner_id_out_of_int32_range_is_422_not_500(client):
    """`Estoque.fornecedor_id`/`Fornecedor.id` são `Integer` (int32). Sem
    teto no schema, um `partner_id` fora da faixa (ex.: 3 bilhões) passaria
    da validação do Pydantic direto para o `WHERE ... = :partner_id` do join
    e estouraria `asyncpg.exceptions.DataError` não tratado (500) — a mesma
    classe de bug que a task 3 corrigiu em `AjusteEstoqueIn.delta`."""
    response = await client.get("/products?partner_id=3000000000", headers=headers_for("student"))
    assert response.status_code == 422
