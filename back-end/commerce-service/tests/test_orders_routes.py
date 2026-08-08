import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Order
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_create_order_requires_authentication(client):
    response = await client.post("/orders", json={"itens": [], "endereco_entrega": "Rua X"})
    assert response.status_code == 403


async def test_my_orders_requires_authentication(client):
    assert (await client.get("/orders/mine")).status_code == 403


async def test_order_detail_requires_authentication(client):
    assert (await client.get("/orders/1")).status_code == 403


async def test_order_tracking_requires_authentication(client):
    assert (await client.get("/orders/1/tracking")).status_code == 403


async def test_delivery_estimate_requires_authentication(client):
    assert (await client.get("/orders/1/delivery-estimate")).status_code == 403


async def test_old_portuguese_order_path_is_gone(client):
    assert (await client.get("/pedidos/meus")).status_code == 404


# ── Cobertura adicional — não pedida literalmente pelo brief, mas exigida
# pelo comportamento que a task 11 introduz nestas rotas (paginação em
# /orders/mine, ownership por user_id já preexistente) ──────────────────


async def _seed_pedido(db_session, aluno_id: str) -> Order:
    pedido = Order(
        user_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        endereco_entrega="Rua Teste, 123",
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_my_orders_listing_is_paginated(client, db_session):
    aluno_id = str(uuid.uuid4())
    for _ in range(5):
        await _seed_pedido(db_session, aluno_id)

    response = await client.get("/orders/mine?limit=2", headers=headers_for("student", aluno_id))
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_my_orders_listing_rejects_limit_above_the_cap(client):
    response = await client.get("/orders/mine?limit=5000", headers=headers_for("student"))
    assert response.status_code == 422


async def test_my_orders_only_returns_orders_owned_by_the_caller(client, db_session):
    mine = str(uuid.uuid4())
    someone_elses = str(uuid.uuid4())
    await _seed_pedido(db_session, mine)
    await _seed_pedido(db_session, someone_elses)

    response = await client.get("/orders/mine", headers=headers_for("student", mine))
    assert response.status_code == 200
    ids = {row["user_id"] for row in response.json()}
    assert ids == {mine}


async def test_my_orders_response_does_not_leak_staff_assignee_ids(client, db_session):
    """Fix round 1 (reviewer finding, MINOR #4): `picker_id`/
    `deliverer_id` (`separador_id`/`entregador_id` antes da task C2) são
    identificadores operacionais internos — quem está
    separando/entregando o pedido não é assunto do aluno. Mesma classe do
    vazamento de `descricao_ia` fechado no learning-service. `PedidoOut`
    (contrato do aluno) não deve incluí-los; `PedidoStaffOut`
    (picking/delivery/admin) é quem os expõe."""
    aluno_id = str(uuid.uuid4())
    await _seed_pedido(db_session, aluno_id)

    response = await client.get("/orders/mine", headers=headers_for("student", aluno_id))
    assert response.status_code == 200
    order = response.json()[0]
    assert set(order) == {
        "id",
        "user_id",
        "status",
        "endereco_entrega",
        "total",
        "carrier_name",
        "estimated_delivery_at",
        "created_at",
    }
    assert "picker_id" not in order
    assert "deliverer_id" not in order


# ── B7: nada provava que o `.limit(limit).offset(offset)` de
# `rastreio_pedido` (app/routers/pedidos.py) roda — apagar a clausula
# deixava a suite verde. `PedidoStatusHistoricoOut` nao expoe `id`, entao
# a fronteira entre paginas e conferida por `observacao`, que vai unica
# por linha. `criado_em` vai explicito e crescente porque a rota ordena
# por `criado_em.asc()`: com o `server_default=func.now()` as 55 linhas
# empatariam no mesmo timestamp e a paginacao ficaria nao-deterministica.


async def test_order_tracking_actually_applies_limit_and_offset(client, db_session):
    from datetime import UTC, datetime, timedelta

    from app.models.pedido import PedidoStatusHistorico

    aluno_id = str(uuid.uuid4())
    pedido = Order(
        user_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        endereco_entrega="Rua Teste, 123",
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    total = 55
    for i in range(total):
        db_session.add(
            PedidoStatusHistorico(
                order_id=pedido.id,
                status=StatusPedido.CRIADO.value,
                observacao=f"evento-{i}",
                criado_em=base + timedelta(minutes=i),
            )
        )
    await db_session.commit()

    headers = headers_for("student", aluno_id)

    first_page = await client.get(f"/orders/{pedido.id}/tracking?limit=10", headers=headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10
    assert first_body[0]["observacao"] == "evento-0"

    last_page = await client.get(
        f"/orders/{pedido.id}/tracking?limit=10&offset=50", headers=headers
    )
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50
    assert last_body[0]["observacao"] == "evento-50"

    marcas_first = {row["observacao"] for row in first_body}
    marcas_last = {row["observacao"] for row in last_body}
    assert marcas_first.isdisjoint(marcas_last)
