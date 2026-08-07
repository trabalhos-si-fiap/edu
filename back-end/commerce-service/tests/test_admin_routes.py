"""Cobertura para `/admin/inventory` — não pedida literalmente pelo brief,
mas necessária porque a task 11 adicionou `EstoqueOut` (app/schemas/estoque.py)
para fechar uma violação da regra "nenhum endpoint devolve objeto ORM cru"
encontrada em `GET /admin/estoque` / `PATCH /admin/estoque/{id}/ajustar"
(sem response_model nenhum) enquanto essas rotas já precisavam ser tocadas
para traduzir o prefixo. Ver task-11-report.md."""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.pedido import Pedido, PedidoStatusHistorico
from app.models.produto import Estoque, Fornecedor, Product
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _seed_pedido(db_session, status: str) -> Pedido:
    pedido = Pedido(
        aluno_id=str(uuid.uuid4()),
        status=status,
        endereco_entrega="Rua Teste, 123",
        valor_total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_estoque(db_session) -> Estoque:
    produto = Product(name="Caderno", price=Decimal("19.90"), type="papelaria")
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


# ── Fix round 2, reviewer finding: transicionar_pedido's own SELECT
# (app/routers/separacao.py:44) had no lock — confirmar_pagamento doesn't
# even read the pedido before delegating to it, so a double-click/retry
# could duplicate the PedidoStatusHistorico row AND the published event. ──


async def test_confirm_payment_is_idempotent_against_a_sequential_double_call(
    client, db_session, _stub_publish_event
):
    """Prova SEQUENCIAL e determinística, não uma corrida de verdade — ver
    task-11-report.md, Fix round 2, para o que continua sem prova
    automatizada (a corrida concorrente em si).

    O que isto prova: a mesma máquina de estados que o `.with_for_update()`
    protege contra corrida também rejeita um reenvio sequencial — a
    segunda chamada nunca encontra o pedido em CRIADO de novo (já está em
    AGUARDANDO_SEPARACAO), então `validar_transicao` recusa ANTES de
    qualquer `db.add(PedidoStatusHistorico(...))` ou `publish_event(...)`
    rodar uma segunda vez. Exatamente um registro de histórico e
    exatamente um evento `order.status_changed`, não dois.
    """
    pedido = await _seed_pedido(db_session, StatusPedido.CRIADO.value)

    first = await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )
    assert first.status_code == 200
    assert first.json()["status"] == StatusPedido.AGUARDANDO_SEPARACAO.value

    second = await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )
    assert second.status_code == 400

    historico_result = await db_session.execute(
        select(PedidoStatusHistorico).where(PedidoStatusHistorico.pedido_id == pedido.id)
    )
    assert len(historico_result.scalars().all()) == 1

    status_changed_events = [
        payload
        for routing_key, payload in _stub_publish_event
        if routing_key == "order.status_changed"
    ]
    assert len(status_changed_events) == 1
    assert status_changed_events[0]["pedido_id"] == pedido.id


# ── B7: o cap declarado nao provava que o `.limit()`/`.offset()` da query
# roda. Os testes de cap acima so exercitam a validacao do `Query(le=200)`
# — apagar `.limit(limit).offset(offset)` do `select()` os deixa verdes.
# Estes dois semeiam mais linhas que o limite pedido e conferem a
# contagem exata, seguindo o padrao ja usado em learning-service
# `test_reviews_today_listing_has_a_default_cap_and_offset`. ────────────


async def test_orders_listing_actually_applies_limit_and_offset(client, db_session):
    total = 55
    for i in range(total):
        db_session.add(
            Pedido(
                aluno_id=str(uuid.uuid4()),
                status=StatusPedido.CRIADO.value,
                endereco_entrega=f"Rua Teste, {i}",
                valor_total=Decimal("100.00"),
            )
        )
    await db_session.commit()

    first_page = await client.get("/admin/orders?limit=10", headers=headers_for("admin"))
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10

    last_page = await client.get("/admin/orders?limit=10&offset=50", headers=headers_for("admin"))
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50

    ids_first = {row["id"] for row in first_body}
    ids_last = {row["id"] for row in last_body}
    assert ids_first.isdisjoint(ids_last)


async def test_inventory_adjust_rejects_a_negative_quantity(client, db_session):
    estoque = await _seed_estoque(db_session)
    quantidade_inicial = estoque.quantidade

    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=-50",
        headers=headers_for("admin"),
    )

    assert response.status_code == 422
    await db_session.refresh(estoque)
    assert estoque.quantidade == quantidade_inicial


async def test_inventory_adjust_accepts_zero(client, db_session):
    """Zero é um ajuste legítimo — "acabou o estoque" não é o mesmo que
    "valor inválido". O piso é 0, não 1."""
    estoque = await _seed_estoque(db_session)
    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=0",
        headers=headers_for("admin"),
    )
    assert response.status_code == 200
    assert response.json()["quantidade"] == 0


async def test_inventory_listing_actually_applies_limit_and_offset(client, db_session):
    fornecedor = Fornecedor(nome="Distribuidora X")
    db_session.add(fornecedor)
    await db_session.flush()

    total = 55
    for i in range(total):
        produto = Product(name=f"Caderno {i}", price=Decimal("19.90"), type="papelaria")
        db_session.add(produto)
        await db_session.flush()
        db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor.id, quantidade=i))
    await db_session.commit()

    first_page = await client.get("/admin/inventory?limit=10", headers=headers_for("admin"))
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10

    last_page = await client.get(
        "/admin/inventory?limit=10&offset=50", headers=headers_for("admin")
    )
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50

    ids_first = {row["id"] for row in first_body}
    ids_last = {row["id"] for row in last_body}
    assert ids_first.isdisjoint(ids_last)
