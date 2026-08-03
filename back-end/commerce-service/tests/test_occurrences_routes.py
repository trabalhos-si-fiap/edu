import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Pedido
from app.models.produto import Produto
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


PICKER_A = "00000000-0000-0000-0000-0000000000e1"
PICKER_B = "00000000-0000-0000-0000-0000000000e2"
DELIVERER_A = "00000000-0000-0000-0000-0000000000f1"
DELIVERER_B = "00000000-0000-0000-0000-0000000000f2"
ADMIN = "00000000-0000-0000-0000-0000000000aa"


async def _seed_pedido(db_session, status: str, **overrides) -> Pedido:
    defaults = {
        "aluno_id": str(uuid.uuid4()),
        "status": status,
        "endereco_entrega": "Rua Teste, 123",
        "valor_total": Decimal("100.00"),
    }
    defaults.update(overrides)
    pedido = Pedido(**defaults)
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_produto(db_session) -> Produto:
    produto = Produto(
        nome="Caderno",
        descricao="Caderno universitário",
        preco=Decimal("19.90"),
        categoria="papelaria",
    )
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)
    return produto


async def test_old_portuguese_occurrences_order_path_is_gone(client, db_session):
    """Fix round 1 (reviewer finding #1): o pedido usado precisa EXISTIR —
    a rota antiga (`listar_ocorrencias_pedido`) 404a em "Pedido não
    encontrado" para QUALQUER id inexistente, então um id chumbado como
    `1` sem seed passaria com 404 mesmo se o path nunca tivesse sido
    traduzido, provando nada. Com um pedido real, a rota antiga
    responderia 200 (lista vazia de ocorrências) se ainda existisse — o
    404 aqui só pode vir da rota não existir mais."""
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value)
    response = await client.get(
        f"/ocorrencias/pedido/{pedido.id}", headers=headers_for("admin", sub=ADMIN)
    )
    assert response.status_code == 404


async def test_old_portuguese_falta_estoque_path_is_gone(client):
    response = await client.post(
        "/ocorrencias/falta-estoque", json={}, headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 404


async def test_old_portuguese_atraso_entrega_path_is_gone(client):
    response = await client.post(
        "/ocorrencias/atraso-entrega", json={}, headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 404


async def test_old_portuguese_resolver_path_is_gone(client, db_session):
    """Fix round 1 (reviewer finding #1): mesma lógica — a ocorrência
    precisa EXISTIR e ser resolvível pelo aluno chamador, senão a rota
    antiga 404aria em "Ocorrência não encontrada" de qualquer forma,
    independente de tradução."""
    aluno_id = "00000000-0000-0000-0000-000000000001"  # sub padrão de headers_for("student")
    pedido = await _seed_pedido(db_session, StatusPedido.CRIADO.value, aluno_id=aluno_id)
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        motivo="teste",
        criado_por=aluno_id,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)

    response = await client.post(
        f"/ocorrencias/{ocorrencia.id}/resolver",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student"),
    )
    assert response.status_code == 404


# ── Gap de autorização #4: reportar_falta_estoque/stock-shortage ─────────
# Judgement call (ver task-11-report.md): tratada como o gap #3 — só o
# separador que reivindicou o pedido (ou um admin) pode reportar.


async def test_stock_shortage_requires_authentication(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": pedido.id, "produto_id": produto.id, "motivo": "sem estoque"},
    )
    assert response.status_code == 403


async def test_stock_shortage_forbids_a_separador_who_never_claimed_the_order(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": pedido.id, "produto_id": produto.id, "motivo": "sem estoque"},
        headers=headers_for("separador", sub=PICKER_B),
    )
    assert response.status_code == 403


async def test_stock_shortage_allows_the_separador_who_claimed_the_order(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": pedido.id, "produto_id": produto.id, "motivo": "sem estoque"},
        headers=headers_for("separador", sub=PICKER_A),
    )
    assert response.status_code == 201


async def test_stock_shortage_allows_admin_regardless_of_ownership(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, separador_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": pedido.id, "produto_id": produto.id, "motivo": "sem estoque"},
        headers=headers_for("admin", sub=ADMIN),
    )
    assert response.status_code == 201


# ── Gap de autorização #5: reportar_atraso_entrega/delivery-delay ────────
# Mesmo judgement call, espelhado para entregador/entregador_id.


async def test_delivery_delay_requires_authentication(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": pedido.id,
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
    )
    assert response.status_code == 403


async def test_delivery_delay_forbids_a_deliverer_who_never_claimed_the_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": pedido.id,
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
        headers=headers_for("entregador", sub=DELIVERER_B),
    )
    assert response.status_code == 403


async def test_delivery_delay_allows_the_deliverer_who_claimed_the_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": pedido.id,
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
        headers=headers_for("entregador", sub=DELIVERER_A),
    )
    assert response.status_code == 201


async def test_delivery_delay_allows_admin_regardless_of_ownership(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": pedido.id,
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
        headers=headers_for("admin", sub=ADMIN),
    )
    assert response.status_code == 201


async def test_occurrences_for_order_listing_is_paginated(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value)
    response = await client.get(
        f"/occurrences/order/{pedido.id}?limit=5000", headers=headers_for("admin", sub=ADMIN)
    )
    assert response.status_code == 422
