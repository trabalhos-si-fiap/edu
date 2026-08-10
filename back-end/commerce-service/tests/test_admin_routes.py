"""Cobertura para `/admin/inventory` — não pedida literalmente pelo brief,
mas necessária porque a task 11 adicionou `EstoqueOut` (app/schemas/estoque.py)
para fechar uma violação da regra "nenhum endpoint devolve objeto ORM cru"
encontrada em `GET /admin/estoque` / `PATCH /admin/estoque/{id}/ajustar"
(sem response_model nenhum) enquanto essas rotas já precisavam ser tocadas
para traduzir o prefixo. Ver task-11-report.md."""

import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.pedido import Order, PedidoStatusHistorico
from app.models.produto import Estoque, Fornecedor, Product
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _seed_pedido(db_session, status: str) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=status,
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _historico_do_pedido(db_session, pedido_id: int) -> list[PedidoStatusHistorico]:
    """Histórico de transições de um pedido, em ordem de criação.

    Contra `PedidoStatusHistorico.order_id`: a task C2 renomeou o FK de
    `pedido_id` para `order_id` (a TABELA `pedido_status_historico` fica em
    português — agregado sem cliente — só o FK acompanhou o rename de
    `pedidos` para `orders`). Medido em app/models/pedido.py."""
    result = await db_session.execute(
        select(PedidoStatusHistorico)
        .where(PedidoStatusHistorico.order_id == pedido_id)
        .order_by(PedidoStatusHistorico.id)
    )
    return list(result.scalars().all())


async def _seed_pedido_com_endereco(db_session) -> Order:
    """Pedido com os oito campos `ship_*` preenchidos — só para o teste que
    prova que a visão de staff compõe `endereco_entrega` a partir deles
    (ver app/services/pedidos.py::endereco_formatado)."""
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.CRIADO.value,
        total=Decimal("100.00"),
        payment_method="PIX",
        ship_label="Casa",
        ship_zip_code="01310-100",
        ship_street="Av. Paulista",
        ship_number="1000",
        ship_complement="ap 42",
        ship_neighborhood="Bela Vista",
        ship_city="São Paulo",
        ship_state="SP",
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


# ── C4: `ship_*`, `payment_method`, `status_updated_at` e o snapshot do
# item — ver task-C4-brief.md. ────────────────────────────────────────────


async def test_staff_view_composes_the_address_from_the_snapshot(client, db_session):
    """Os schemas de staff mostravam `endereco_entrega`; a coluna morreu, mas
    a informação não — ela passa a ser composta de sete dos oito campos
    `ship_*` do snapshot (`ship_label` fica de fora — ver
    app/services/pedidos.py::endereco_formatado)."""
    await _seed_pedido_com_endereco(db_session)
    response = await client.get("/admin/orders", headers=headers_for("admin"))
    assert response.status_code == 200
    assert response.json()[0]["endereco_entrega"] == (
        "Av. Paulista, 1000, ap 42 - Bela Vista, São Paulo - SP, 01310-100"
    )


async def test_a_transition_stamps_status_updated_at(client, db_session):
    """A timeline do rastreio mostra a hora da última mudança — sem este
    carimbo ela mostraria a hora da criação para sempre."""
    pedido = await _seed_pedido(db_session, status=StatusPedido.CRIADO.value)
    antes = pedido.status_updated_at

    response = await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )
    assert response.status_code == 200

    await db_session.refresh(pedido)
    assert pedido.status_updated_at > antes


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

    Atualizado na task C1: `confirmar_pagamento` agora encadeia CRIADO ->
    CONFIRMADO -> AGUARDANDO_SEPARACAO numa única chamada (ver
    status_pedido.py), então a PRIMEIRA chamada por si só já grava duas
    linhas de histórico e publica dois eventos — isso não é o duplo-clique
    que este teste mede, é o comportamento normal de uma chamada. A
    invariante que sobra, e que continua valendo, é a mesma de sempre: a
    mesma máquina de estados que o `.with_for_update()` protege contra
    corrida também rejeita um reenvio sequencial — a segunda chamada nunca
    encontra o pedido em CRIADO de novo (já está em AGUARDANDO_SEPARACAO),
    então `validar_transicao` recusa ANTES de qualquer
    `db.add(PedidoStatusHistorico(...))` ou `publish_event(...)` rodar de
    novo. A SEGUNDA chamada não acrescenta nada — nem histórico, nem
    evento.
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

    historico = await _historico_do_pedido(db_session, pedido.id)
    assert [h.status for h in historico] == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]

    status_changed_events = [
        payload
        for routing_key, payload in _stub_publish_event
        if routing_key == "order.status_changed"
    ]
    assert [e["status"] for e in status_changed_events] == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]
    # `str(pedido.id)`: o payload carrega o id como string, porque JSON não
    # tem tipo UUID. Esta asserção comparava contra o `uuid.UUID` cru e
    # passava — ou seja, travava como CORRETO um payload que o transporte
    # real não conseguia serializar (task C3, fix round 1, finding 3).
    assert all(e["pedido_id"] == str(pedido.id) for e in status_changed_events)


# ── B7: o cap declarado nao provava que o `.limit()`/`.offset()` da query
# roda. Os testes de cap acima so exercitam a validacao do `Query(le=200)`
# — apagar `.limit(limit).offset(offset)` do `select()` os deixa verdes.
# Estes dois semeiam mais linhas que o limite pedido e conferem a
# contagem exata, seguindo o padrao ja usado em learning-service
# `test_reviews_today_listing_has_a_default_cap_and_offset`. ────────────


async def test_orders_listing_actually_applies_limit_and_offset(client, db_session):
    total = 55
    for _i in range(total):
        db_session.add(
            Order(
                user_id=str(uuid.uuid4()),
                status=StatusPedido.CRIADO.value,
                total=Decimal("100.00"),
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


async def test_confirm_payment_lands_the_order_in_the_picking_queue(
    client, db_session, _stub_publish_event
):
    """Confirmar pagamento passa por CONFIRMADO e para em AGUARDANDO_SEPARACAO.

    Parar em CONFIRMADO deixaria a fila de separação sempre vazia — não há
    simulador na fase 2 para avançar sozinho."""
    pedido = await _seed_pedido(db_session, status=StatusPedido.CRIADO.value)

    response = await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value

    historico = [h.status for h in await _historico_do_pedido(db_session, pedido.id)]
    assert historico == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]

    chaves_status = [
        payload["status"] for key, payload in _stub_publish_event if key == "order.status_changed"
    ]
    assert chaves_status == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]


async def test_confirm_payment_recovers_after_the_first_publish_fails(
    client, db_session, monkeypatch
):
    """Um publish que falha na PRIMEIRA transição não pode tornar o pedido
    irrecuperável.

    `transicionar_pedido` (app/routers/separacao.py) comita ANTES de
    publicar o evento, e `EventPublisher.publish`
    (packages/edu-common/src/edu_common/events.py) propaga a exceção. Se o
    broker der um blip no meio do clique do admin, `CRIADO -> CONFIRMADO`
    já está gravado e a rota estoura antes de encadear
    `CONFIRMADO -> AGUARDANDO_SEPARACAO`.

    `CONFIRMADO` não é estado de repouso: a fila de separação seleciona
    `AGUARDANDO_SEPARACAO` (`separacao.py::fila_separacao`) e
    `TRANSICOES_VALIDAS[CONFIRMADO]` só oferece `AGUARDANDO_SEPARACAO` e
    `CANCELADO` — e `confirmar_pagamento` era a ÚNICA rota que oferecia a
    primeira. Sem o guard de estado, o retry tentava `CONFIRMADO ->
    CONFIRMADO`, que `validar_transicao` recusa, e o pedido só saía de lá
    por SQL manual.

    O teste força o blip no evento de `CONFIRMADO`, prova que o pedido fica
    fora da fila, e então exige que um segundo clique — o gesto que o admin
    realmente faz — o leve até `AGUARDANDO_SEPARACAO` SEM duplicar a linha
    `CONFIRMADO` do histórico.
    """
    pedido = await _seed_pedido(db_session, status=StatusPedido.CRIADO.value)

    async def _publish_com_blip(routing_key: str, payload: dict) -> None:
        if payload.get("status") == StatusPedido.CONFIRMADO.value:
            raise RuntimeError("blip do broker")

    monkeypatch.setattr("app.routers.separacao.publish_event", _publish_com_blip)

    with pytest.raises(RuntimeError, match="blip do broker"):
        await client.patch(
            f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
        )

    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.CONFIRMADO.value

    fila = await client.get("/picking/queue", headers=headers_for("admin"))
    assert fila.status_code == 200
    assert str(pedido.id) not in {row["id"] for row in fila.json()}

    eventos: list[tuple[str, dict]] = []

    async def _publish_ok(routing_key: str, payload: dict) -> None:
        eventos.append((routing_key, payload))

    monkeypatch.setattr("app.routers.separacao.publish_event", _publish_ok)

    retry = await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == StatusPedido.AGUARDANDO_SEPARACAO.value

    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value

    assert [h.status for h in await _historico_do_pedido(db_session, pedido.id)] == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]
    assert [payload["status"] for _key, payload in eventos] == [
        StatusPedido.AGUARDANDO_SEPARACAO.value
    ]

    fila_depois = await client.get("/picking/queue", headers=headers_for("admin"))
    assert fila_depois.status_code == 200
    assert str(pedido.id) in {row["id"] for row in fila_depois.json()}


async def test_confirm_payment_on_an_unknown_order_still_answers_404(client):
    """Guarda do ramo `pedido is None` do guard de estado.

    Não nasceu vermelho: o 404 sempre veio de `transicionar_pedido` e
    continua vindo de lá. Existe porque o guard introduziu um caminho em que
    `scalar_one_or_none()` devolve `None` — sem este teste, trocá-lo por um
    `scalar_one()` (que estoura 500) passaria despercebido.
    """
    response = await client.patch(
        f"/admin/orders/{uuid.uuid4()}/confirm-payment", headers=headers_for("admin")
    )
    assert response.status_code == 404


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
