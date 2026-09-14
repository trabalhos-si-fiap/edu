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


# ── Fix final: um pedido ruim não pode abortar o resto da varredura. ───────


async def test_one_bad_order_does_not_abort_the_rest_of_the_tick(
    db_session, seed_pedido_parado, monkeypatch, _stub_publish_event
):
    """O `select` é feito sem lock; `transicionar_pedido` relê com lock. Um
    pedido cujo status mudou nessa janela levanta `HTTPException(400)` — e
    esse 400 escapava do laço, então TODO pedido ainda não visitado era
    pulado naquele tique. Um estado inconsistente de um pedido não pode
    calar a rede de segurança para os outros."""
    from fastapi import HTTPException

    from app.services import avanco_automatico as avanco_module

    ruim = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    bom = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    real = avanco_module.transicionar_pedido

    async def _falha_so_no_ruim(db, pedido_id, *args, **kwargs):
        if pedido_id == ruim.id:
            raise HTTPException(400, "Transição inválida: AGUARDANDO_SEPARACAO → EM_SEPARACAO")
        return await real(db, pedido_id, *args, **kwargs)

    monkeypatch.setattr("app.services.avanco_automatico.transicionar_pedido", _falha_so_no_ruim)

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == [bom.id]
    await db_session.refresh(bom)
    assert bom.status == StatusPedido.EM_SEPARACAO.value
    await db_session.refresh(ruim)
    assert ruim.status == StatusPedido.AGUARDANDO_SEPARACAO.value


# ── Estados de passagem: a rede de segurança atravessa, no mesmo tique, os
# estados que as rotas manuais atravessam numa chamada só. ─────────────────


async def _historico(db_session, pedido_id) -> list[str]:
    from sqlalchemy import select

    from app.models.pedido import PedidoStatusHistorico

    resultado = await db_session.execute(
        select(PedidoStatusHistorico.status)
        .where(PedidoStatusHistorico.order_id == pedido_id)
        .order_by(PedidoStatusHistorico.id)
    )
    return list(resultado.scalars().all())


async def test_an_auto_advanced_picking_ends_waiting_for_collection(
    db_session, seed_pedido_parado, _stub_publish_event
):
    """O bug: EM_SEPARACAO avançava para SEPARADO, e SEPARADO não tinha
    próximo passo — o pedido ficava lá para sempre, fora da fila do
    entregador (que lê AGUARDANDO_COLETA) e fora de qualquer rota manual
    (`finish` exige EM_SEPARACAO). `finalizar_separacao` encadeia
    SEPARADO -> AGUARDANDO_COLETA na mesma chamada; a rede de segurança faz o
    mesmo, com as mesmas duas linhas de histórico e os dois eventos, nessa
    ordem."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.EM_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 180)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_COLETA.value
    assert await _historico(db_session, pedido.id) == [
        StatusPedido.SEPARADO.value,
        StatusPedido.AGUARDANDO_COLETA.value,
    ]
    assert [payload["status"] for _chave, payload in _stub_publish_event] == [
        StatusPedido.SEPARADO.value,
        StatusPedido.AGUARDANDO_COLETA.value,
    ]


async def test_an_order_left_in_separado_is_moved_on(
    db_session, seed_pedido_parado, _stub_publish_event
):
    """Quem já ficou preso em SEPARADO pelo bug antigo — ou por um encadeamento
    interrompido no meio (broker fora entre as duas transições) — sai de lá no
    tique seguinte."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.SEPARADO.value, parado_ha=timedelta(minutes=20)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 180)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_COLETA.value


async def test_the_payment_confirmation_is_crossed_in_one_tick(
    db_session, seed_pedido_parado, _stub_publish_event
):
    """Mesmo critério para CONFIRMADO: `confirmar_pagamento_do_pedido`
    (admin.py) o atravessa numa chamada, e `CONFIRMADO` não tem destinatário
    de push justamente por ser transitório. Repousar nele por um prazo
    inteiro seria um passo que nenhuma rota manual produz."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.CRIADO.value, parado_ha=timedelta(minutes=20)
    )

    await avancar_parados(db_session, datetime.now(UTC), 180)

    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value
    assert await _historico(db_session, pedido.id) == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]


async def test_a_full_run_of_ticks_takes_an_order_from_created_to_delivered(
    db_session, seed_pedido_parado, _stub_publish_event
):
    """Ponta a ponta, só com a rede de segurança: nenhum estado do caminho
    feliz pode ser um beco sem saída. Cada tique roda "no futuro" (o prazo já
    venceu para a transição que o tique anterior acabou de carimbar)."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.CRIADO.value, parado_ha=timedelta(minutes=20)
    )

    for tique in range(1, 11):
        await avancar_parados(db_session, datetime.now(UTC) + timedelta(hours=tique), 180)
        await db_session.refresh(pedido)
        if pedido.status == StatusPedido.ENTREGUE.value:
            break

    assert pedido.status == StatusPedido.ENTREGUE.value
    assert tique == 5
    assert await _historico(db_session, pedido.id) == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
        StatusPedido.EM_SEPARACAO.value,
        StatusPedido.SEPARADO.value,
        StatusPedido.AGUARDANDO_COLETA.value,
        StatusPedido.EM_TRANSITO.value,
        StatusPedido.ENTREGUE.value,
    ]


async def test_a_status_changed_after_the_scan_is_never_trampled(
    db_session, test_session_factory, seed_pedido_parado, monkeypatch, _stub_publish_event
):
    """A varredura carregava ENTIDADES `Order` na sessão do tique. O
    `SELECT ... FOR UPDATE` de `transicionar_pedido`, na mesma sessão, devolve
    a instância do identity map SEM repopular os atributos (o mesmo defeito
    medido em `admin.py::confirmar_pagamento`) — então a revalidação com lock
    olhava o status da varredura, não o do banco.

    O caso que importa: o separador reporta falta de estoque entre a varredura
    e a transição. O pedido está em AGUARDANDO_SUBSTITUICAO, esperando o
    aluno, e a rede de segurança gravava SEPARADO por cima da decisão que ela
    jurou nunca atropelar.

    O tique roda numa sessão própria, como `scheduler.py::tick_avanco_automatico`
    roda — a `db_session` do teste já guarda a instância semeada."""
    from sqlalchemy import update

    from app.models.pedido import Order
    from app.services import avanco_automatico as avanco_module

    pedido = await seed_pedido_parado(
        status=StatusPedido.EM_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    real = avanco_module.transicionar_pedido

    async def _falta_reportada_antes_da_transicao(db, pedido_id, *args, **kwargs):
        async with test_session_factory() as separador:
            await separador.execute(
                update(Order)
                .where(Order.id == pedido_id)
                .values(status=StatusPedido.AGUARDANDO_SUBSTITUICAO.value)
            )
            await separador.commit()
        return await real(db, pedido_id, *args, **kwargs)

    monkeypatch.setattr(
        "app.services.avanco_automatico.transicionar_pedido", _falta_reportada_antes_da_transicao
    )

    async with test_session_factory() as sessao_do_tique:
        avancados = await avancar_parados(sessao_do_tique, datetime.now(UTC), 180)

    assert avancados == []
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SUBSTITUICAO.value


async def _abrir_ocorrencia(db_session, pedido_id, transportadora_id: int | None = None):
    import uuid

    from app.models.ocorrencia import Ocorrencia

    db_session.add(
        Ocorrencia(
            pedido_id=pedido_id,
            tipo="FALTA_ESTOQUE" if transportadora_id is None else "DANO",
            status="ABERTA",
            motivo="teste",
            criado_por=uuid.uuid4(),
            transportadora_id=transportadora_id,
        )
    )
    await db_session.commit()


async def test_an_occurrence_waiting_on_the_student_holds_the_picking(
    db_session, seed_pedido_parado, _stub_publish_event
):
    """`finalizar_separacao` recusa terminar com ocorrência aberta que o aluno
    decide. A rede de segurança substitui essa rota, então recusa pelo mesmo
    motivo — senão o pedido sairia para coleta com a decisão do aluno
    pendente."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.EM_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    await _abrir_ocorrencia(db_session, pedido.id)

    avancados = await avancar_parados(db_session, datetime.now(UTC), 180)

    assert avancados == []
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_SEPARACAO.value


async def test_a_carrier_occurrence_does_not_hold_the_picking(
    db_session, seed_carregamento, seed_pedido_parado, _stub_publish_event
):
    """O mesmo escopo do guard da rota: ocorrência de transportadora é assunto
    da administração, e não segura a separação."""
    carregamento = await seed_carregamento()
    pedido = await seed_pedido_parado(
        status=StatusPedido.EM_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    await _abrir_ocorrencia(db_session, pedido.id, carregamento.transportadora_id)

    avancados = await avancar_parados(db_session, datetime.now(UTC), 180)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_COLETA.value


# ── Frota própria: a coleta da rede de segurança também anexa um carregamento
# ao pedido que não tem, para o mapa do aluno andar. ───────────────────────


async def _carregamentos(db_session):
    from sqlalchemy import select

    from app.models.carregamento import Carregamento

    resultado = await db_session.execute(select(Carregamento).order_by(Carregamento.id))
    return list(resultado.scalars().all())


async def test_the_collect_hop_attaches_an_own_fleet_shipment(
    db_session, monkeypatch, _stub_publish_event
):
    """Mesma frota própria da coleta manual, com uma diferença honesta:
    `criado_por` é o UUID nulo (`CRIADO_PELO_SISTEMA`), não um id de pessoa —
    a coluna é NOT NULL e ninguém coletou."""
    import uuid
    from decimal import Decimal

    from app.models.pedido import Order
    from app.services.directions import DirectionsResult
    from app.services.posicao import ultima_posicao
    from app.services.simulador_posicao import avancar_carregamentos

    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.AGUARDANDO_COLETA.value,
        total=Decimal("1299.90"),
        status_updated_at=datetime.now(UTC) - timedelta(minutes=20),
        ship_street="Rua das Flores",
        ship_number="42",
        ship_city="Jundiaí",
        ship_state="SP",
        origem_rotulo="Leroy Merlin Marginal Tietê",
        origem_lat=Decimal("-23.518300"),
        origem_lng=Decimal("-46.627600"),
    )
    db_session.add(pedido)
    await db_session.commit()
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")

    async def fake_fetch(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="60 km",
            distance_km=60.0,
            duration_text="50 min",
            duration_minutes=50,
            destination_latitude=-23.185700,
            destination_longitude=-46.897800,
        )

    monkeypatch.setattr("app.services.posicao.directions.fetch_directions", fake_fetch)

    avancados = await avancar_parados(db_session, datetime.now(UTC), 180)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_TRANSITO.value
    [lote] = await _carregamentos(db_session)
    assert pedido.carregamento_id == lote.id
    assert pedido.carrier_name == "Frota própria Edu"
    assert pedido.deliverer_id is None
    assert lote.criado_por == uuid.UUID(int=0)
    assert (lote.origem_lat, lote.origem_lng) == (pedido.origem_lat, pedido.origem_lng)
    assert pedido.destino_lat == Decimal("-23.185700")
    assert [chave for chave, _ in _stub_publish_event] == ["order.status_changed"]

    assert await avancar_carregamentos(db_session, datetime.now(UTC)) == 1
    assert await ultima_posicao(db_session, lote.id) is not None


async def test_the_collect_hop_keeps_the_shipment_an_order_already_has(
    db_session, seed_carregamento, _stub_publish_event
):
    carregamento = await seed_carregamento()
    pedido = await _seed_pronto_para_coleta(db_session, carregamento.id, timedelta(minutes=20))

    await avancar_parados(db_session, datetime.now(UTC), 180)

    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_TRANSITO.value
    assert pedido.carregamento_id == carregamento.id
    assert [lote.id for lote in await _carregamentos(db_session)] == [carregamento.id]
