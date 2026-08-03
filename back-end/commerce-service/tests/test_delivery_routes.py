import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Pedido
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


DELIVERER_A = "00000000-0000-0000-0000-0000000000d1"
DELIVERER_B = "00000000-0000-0000-0000-0000000000d2"


async def _seed_pedido(db_session, status: str, entregador_id: str | None = None) -> Pedido:
    pedido = Pedido(
        aluno_id=str(uuid.uuid4()),
        status=status,
        endereco_entrega="Rua Teste, 123",
        valor_total=Decimal("100.00"),
        entregador_id=entregador_id,
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_delivery_queue_requires_authentication(client):
    assert (await client.get("/delivery/queue")).status_code == 403


async def test_delivery_mine_requires_authentication(client):
    assert (await client.get("/delivery/mine")).status_code == 403


async def test_delivery_queue_rejects_limit_above_the_cap(client):
    response = await client.get("/delivery/queue?limit=5000", headers=headers_for("entregador"))
    assert response.status_code == 422


async def test_old_portuguese_delivery_queue_path_is_gone(client):
    response = await client.get("/entrega/fila", headers=headers_for("entregador"))
    assert response.status_code == 404


async def test_old_portuguese_confirmar_coleta_path_is_gone(client):
    response = await client.patch("/entrega/1/confirmar-coleta", headers=headers_for("entregador"))
    assert response.status_code == 404


async def test_old_portuguese_confirmar_entrega_path_is_gone(client):
    response = await client.patch("/entrega/1/confirmar-entrega", headers=headers_for("entregador"))
    assert response.status_code == 404


async def test_collect_claims_the_order_for_the_caller(client, db_session):
    """`collect` é claim-on-first-action de propósito (ver docstring em
    entrega.py) — não é um dos 5 gaps, mas prova que a rota ainda funciona
    depois da tradução do path."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200
    assert response.json()["entregador_id"] == DELIVERER_A


# ── Gap de autorização #2: confirmar_entrega/deliver não checava posse ──


async def test_deliver_forbids_a_deliverer_who_never_collected_the_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/deliver", headers=headers_for("entregador", sub=DELIVERER_B)
    )
    assert response.status_code == 403


async def test_deliver_allows_the_deliverer_who_collected_the_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/deliver", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200
    assert response.json()["status"] == StatusPedido.ENTREGUE.value
