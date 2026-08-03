import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Pedido
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_picking_queue_requires_authentication(client):
    assert (await client.get("/picking/queue")).status_code == 403


async def test_picking_queue_forbids_students(client):
    assert (await client.get("/picking/queue", headers=headers_for("student"))).status_code == 403


async def test_picking_queue_allows_separador(client):
    assert (await client.get("/picking/queue", headers=headers_for("separador"))).status_code == 200


async def test_old_portuguese_picking_path_is_gone(client):
    response = await client.get("/separacao/fila", headers=headers_for("separador"))
    assert response.status_code == 404


async def test_picking_queue_rejects_limit_above_the_cap(client):
    response = await client.get("/picking/queue?limit=5000", headers=headers_for("separador"))
    assert response.status_code == 422


# ── Gap de autorização #3: finalizar_separacao/finish não checava posse ──

PICKER_A = "00000000-0000-0000-0000-0000000000a1"
PICKER_B = "00000000-0000-0000-0000-0000000000b2"


async def _seed_pedido_em_separacao(db_session, separador_id: str | None) -> Pedido:
    pedido = Pedido(
        aluno_id=str(uuid.uuid4()),
        status=StatusPedido.EM_SEPARACAO.value,
        endereco_entrega="Rua Teste, 123",
        valor_total=Decimal("100.00"),
        separador_id=separador_id,
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_finish_picking_forbids_a_separador_who_never_claimed_the_order(client, db_session):
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_B)
    )
    assert response.status_code == 403


async def test_finish_picking_allows_the_separador_who_claimed_the_order(client, db_session):
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 200
    assert response.json()["status"] == StatusPedido.AGUARDANDO_COLETA.value


async def test_old_portuguese_finalizar_path_is_gone(client):
    response = await client.patch(
        "/separacao/1/finalizar", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 404
