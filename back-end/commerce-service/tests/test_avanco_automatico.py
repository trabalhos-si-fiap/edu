from datetime import UTC, datetime, timedelta

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
