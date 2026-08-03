"""Cobertura para `/admin/inventory` — não pedida literalmente pelo brief,
mas necessária porque a task 11 adicionou `EstoqueOut` (app/schemas/estoque.py)
para fechar uma violação da regra "nenhum endpoint devolve objeto ORM cru"
encontrada em `GET /admin/estoque` / `PATCH /admin/estoque/{id}/ajustar"
(sem response_model nenhum) enquanto essas rotas já precisavam ser tocadas
para traduzir o prefixo. Ver task-11-report.md."""

from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Produto


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _seed_estoque(db_session) -> Estoque:
    produto = Produto(nome="Caderno", preco=Decimal("19.90"), categoria="papelaria")
    fornecedor = Fornecedor(nome="Distribuidora X")
    db_session.add_all([produto, fornecedor])
    await db_session.flush()

    estoque = Estoque(produto_id=produto.id, fornecedor_id=fornecedor.id, quantidade=10)
    db_session.add(estoque)
    await db_session.commit()
    await db_session.refresh(estoque)
    return estoque


async def test_old_portuguese_estoque_path_is_gone(client):
    response = await client.get("/admin/estoque", headers=headers_for("admin"))
    assert response.status_code == 404


async def test_inventory_listing_requires_admin_role(client):
    response = await client.get("/admin/inventory", headers=headers_for("separador"))
    assert response.status_code == 403


async def test_inventory_listing_rejects_limit_above_the_cap(client):
    response = await client.get("/admin/inventory?limit=5000", headers=headers_for("admin"))
    assert response.status_code == 422


async def test_inventory_response_exposes_only_declared_fields(client, db_session):
    await _seed_estoque(db_session)
    response = await client.get("/admin/inventory", headers=headers_for("admin"))
    assert response.status_code == 200
    row = response.json()[0]
    assert set(row) == {"id", "produto_id", "fornecedor_id", "quantidade", "atualizado_em"}


async def test_orders_listing_is_paginated(client):
    response = await client.get("/admin/orders?limit=5000", headers=headers_for("admin"))
    assert response.status_code == 422
