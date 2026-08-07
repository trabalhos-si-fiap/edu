"""Testes de `/products`.

DESVIO do rascunho do brief (task-11-brief.md): o brief testa `/products`
sem cabeçalho de autenticação e espera 200 — mas o gap de autorização #1 do
sweep de segurança (superseding list da task) exige exatamente o oposto:
"GET /produtos — no Depends at all, completely unauthenticated. Confirmed."
CLAUDE.md, regra inviolável #2, reforça: "Nenhuma rota pode existir sem
Depends(get_current_user) ou equivalente." Constraint vence o brief — todo
teste de listagem abaixo agora manda um token válido, e ganhamos um teste
novo (`test_products_listing_requires_authentication`) provando que a
ausência de token é rejeitada.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import insert

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Product
from app.services.substituicao_ia import sugerir_substitutos


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _seed_products(db_session, quantity: int) -> None:
    await db_session.execute(
        insert(Product),
        [
            {
                "name": f"Livro {i}",
                "description": f"Descrição {i}",
                "price": 49.90,
                "type": "livros",
                "image_url": "",
            }
            for i in range(quantity)
        ],
    )
    await db_session.commit()


async def test_products_are_listed_in_english_path(client):
    response = await client.get("/products", headers=headers_for("student"))
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_products_listing_requires_authentication(client):
    """Gap de autorização #1 — prova que a ausência de token é rejeitada."""
    assert (await client.get("/products")).status_code == 403


async def test_old_portuguese_path_is_gone(client):
    assert (await client.get("/produtos")).status_code == 404


async def test_products_listing_is_paginated(client, db_session):
    await _seed_products(db_session, 5)
    response = await client.get("/products?limit=2", headers=headers_for("student"))
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_products_listing_rejects_limit_above_the_cap(client):
    response = await client.get("/products?limit=5000", headers=headers_for("student"))
    assert response.status_code == 422


async def test_products_listing_has_a_default_limit(client, db_session):
    await _seed_products(db_session, 120)
    response = await client.get("/products", headers=headers_for("student"))
    assert len(response.json()) <= 100


async def test_product_response_exposes_only_declared_fields(client, db_session):
    await _seed_products(db_session, 1)
    response = await client.get("/products", headers=headers_for("student"))
    product = response.json()[0]
    assert set(product) == {"id", "name", "description", "price", "type", "image_url"}


async def test_products_can_be_filtered_by_category(client, db_session):
    await _seed_products(db_session, 2)
    response = await client.get("/products?category=livros", headers=headers_for("student"))
    assert response.status_code == 200
    assert all(p["type"] == "livros" for p in response.json())


async def test_unknown_category_returns_empty_list(client, db_session):
    await _seed_products(db_session, 2)
    response = await client.get("/products?category=inexistente", headers=headers_for("student"))
    assert response.json() == []


async def test_product_id_is_a_uuid_string_in_the_response(client, db_session):
    """O Flutter faz `as String` sobre `id`. Inteiro levanta TypeError que o
    tratamento de erro do app não captura — a tela quebra sem virar mensagem."""
    produto = Product(name="Guia", price=Decimal("49.90"), type="apostila")
    db_session.add(produto)
    await db_session.commit()

    response = await client.get("/products", headers=headers_for("student"))

    assert response.status_code == 200
    item = response.json()[0]
    assert isinstance(item["id"], str)
    uuid.UUID(item["id"])  # levanta se não for um UUID


async def test_suggested_products_are_stored_as_uuid_strings(db_session):
    """`ocorrencias.produtos_sugeridos` é JSONB. JSON não tem tipo UUID, então
    a lista guarda strings — e `substituicao_ia` tem que produzi-las assim.

    DESVIO do rascunho do Step 2 do brief: ele só cria `alvo` e `similar`,
    sem `Estoque`. `sugerir_substitutos` filtra candidatos por
    `Estoque.quantidade > 0` (join); sem nenhum `Estoque`, `candidatos` fica
    vazio e a função retorna `[]` no early-return (produto.py:65-66,
    substituicao_ia.py). `all(isinstance(s, str) for s in [])` é True por
    vácuo — o teste passaria mesmo se `sugerir_substitutos` nunca devolvesse
    uma string. Por isso crio um `Fornecedor` e um `Estoque` com
    `quantidade > 0` para `similar`, e asserto que a lista não é vazia antes
    de checar o tipo dos elementos."""
    alvo = Product(name="Guia", price=Decimal("49.90"), type="apostila")
    similar = Product(name="Guia Avançado", price=Decimal("59.90"), type="apostila")
    db_session.add_all([alvo, similar])
    await db_session.flush()

    fornecedor = Fornecedor(nome="Distribuidora Y")
    db_session.add(fornecedor)
    await db_session.flush()

    db_session.add(Estoque(produto_id=similar.id, fornecedor_id=fornecedor.id, quantidade=5))
    await db_session.commit()

    sugeridos = await sugerir_substitutos(db_session, alvo.id)

    assert sugeridos  # não pode passar por vácuo
    assert all(isinstance(s, str) for s in sugeridos)
    for s in sugeridos:
        uuid.UUID(s)
