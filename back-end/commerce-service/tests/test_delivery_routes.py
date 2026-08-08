import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Order
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


DELIVERER_A = "00000000-0000-0000-0000-0000000000d1"
DELIVERER_B = "00000000-0000-0000-0000-0000000000d2"
ADMIN = "00000000-0000-0000-0000-0000000000d9"


async def _seed_pedido(db_session, status: str, entregador_id: str | None = None) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=status,
        endereco_entrega="Rua Teste, 123",
        total=Decimal("100.00"),
        deliverer_id=entregador_id,
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


async def test_old_portuguese_confirmar_coleta_path_is_gone(client, db_session):
    """Fix round 1 (reviewer finding #1): o pedido usado precisa EXISTIR e
    estar em AGUARDANDO_COLETA — a rota antiga (`confirmar_coleta`) 404a
    em "Pedido não encontrado" para QUALQUER id inexistente, então um id
    chumbado como `1` sem seed passaria com 404 mesmo se o path nunca
    tivesse sido traduzido. Com um pedido real que satisfaz a
    pré-condição de estado, a rota antiga responderia 200 se ainda
    existisse — o 404 aqui só pode vir da rota não existir mais."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)
    response = await client.patch(
        f"/entrega/{pedido.id}/confirmar-coleta", headers=headers_for("entregador")
    )
    assert response.status_code == 404


async def test_old_portuguese_confirmar_entrega_path_is_gone(client, db_session):
    """Fix round 1 (reviewer finding #1): mesma lógica — o pedido precisa
    EXISTIR, estar em EM_TRANSITO e pertencer ao entregador chamador
    (gap #2 fix), senão a rota antiga (`confirmar_entrega`) 404aria dentro
    de `transicionar_pedido` de qualquer forma, independente de
    tradução."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )
    response = await client.patch(
        f"/entrega/{pedido.id}/confirmar-entrega",
        headers=headers_for("entregador", sub=DELIVERER_A),
    )
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
    assert response.json()["deliverer_id"] == DELIVERER_A


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


# ── Fix round 1, reviewer finding #2: collect must honor a pre-set
# deliverer_id (e.g. from admin's assign-deliverer) instead of letting
# any other entregador overwrite it on claim. ──────────────────────────


async def test_collect_rejects_a_deliverer_when_admin_already_assigned_someone_else(
    client, db_session
):
    """Reproduz o cenário exato do reviewer: admin atribui o pedido a D1
    (sem mudar status), e D2 tenta "coletar" o mesmo pedido depois. Antes
    do fix, isso sequestrava silenciosamente o pedido de D1 para D2."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    assign_response = await client.patch(
        f"/admin/orders/{pedido.id}/assign-deliverer?entregador_id={DELIVERER_A}",
        headers=headers_for("admin", sub=ADMIN),
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["deliverer_id"] == DELIVERER_A

    hijack_response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_B)
    )
    assert hijack_response.status_code == 403


async def test_collect_allows_the_deliverer_admin_already_assigned(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    await client.patch(
        f"/admin/orders/{pedido.id}/assign-deliverer?entregador_id={DELIVERER_A}",
        headers=headers_for("admin", sub=ADMIN),
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200


# ── B7: `test_delivery_queue_rejects_limit_above_the_cap` so exercita a
# validacao do `Query(le=200)`; apagar `.limit(limit).offset(offset)` das
# duas queries de `app/routers/entrega.py` o deixa verde. Estes dois
# semeiam mais linhas que o limite pedido e conferem a contagem exata. ──


async def test_delivery_queue_actually_applies_limit_and_offset(client, db_session):
    total = 55
    for i in range(total):
        db_session.add(
            Order(
                user_id=str(uuid.uuid4()),
                status=StatusPedido.AGUARDANDO_COLETA.value,
                endereco_entrega=f"Rua Teste, {i}",
                total=Decimal("100.00"),
            )
        )
    await db_session.commit()

    first_page = await client.get(
        "/delivery/queue?limit=10", headers=headers_for("entregador", DELIVERER_A)
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10

    last_page = await client.get(
        "/delivery/queue?limit=10&offset=50", headers=headers_for("entregador", DELIVERER_A)
    )
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50

    assert {row["id"] for row in first_body}.isdisjoint({row["id"] for row in last_body})


async def test_delivery_mine_actually_applies_limit_and_offset(client, db_session):
    total = 55
    for i in range(total):
        db_session.add(
            Order(
                user_id=str(uuid.uuid4()),
                status=StatusPedido.EM_TRANSITO.value,
                endereco_entrega=f"Rua Teste, {i}",
                total=Decimal("100.00"),
                deliverer_id=DELIVERER_A,
            )
        )
    await db_session.commit()

    first_page = await client.get(
        "/delivery/mine?limit=10", headers=headers_for("entregador", DELIVERER_A)
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10

    last_page = await client.get(
        "/delivery/mine?limit=10&offset=50", headers=headers_for("entregador", DELIVERER_A)
    )
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50

    assert {row["id"] for row in first_body}.isdisjoint({row["id"] for row in last_body})
