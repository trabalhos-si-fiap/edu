import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Order
from app.services.directions import DirectionsResult
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
    for _i in range(total):
        db_session.add(
            Order(
                user_id=str(uuid.uuid4()),
                status=StatusPedido.AGUARDANDO_COLETA.value,
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


async def test_a_deliverer_user_still_collects_the_old_way(client, db_session):
    """O papel `entregador` deixa de ser o caminho normal, mas não morre: a
    spec A seeda uma conta com ele, e a suíte de entrega inteira depende
    dele. Esta task não pode quebrar esse caminho."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", DELIVERER_A)
    )

    assert response.status_code == 200


async def test_delivery_mine_actually_applies_limit_and_offset(client, db_session):
    total = 55
    for _i in range(total):
        db_session.add(
            Order(
                user_id=str(uuid.uuid4()),
                status=StatusPedido.EM_TRANSITO.value,
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


# ── Fix round 1 (reviewer, Important): a fábrica `ator_de_entrega` devolve
# cada rota ao conjunto de papéis de usuário que ela já tinha ANTES desta
# task — admin só em `queue`, nunca em `collect`/`deliver`/`mine`. ─────────


async def test_admin_is_refused_on_collect(client, db_session):
    """Antes desta spec, `PATCH /delivery/{id}/collect` era
    `requer_papel("entregador")` só — admin nunca pôde reivindicar um
    pedido por aqui (o caminho de admin é
    `/admin/orders/{id}/assign-deliverer`). Um token admin passando por
    `ator_de_entrega("entregador")` não pode reabrir essa porta."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("admin", ADMIN)
    )

    assert response.status_code == 403


async def test_admin_is_refused_on_deliver(client, db_session):
    """Mesma razão de `test_admin_is_refused_on_collect`:
    `PATCH /delivery/{id}/deliver` também excluía admin antes desta task."""
    pedido = await _seed_pedido(
        db_session, StatusPedido.EM_TRANSITO.value, entregador_id=DELIVERER_A
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/deliver", headers=headers_for("admin", ADMIN)
    )

    assert response.status_code == 403


async def test_admin_is_still_accepted_on_queue(client, db_session):
    """`GET /delivery/queue` sempre aceitou admin (`requer_papel("entregador",
    "admin")`, antes desta spec) — prova que o fix devolveu cada rota ao seu
    conjunto original, em vez de banir admin de todo `/delivery`."""
    await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    response = await client.get("/delivery/queue", headers=headers_for("admin", ADMIN))

    assert response.status_code == 200


# ── Task 6: `collect` congela `orders.destino_lat/lng` via `congelar_destino`
# — uma vez, e nunca bloqueando a coleta. ──────────────────────────────────


async def _seed_pedido_com_endereco_e_carregamento(
    db_session, carregamento_id: int, status: str = StatusPedido.AGUARDANDO_COLETA.value
) -> Order:
    """Pedido pronto para coleta, com snapshot de endereço de entrega (o que
    `congelar_destino` precisa para montar o destino geocodificável) e já
    associado a um carregamento com origem congelada (o que
    `seed_carregamento` já garante)."""
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=status,
        total=Decimal("100.00"),
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


async def test_collect_freezes_the_destination_when_directions_succeeds(
    client, db_session, monkeypatch, seed_carregamento
):
    """Prova positiva de `congelar_destino`: a coleta grava `destino_lat/lng`
    a partir da resposta (remendada) da Google Directions — o caminho feliz
    que os demais testes de `/collect` não exercitam porque não configuram
    `google_maps_api_key`."""
    carregamento = await seed_carregamento()
    pedido = await _seed_pedido_com_endereco_e_carregamento(db_session, carregamento.id)
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

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200

    await db_session.refresh(pedido)
    assert pedido.destino_lat == Decimal("-23.185700")
    assert pedido.destino_lng == Decimal("-46.897800")


async def test_collect_never_fails_when_the_provider_is_unreachable(
    client, db_session, monkeypatch, seed_carregamento
):
    """`congelar_destino` nunca levanta (constraint global da task 6): mesmo
    com a chave configurada e o endereço presente, uma falha ao alcançar a
    Google — aqui, o bloqueio estrutural de rede real de
    `conftest.py::_block_real_network_calls`, que nenhum monkeypatch de
    `fetch_directions` neutraliza neste teste de propósito — não pode
    derrubar a coleta. O pedido só fica sem destino."""
    carregamento = await seed_carregamento()
    pedido = await _seed_pedido_com_endereco_e_carregamento(db_session, carregamento.id)
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200

    await db_session.refresh(pedido)
    assert pedido.destino_lat is None


async def test_collect_never_fails_when_the_provider_returns_an_unusable_coordinate(
    client, db_session, monkeypatch, seed_carregamento
):
    """Fix round 1 (Important, plan-mandated): a resposta da Google pode
    formalmente ter `status: OK` e ainda assim carregar um valor que não vira
    `Decimal` — a conversão em `congelar_destino` estourava
    `decimal.InvalidOperation` FORA do `try`, e a coleta virava um 500 para um
    pedido que, na verdade, já tinha sido coletado (`transicionar_pedido` já
    tinha commitado antes de `congelar_destino` rodar). `congelar_destino`
    promete nunca levantar; este teste força o pior caso do lado de dentro do
    próprio parsing, não só da chamada de rede."""
    carregamento = await seed_carregamento()
    pedido = await _seed_pedido_com_endereco_e_carregamento(db_session, carregamento.id)
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")

    async def fake_fetch_valor_invalido(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="10 km",
            distance_km=10.0,
            duration_text="20 min",
            duration_minutes=20,
            destination_latitude="não é número",
            destination_longitude=-46.897800,
        )

    monkeypatch.setattr(
        "app.services.posicao.directions.fetch_directions", fake_fetch_valor_invalido
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200

    await db_session.refresh(pedido)
    assert pedido.destino_lat is None


# ── Frota própria: a coleta de um pedido SEM carregamento cria um, para o
# destino ser congelado e o marcador do entregador andar no mapa do aluno —
# sem o admin cadastrar transportadora, criar lote e digitar o id do pedido.


ORIGEM_LEROY = ("Leroy Merlin Marginal Tietê", Decimal("-23.518300"), Decimal("-46.627600"))
DESTINO_ALUNO = (-23.185700, -46.897800)


async def _seed_pedido_sem_carregamento(
    db_session, status: str = StatusPedido.AGUARDANDO_COLETA.value
) -> Order:
    """Pedido como o checkout da spec B o deixa: origem congelada do parceiro,
    snapshot de endereço, e nenhum carregamento."""
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=status,
        total=Decimal("1299.90"),
        ship_label="Casa",
        ship_zip_code="13201-005",
        ship_street="Rua das Flores",
        ship_number="42",
        ship_neighborhood="Centro",
        ship_city="Jundiaí",
        ship_state="SP",
        origem_rotulo=ORIGEM_LEROY[0],
        origem_lat=ORIGEM_LEROY[1],
        origem_lng=ORIGEM_LEROY[2],
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _carregamentos(db_session):
    from sqlalchemy import select

    from app.models.carregamento import Carregamento

    resultado = await db_session.execute(select(Carregamento).order_by(Carregamento.id))
    return list(resultado.scalars().all())


def _directions_que_anota(origens: list) -> object:
    async def fake_fetch(client, *, origin, destination, api_key):
        origens.append(origin)
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="60 km",
            distance_km=60.0,
            duration_text="50 min",
            duration_minutes=50,
            destination_latitude=DESTINO_ALUNO[0],
            destination_longitude=DESTINO_ALUNO[1],
        )

    return fake_fetch


async def test_collect_without_a_shipment_attaches_one_from_the_own_fleet(
    client, db_session, _stub_publish_event
):
    from app.models.transportadora import Carrier, CarrierStatus
    from app.services.carregamentos import ALFABETO_CODIGO, TAMANHO_CODIGO

    pedido = await _seed_pedido_sem_carregamento(db_session)

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == StatusPedido.EM_TRANSITO.value
    await db_session.refresh(pedido)
    [lote] = await _carregamentos(db_session)
    assert pedido.carregamento_id == lote.id
    assert pedido.carrier_name == "Frota própria Edu"
    assert (lote.origem_rotulo, lote.origem_lat, lote.origem_lng) == ORIGEM_LEROY
    assert lote.criado_por == uuid.UUID(DELIVERER_A)
    assert lote.aberto_em is not None
    assert len(lote.codigo) == TAMANHO_CODIGO
    assert set(lote.codigo) <= set(ALFABETO_CODIGO)
    assert lote.senha_hash.startswith("$2")

    frota = await db_session.get(Carrier, lote.transportadora_id)
    assert frota.name == "Frota própria Edu"
    assert frota.status == CarrierStatus.ACTIVE.value

    # A coleta publica o que sempre publicou. `shipment.created` NÃO sai: ele
    # mandaria por e-mail uma credencial a uma transportadora que não existe.
    assert [chave for chave, _ in _stub_publish_event] == ["order.status_changed"]


async def test_own_fleet_shipment_records_who_collected_it_from_the_token(
    client, db_session, _stub_publish_event
):
    """O painel mostra em "RETIRADA" quem pegou a carga. Num lote do admin
    quem grava é o login do lote; na frota própria não há esse login, então o
    nome vem do token de quem coletou — sem ele o painel mostrava "— · data".
    Token emitido antes da claim continua coletando, só sem nome."""
    pedido = await _seed_pedido_sem_carregamento(db_session)
    antigo = await _seed_pedido_sem_carregamento(db_session)
    token = create_access_token(
        DELIVERER_A, "entregador", settings.jwt_secret, nome="Entregador Demo"
    )

    com_nome = await client.patch(
        f"/delivery/{pedido.id}/collect", headers={"Authorization": f"Bearer {token}"}
    )
    sem_nome = await client.patch(
        f"/delivery/{antigo.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )

    assert com_nome.status_code == 200, com_nome.text
    assert sem_nome.status_code == 200, sem_nome.text
    lotes = {lote.id: lote for lote in await _carregamentos(db_session)}
    await db_session.refresh(pedido)
    await db_session.refresh(antigo)
    assert lotes[pedido.carregamento_id].entregador_nome == "Entregador Demo"
    assert lotes[antigo.carregamento_id].entregador_nome is None


async def test_an_own_fleet_shipment_moves_the_courier_on_the_students_map(
    client, db_session, monkeypatch, _stub_publish_event
):
    """O ponto da tarefa, de ponta a ponta: com carregamento, `congelar_destino`
    parte da origem do pedido, o simulador grava posição, e o rastreio do
    aluno mostra o entregador e o nome da frota."""
    from app.services.posicao import ultima_posicao
    from app.services.simulador_posicao import avancar_carregamentos

    pedido = await _seed_pedido_sem_carregamento(db_session)
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")
    origens: list = []
    monkeypatch.setattr(
        "app.services.posicao.directions.fetch_directions", _directions_que_anota(origens)
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(pedido)
    assert origens == [(float(ORIGEM_LEROY[1]), float(ORIGEM_LEROY[2]))]
    assert pedido.destino_lat == Decimal("-23.185700")

    from datetime import UTC, datetime, timedelta

    assert await avancar_carregamentos(db_session, datetime.now(UTC) + timedelta(minutes=3)) == 1
    posicao = await ultima_posicao(db_session, pedido.carregamento_id)
    assert posicao is not None
    # Entre a origem e o destino (Jundiaí fica ao norte da Marginal Tietê).
    assert ORIGEM_LEROY[1] < posicao.lat < Decimal(str(DESTINO_ALUNO[0]))

    rastreio = await client.get(
        f"/orders/{pedido.id}/tracking", headers=headers_for("student", sub=str(pedido.user_id))
    )
    assert rastreio.status_code == 200, rastreio.text
    assert rastreio.json()["carrier"] == "Frota própria Edu"
    assert rastreio.json()["courier_position"] is not None


async def test_every_own_fleet_shipment_shares_one_carrier(client, db_session):
    """Um lote por pedido (o simulador interpola para UM destino por lote),
    mas uma transportadora só — criada na primeira coleta, sem seed."""
    from sqlalchemy import func, select

    from app.models.transportadora import Carrier

    primeiro = await _seed_pedido_sem_carregamento(db_session)
    segundo = await _seed_pedido_sem_carregamento(db_session)

    for pedido in (primeiro, segundo):
        response = await client.patch(
            f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
        )
        assert response.status_code == 200, response.text

    lotes = await _carregamentos(db_session)
    assert len(lotes) == 2
    assert lotes[0].transportadora_id == lotes[1].transportadora_id
    total = await db_session.scalar(
        select(func.count()).select_from(Carrier).where(Carrier.name == "Frota própria Edu")
    )
    assert total == 1


async def test_collect_keeps_the_shipment_an_order_already_has(
    client, db_session, seed_carregamento
):
    """O caminho de antes não muda: o lote que o admin montou continua sendo o
    lote do pedido, e nenhuma frota própria é criada."""
    from sqlalchemy import func, select

    from app.models.transportadora import Carrier

    carregamento = await seed_carregamento()
    pedido = await _seed_pedido_com_endereco_e_carregamento(db_session, carregamento.id)

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )

    assert response.status_code == 200, response.text
    await db_session.refresh(pedido)
    assert pedido.carregamento_id == carregamento.id
    assert [lote.id for lote in await _carregamentos(db_session)] == [carregamento.id]
    assert await db_session.scalar(select(func.count()).select_from(Carrier)) == 1


async def test_a_refused_collect_leaves_no_shipment_behind(client, db_session):
    pedido = await _seed_pedido_sem_carregamento(
        db_session, status=StatusPedido.AGUARDANDO_SEPARACAO.value
    )

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )

    assert response.status_code == 400
    assert await _carregamentos(db_session) == []


async def test_a_colliding_own_fleet_code_is_drawn_again(
    client, db_session, monkeypatch, seed_carregamento
):
    """A colisão de `codigo` é pega pelo índice único, como em
    `criar_carregamento` — mas aqui dentro da transação da coleta, que já
    segura o lock do pedido e já gravou `deliverer_id`. O re-sorteio não pode
    desfazer nada disso."""
    await seed_carregamento(codigo="ABCD2345")
    pedido = await _seed_pedido_sem_carregamento(db_session)
    sorteios = iter(["ABCD2345", "WXYZ6789"])
    monkeypatch.setattr("app.services.carregamentos.gerar_codigo", lambda: next(sorteios))

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", sub=DELIVERER_A)
    )

    assert response.status_code == 200, response.text
    await db_session.refresh(pedido)
    assert str(pedido.deliverer_id) == DELIVERER_A
    assert pedido.status == StatusPedido.EM_TRANSITO.value
    lote = next(lote for lote in await _carregamentos(db_session) if lote.codigo == "WXYZ6789")
    assert pedido.carregamento_id == lote.id


async def test_two_concurrent_collects_attach_one_shipment(client, db_session):
    """Regra 3 do CLAUDE.md: o lote é criado DEPOIS do `with_for_update()` do
    pedido, na mesma transação da transição. A segunda coleta espera o lock,
    relê o pedido já com carregamento e não cria outro."""
    import asyncio

    pedido = await _seed_pedido_sem_carregamento(db_session)
    url = f"/delivery/{pedido.id}/collect"

    respostas = await asyncio.wait_for(
        asyncio.gather(
            client.patch(url, headers=headers_for("entregador", sub=DELIVERER_A)),
            client.patch(url, headers=headers_for("entregador", sub=DELIVERER_A)),
        ),
        timeout=10,
    )

    assert sorted(r.status_code for r in respostas) == [200, 400]
    assert len(await _carregamentos(db_session)) == 1
