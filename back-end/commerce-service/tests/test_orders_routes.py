import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Pedido
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
# /orders/mine, ownership por aluno_id já preexistente) ──────────────────


async def _seed_pedido(db_session, aluno_id: str) -> Pedido:
    pedido = Pedido(
        aluno_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        endereco_entrega="Rua Teste, 123",
        valor_total=Decimal("100.00"),
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
    ids = {row["aluno_id"] for row in response.json()}
    assert ids == {mine}
