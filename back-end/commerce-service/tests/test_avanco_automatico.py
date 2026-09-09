from datetime import UTC, datetime, timedelta

from app.config import settings
from app.services.avanco_automatico import PROXIMO_ESTADO, avancar_parados
from app.services.status_pedido import TRANSICOES_VALIDAS, StatusPedido


def test_every_hop_is_a_valid_transition():
    """Um destino fora de TRANSICOES_VALIDAS faria o job levantar 400 em
    silêncio a cada varredura, para sempre."""
    for origem, destino in PROXIMO_ESTADO.items():
        assert destino in TRANSICOES_VALIDAS[origem]


def test_the_substitution_wait_never_advances_on_its_own():
    """É o único estado que espera decisão do aluno — e essa decisão é o que
    a apresentação está mostrando."""
    assert StatusPedido.AGUARDANDO_SUBSTITUICAO not in PROXIMO_ESTADO


def test_terminal_states_never_advance():
    assert StatusPedido.ENTREGUE not in PROXIMO_ESTADO
    assert StatusPedido.CANCELADO not in PROXIMO_ESTADO


async def test_it_is_off_by_default(db_session, seed_pedido_parado):
    """`AVANCO_AUTOMATICO_SEGUNDOS` ausente vale 0, e 0 é desligado. Critério
    de pronto 6 da spec."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(hours=3)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 0)

    assert avancados == []
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value


async def test_it_does_not_fire_before_the_deadline(db_session, seed_pedido_parado):
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(seconds=30)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == []
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value


async def test_it_fires_after_the_deadline(db_session, seed_pedido_parado, _stub_publish_event):
    """`_stub_publish_event` (fixture já existente, mesma usada por `client`)
    substitui `publish_event` por um capturador: `avancar_parados` escreve por
    `transicionar_pedido`, que publica, e `ASGITransport` nunca roda o
    lifespan que conectaria o publisher de verdade — sem o stub, este teste
    estouraria `RuntimeError: EventPublisher not connected`."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_SEPARACAO.value


async def test_a_manual_action_restarts_the_clock(
    db_session, seed_pedido_parado, _stub_publish_event
):
    """Ação manual sempre vence: `transicionar_pedido` carimba
    `status_updated_at`, e a contagem recomeça dali. Nada precisa ser
    cancelado.

    `_stub_publish_event` pelo mesmo motivo de `test_it_fires_after_the_deadline`
    acima: a chamada manual a `transicionar_pedido` também publica, e o
    publisher real nunca está conectado nesta suíte."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    from app.routers.separacao import transicionar_pedido

    await transicionar_pedido(
        db_session, pedido.id, StatusPedido.EM_SEPARACAO.value, str(pedido.user_id)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == []


async def test_it_publishes_through_the_same_funnel(db_session, seed_pedido_parado, monkeypatch):
    """Escreve pela mesma função de transição que as rotas usam — nunca
    UPDATE direto —, então validação, histórico e evento acontecem de um jeito
    só."""
    eventos: list[tuple[str, dict]] = []

    async def _capturar(chave, payload):
        eventos.append((chave, payload))

    monkeypatch.setattr("app.routers.separacao.publish_event", _capturar)
    await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )

    await avancar_parados(db_session, datetime.now(UTC), 600)

    assert [chave for chave, _ in eventos] == ["order.status_changed"]


# ── Fix final: a rede de segurança congela o destino no salto que substitui
# `confirmar_coleta`. ───────────────────────────────────────────────────────


async def _seed_pronto_para_coleta(db_session, carregamento_id: int, parado_ha: timedelta):
    """Pedido em AGUARDANDO_COLETA, com snapshot de endereço e carregamento —
    o mesmo estado que `PATCH /delivery/{id}/collect` encontraria."""
    import uuid
    from decimal import Decimal

    from app.models.pedido import Order

    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.AGUARDANDO_COLETA.value,
        total=Decimal("100.00"),
        status_updated_at=datetime.now(UTC) - parado_ha,
        carregamento_id=carregamento_id,
        ship_label="Casa",
        ship_zip_code="13201-005",
        ship_street="Rua das Flores",
        ship_number="42",
        ship_neighborhood="Centro",
        ship_city="Jundiaí",
        ship_state="SP",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_the_collect_hop_freezes_the_destination(
    db_session, seed_carregamento, monkeypatch, _stub_publish_event
):
    """`congelar_destino` só era chamado por `confirmar_coleta`. Quando a rede
    de segurança faz a coleta, o pedido ficava sem coordenada de destino para
    sempre — o simulador o filtra fora e o mapa do comprador nunca anda."""
    from decimal import Decimal

    from app.services.directions import DirectionsResult

    carregamento = await seed_carregamento()
    pedido = await _seed_pronto_para_coleta(db_session, carregamento.id, timedelta(minutes=20))
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")

    async def fake_fetch(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="10 km",
            distance_km=10.0,
            duration_text="20 min",
            duration_minutes=20,
            destination_latitude=-23.185700,
            destination_longitude=-46.897800,
        )

    monkeypatch.setattr("app.services.posicao.directions.fetch_directions", fake_fetch)

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_TRANSITO.value
    assert pedido.destino_lat == Decimal("-23.185700")
    assert pedido.destino_lng == Decimal("-46.897800")


async def test_a_hop_that_is_not_the_collect_never_touches_the_destination(
    db_session, seed_pedido_parado, monkeypatch, _stub_publish_event
):
    """Congelar destino é um efeito da COLETA, não de qualquer avanço: um
    salto AGUARDANDO_SEPARACAO -> EM_SEPARACAO não pode chamar a Google."""
    chamadas = []

    async def _nao_deveria(db, order):
        chamadas.append(order.id)

    monkeypatch.setattr("app.services.avanco_automatico.congelar_destino", _nao_deveria)
    await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )

    await avancar_parados(db_session, datetime.now(UTC), 600)

    assert chamadas == []
