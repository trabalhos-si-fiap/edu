import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order, OrderItem
from app.models.produto import Product
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


PICKER_A = "00000000-0000-0000-0000-0000000000e1"
PICKER_B = "00000000-0000-0000-0000-0000000000e2"
DELIVERER_A = "00000000-0000-0000-0000-0000000000f1"
DELIVERER_B = "00000000-0000-0000-0000-0000000000f2"
ADMIN = "00000000-0000-0000-0000-0000000000aa"
# sub padrão de headers_for("student")
ALUNO = "00000000-0000-0000-0000-000000000001"


async def _seed_pedido(db_session, status: str, **overrides) -> Order:
    defaults = {
        "user_id": str(uuid.uuid4()),
        "status": status,
        "total": Decimal("100.00"),
    }
    defaults.update(overrides)
    pedido = Order(**defaults)
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_produto(db_session) -> Product:
    produto = Product(
        name="Caderno",
        description="Caderno universitário",
        price=Decimal("19.90"),
        type="papelaria",
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
    pedido = await _seed_pedido(db_session, StatusPedido.CRIADO.value, user_id=aluno_id)
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
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": str(pedido.id), "produto_id": str(produto.id), "motivo": "sem estoque"},
    )
    assert response.status_code == 403


async def test_stock_shortage_forbids_a_separador_who_never_claimed_the_order(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": str(pedido.id), "produto_id": str(produto.id), "motivo": "sem estoque"},
        headers=headers_for("separador", sub=PICKER_B),
    )
    assert response.status_code == 403


async def test_stock_shortage_allows_the_separador_who_claimed_the_order(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": str(pedido.id), "produto_id": str(produto.id), "motivo": "sem estoque"},
        headers=headers_for("separador", sub=PICKER_A),
    )
    assert response.status_code == 201


async def test_stock_shortage_allows_admin_regardless_of_ownership(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={"pedido_id": str(pedido.id), "produto_id": str(produto.id), "motivo": "sem estoque"},
        headers=headers_for("admin", sub=ADMIN),
    )
    assert response.status_code == 201


# ── Gap de autorização #5: reportar_atraso_entrega/delivery-delay ────────
# Mesmo judgement call, espelhado para entregador/deliverer_id.


async def test_delivery_delay_requires_authentication(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": str(pedido.id),
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
    )
    assert response.status_code == 403


async def test_delivery_delay_forbids_a_deliverer_who_never_claimed_the_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": str(pedido.id),
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
        headers=headers_for("entregador", sub=DELIVERER_B),
    )
    assert response.status_code == 403


async def test_delivery_delay_allows_the_deliverer_who_claimed_the_order(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": str(pedido.id),
            "motivo": "trânsito intenso",
            "nova_data_sugerida": "2026-01-01T12:00:00Z",
        },
        headers=headers_for("entregador", sub=DELIVERER_A),
    )
    assert response.status_code == 201


async def test_delivery_delay_allows_admin_regardless_of_ownership(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
    )

    response = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": str(pedido.id),
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


# ── B7: nada provava que o `.limit(limit).offset(offset)` de
# `listar_ocorrencias_pedido` (app/routers/ocorrencias.py) roda de fato —
# apagar a clausula deixava a suite verde. `criado_em` vai explicito e
# distinto por linha porque a rota ordena por `criado_em.desc()`: com o
# `server_default=func.now()` as 55 linhas empatariam no mesmo timestamp
# e a fronteira entre as paginas ficaria nao-deterministica. ────────────


async def test_order_occurrences_listing_actually_applies_limit_and_offset(client, db_session):
    from datetime import UTC, datetime, timedelta

    pedido = await _seed_pedido(db_session, StatusPedido.CRIADO.value)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    total = 55
    for i in range(total):
        db_session.add(
            Ocorrencia(
                pedido_id=pedido.id,
                tipo="ATRASO_ENTREGA",
                status="ABERTA",
                motivo=f"Ocorrencia {i}",
                criado_por=ADMIN,
                criado_em=base + timedelta(minutes=i),
            )
        )
    await db_session.commit()

    first_page = await client.get(
        f"/occurrences/order/{pedido.id}?limit=10", headers=headers_for("admin", ADMIN)
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10

    last_page = await client.get(
        f"/occurrences/order/{pedido.id}?limit=10&offset=50",
        headers=headers_for("admin", ADMIN),
    )
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50

    assert {row["id"] for row in first_body}.isdisjoint({row["id"] for row in last_body})


async def _seed_ocorrencia_falta_estoque(db_session, pedido, produto) -> Ocorrencia:
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="FALTA_ESTOQUE",
        status="ABERTA",
        produto_id=produto.id,
        motivo="Sem estoque no CD",
        criado_por=PICKER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    return ocorrencia


async def test_concurrent_resolves_apply_the_price_delta_once(client, db_session, monkeypatch):
    """O `status != "ABERTA"` é um TOCTOU sem lock de linha.

    Precisa ser concorrente E precisa forçar a intercalação. Em série o
    defeito não aparece: a segunda chamada enxerga o `RESOLVIDA` que a
    primeira já commitou e devolve 400 sozinha. E um `asyncio.gather` puro
    também não basta — as queries locais voltam rápido demais para o event
    loop trocar de tarefa (medido).

    O encontro é feito sem `sleep`: a PRIMEIRA requisição para no seu commit
    e só segue quando a SEGUNDA abre a própria sessão. O sinal sai ANTES do
    SELECT da segunda, de propósito — depois dele, com o `FOR UPDATE` no
    lugar, ela ficaria bloqueada no banco esperando a primeira, que estaria
    esperando por ela, e o teste travaria em vez de medir.
    """
    original = await _seed_produto(db_session)
    substituto = Product(
        name="Substituto",
        price=Decimal("150.00"),
        type="apostila",
        image_url="products/substituto.jpg",
        rating_avg=Decimal("4.80"),
        rating_count=42,
    )
    db_session.add(substituto)
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, user_id=ALUNO, picker_id=PICKER_A
    )
    # `image_url`/`rating_avg`/`rating_count` do item de propósito
    # diferentes dos do `substituto` acima — se a resolução deixasse esses
    # campos intocados (o mesmo defeito do `product_name` stale, achado do
    # code review), a asserção do fim do teste passaria por acidente com os
    # dois produtos tendo os mesmos valores por coincidência de default.
    item = OrderItem(
        order_id=pedido.id,
        product_id=original.id,
        product_name=original.name,
        supplier_id=None,
        quantity=2,
        unit_price=Decimal("100.00"),
        image_url="products/original.jpg",
        rating_avg=Decimal("3.00"),
        rating_count=7,
    )
    db_session.add(item)
    pedido.total = Decimal("200.00")
    await db_session.commit()
    await db_session.refresh(substituto)
    # Capturados como valores Python simples, não como acesso a atributo do
    # ORM: `db_session.expire_all()` mais abaixo expira TODOS os objetos da
    # sessão, `substituto` incluído, e reler um atributo expirado fora de um
    # contexto async levantaria `MissingGreenlet` (medido).
    substituto_id = substituto.id
    substituto_image_url = substituto.image_url
    substituto_rating_avg = substituto.rating_avg
    substituto_rating_count = substituto.rating_count
    ocorrencia = await _seed_ocorrencia_falta_estoque(db_session, pedido, original)

    execute_real = AsyncSession.execute
    commit_real = AsyncSession.commit
    sessoes_vistas = {id(db_session)}
    a_segunda_abriu = asyncio.Event()
    estado = {"ja_esperou": False}

    async def execute_espiao(self, *args, **kwargs):
        if id(self) not in sessoes_vistas:
            sessoes_vistas.add(id(self))
            if len(sessoes_vistas) == 3:  # db_session + as duas sessões de rota
                a_segunda_abriu.set()
        return await execute_real(self, *args, **kwargs)

    async def commit_espiao(self):
        if id(self) != id(db_session) and not estado["ja_esperou"]:
            estado["ja_esperou"] = True
            await asyncio.wait_for(a_segunda_abriu.wait(), timeout=5)
        return await commit_real(self)

    monkeypatch.setattr(AsyncSession, "execute", execute_espiao)
    monkeypatch.setattr(AsyncSession, "commit", commit_espiao)

    corpo = {"resolucao": "substituir", "produto_escolhido_id": str(substituto.id)}
    primeira, segunda = await asyncio.gather(
        client.post(
            f"/occurrences/{ocorrencia.id}/resolve", json=corpo, headers=headers_for("student")
        ),
        client.post(
            f"/occurrences/{ocorrencia.id}/resolve", json=corpo, headers=headers_for("student")
        ),
    )

    monkeypatch.undo()

    codigos = sorted([primeira.status_code, segunda.status_code])
    assert codigos == [200, 400], f"{primeira.text} / {segunda.text}"

    db_session.expire_all()
    await db_session.refresh(pedido)
    # 200.00 + (150.00 - 100.00) * 2 = 300.00. Aplicada UMA vez.
    assert pedido.total == Decimal("300.00")

    # O snapshot inteiro tem que virar o do produto NOVO, não só id/preço —
    # achado do code review: `product_name` ficava com o nome do produto
    # ANTIGO depois da substituição, e o mesmo valeria para
    # image_url/rating_avg/rating_count se não fossem atualizados junto.
    await db_session.refresh(item)
    assert item.product_id == substituto_id
    assert item.product_name == "Substituto"
    assert item.image_url == substituto_image_url
    assert item.rating_avg == substituto_rating_avg
    assert item.rating_count == substituto_rating_count


async def test_cancel_publishes_the_status_change_after_the_commit(
    client, db_session, _stub_publish_event
):
    """Ordem relativa dos eventos. A prova de que são pós-commit é o teste
    seguinte — este sozinho passaria também com o publish antes do commit."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, user_id=ALUNO, picker_id=PICKER_A
    )
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        nova_data_sugerida=datetime.now(UTC) + timedelta(days=2),
        motivo="Chuva na rota",
        criado_por=DELIVERER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    _stub_publish_event.clear()

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student"),
    )
    assert response.status_code == 200, response.text

    chaves = [routing_key for routing_key, _ in _stub_publish_event]
    assert chaves == ["order.status_changed", "order.occurrence_resolved"]

    db_session.expire_all()
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.CANCELADO.value


async def test_cancelling_through_an_occurrence_stamps_status_updated_at(client, db_session):
    """`cancelar_pedido` (resolução de ocorrência) muta `Order.status` fora
    do funil `transicionar_pedido` — é o único outro lugar do serviço que
    faz isso (`grep -rn "\\.status = " app/routers/ app/services/`, ver
    task-C4-report.md). Sem o mesmo carimbo que o Step 5 da C4 deu ao
    funil, a timeline do rastreio mostraria a hora da criação para sempre
    para o único cancelamento que o próprio aluno pode disparar."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, user_id=ALUNO, picker_id=PICKER_A
    )
    antes = pedido.status_updated_at
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        nova_data_sugerida=datetime.now(UTC) + timedelta(days=2),
        motivo="Chuva na rota",
        criado_por=DELIVERER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student"),
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    await db_session.refresh(pedido)
    assert pedido.status_updated_at > antes


async def test_a_failed_commit_publishes_nothing(
    client, db_session, monkeypatch, _stub_publish_event
):
    """Se o commit estourar, o aluno não pode ter sido notificado."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, user_id=ALUNO, picker_id=PICKER_A
    )
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        nova_data_sugerida=datetime.now(UTC) + timedelta(days=2),
        motivo="Chuva na rota",
        criado_por=DELIVERER_A,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    _stub_publish_event.clear()

    async def _commit_que_falha(self):
        raise RuntimeError("commit falhou")

    # Afeta TODA sessão, inclusive a do `db_session` — por isso o seed
    # acontece antes do patch e nada é commitado depois dele.
    monkeypatch.setattr(AsyncSession, "commit", _commit_que_falha)

    with pytest.raises(RuntimeError, match="commit falhou"):
        await client.post(
            f"/occurrences/{ocorrencia.id}/resolve",
            json={"resolucao": "cancelar_pedido"},
            headers=headers_for("student"),
        )

    assert _stub_publish_event == []


async def test_a_picker_cannot_read_occurrences_of_an_order_they_do_not_hold(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("separador", sub=PICKER_B)
    )
    assert response.status_code == 403


async def test_a_courier_cannot_read_occurrences_of_an_order_they_do_not_hold(client, db_session):
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
    )

    response = await client.get(
        f"/occurrences/order/{pedido.id}",
        headers=headers_for("entregador", sub=str(uuid.uuid4())),
    )
    assert response.status_code == 403


async def test_a_picker_with_no_assignment_at_all_is_also_refused(client, db_session):
    """`picker_id is None` não pode ser lido como "é meu"."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value)

    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 403


async def test_the_assigned_picker_can_read_them(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 200


async def test_an_admin_still_reads_any_order(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)
    response = await client.get(
        f"/occurrences/order/{pedido.id}", headers=headers_for("admin", sub=ADMIN)
    )
    assert response.status_code == 200


async def test_occurrence_detail_applies_the_same_rule(client, db_session):
    produto = await _seed_produto(db_session)
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)
    ocorrencia = await _seed_ocorrencia_falta_estoque(db_session, pedido, produto)

    response = await client.get(
        f"/occurrences/{ocorrencia.id}", headers=headers_for("separador", sub=PICKER_B)
    )
    assert response.status_code == 403
