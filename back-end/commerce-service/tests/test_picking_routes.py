import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import insert

from app.config import settings
from app.models.pedido import Order
from app.services.status_pedido import StatusPedido

# Precisa bater com CANDIDATOS_FILA_MAXIMO em app/routers/separacao.py — mas
# como LITERAL aqui, não como import da constante (nunca alimentar a
# constante da implementação de volta no teste que a fixa).
CANDIDATOS_FILA_MAXIMO_ESPERADO = 500


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
ADMIN = "00000000-0000-0000-0000-0000000000a9"


async def _seed_pedido_em_separacao(db_session, separador_id: str | None) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.EM_SEPARACAO.value,
        endereco_entrega="Rua Teste, 123",
        total=Decimal("100.00"),
        picker_id=separador_id,
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_pedido_aguardando_separacao(db_session) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.AGUARDANDO_SEPARACAO.value,
        endereco_entrega="Rua Teste, 123",
        total=Decimal("100.00"),
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


# ── Fix round 1, reviewer finding #2: start must honor a pre-set
# picker_id (e.g. from admin's assign-picker) instead of letting any
# other separador overwrite it on claim. ────────────────────────────────


async def test_start_rejects_a_separador_when_admin_already_assigned_someone_else(
    client, db_session
):
    """Mesmo cenário do reviewer, espelhado para picking: admin atribui o
    pedido a P1 (sem mudar status), e P2 tenta "iniciar" a separação
    depois."""
    pedido = await _seed_pedido_aguardando_separacao(db_session)

    assign_response = await client.patch(
        f"/admin/orders/{pedido.id}/assign-picker?separador_id={PICKER_A}",
        headers=headers_for("admin", sub=ADMIN),
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["picker_id"] == PICKER_A

    hijack_response = await client.patch(
        f"/picking/{pedido.id}/start", headers=headers_for("separador", sub=PICKER_B)
    )
    assert hijack_response.status_code == 403


async def test_start_allows_the_separador_admin_already_assigned(client, db_session):
    pedido = await _seed_pedido_aguardando_separacao(db_session)

    await client.patch(
        f"/admin/orders/{pedido.id}/assign-picker?separador_id={PICKER_A}",
        headers=headers_for("admin", sub=ADMIN),
    )

    response = await client.patch(
        f"/picking/{pedido.id}/start", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 200


# ── Fix round 1, reviewer finding #5: the candidate fetch behind
# /picking/queue must itself be capped, not just the paginated response. ─


async def test_picking_queue_candidate_fetch_is_capped(client, db_session):
    """Semeia mais pedidos do que `CANDIDATOS_FILA_MAXIMO_ESPERADO` e prova
    que o pool de candidatos pontuados/ordenados tem exatamente esse
    tamanho — não o total semeado.

    Todos os pedidos são idênticos em espera/risco (sem itens, portanto
    sem risco de estoque, e criados quase simultaneamente), então
    `priorizar_fila` empata todos os scores; como `list.sort` é estável, a
    ordem final == ordem de chegada do SELECT, que é `created_at ASC, id
    ASC` — ou seja, ordem de inserção. Pedindo `offset=490&limit=200`:
    se o fetch está corretamente limitado ao teto, sobram só os últimos
    `CANDIDATOS_FILA_MAXIMO_ESPERADO - 490 = 10` candidatos; sem o cap
    (bug), sobrariam `total_semeado - 490 = 15`.
    """
    total_semeado = CANDIDATOS_FILA_MAXIMO_ESPERADO + 5
    await db_session.execute(
        insert(Order),
        [
            {
                "user_id": str(uuid.uuid4()),
                "status": StatusPedido.AGUARDANDO_SEPARACAO.value,
                "endereco_entrega": "Rua Teste, 123",
                "total": Decimal("100.00"),
            }
            for _ in range(total_semeado)
        ],
    )
    await db_session.commit()

    response = await client.get(
        "/picking/queue?limit=200&offset=490", headers=headers_for("separador")
    )
    assert response.status_code == 200
    assert len(response.json()) == 10


async def test_old_portuguese_finalizar_path_is_gone(client, db_session):
    """Fix round 1 (reviewer finding #1): o pedido usado precisa EXISTIR e
    estar em EM_SEPARACAO com `picker_id=PICKER_A` — a rota antiga
    (`finalizar_separacao`) 404a em "Pedido não encontrado" para QUALQUER
    id inexistente, então um id chumbado como `1` sem seed passaria com
    404 mesmo se o path nunca tivesse sido traduzido. Com um pedido real
    que satisfaz TODAS as pré-condições (existe, dono correto, sem
    ocorrência aberta, transição válida), a rota antiga responderia 200 se
    ainda existisse — o 404 aqui só pode vir da rota não existir mais."""
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)
    response = await client.patch(
        f"/separacao/{pedido.id}/finalizar", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 404
