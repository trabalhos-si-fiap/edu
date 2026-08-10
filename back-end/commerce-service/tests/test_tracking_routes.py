"""Testes de endpoint do rastreio de pedido: tela de rastreio, rota no mapa
e previsão de ETA.

Porte de `legacy/tests/test_tracking_routes.py`. A C8 portou os cinco
testes de `GET /orders/{id}/tracking` (arquivo antes "PARCIAL" — ver
task-C8-report.md); esta task (C9) completa o arquivo com os 9 de 14 que
faltavam: `predict-eta` (4) e `GET /orders/{id}/route` (5).

Adaptações: sem prefixo `/api`; autenticação via header `Authorization:
Bearer <jwt>` (`edu_common.security.create_access_token`), não via
`app.dependency_overrides[get_current_user]` como no legacy — este serviço
não tem uma tabela de usuários própria, o `sub` do token é o `user_id`
direto. Ids de pedido são `uuid.UUID` no path (não string opaca como no
legacy), então um id malformado nunca chega ao service: cai na validação
do FastAPI e vira 422, não 404 — ver
`test_get_order_tracking_malformed_id_returns_422` (C8, `/tracking`) e
`test_get_order_route_malformed_id_raises` em
`tests/test_tracking_services.py` (C9, `/route`) — a mesma divergência,
registrada nos dois lugares.

`predict-eta` diverge do legacy de propósito (divergência deliberada nº 6,
decisão do usuário de 2026-08-08): aqui ele checa ownership do pedido antes
de calcular a ETA — o legacy nunca carrega o pedido, então qualquer aluno
autenticado podia pedir a ETA de um `order_id` alheio ou inexistente. Os
testes `test_predict_eta_unknown_order_returns_404` e
`test_predict_eta_foreign_order_returns_404` abaixo não têm equivalente no
legacy — são desta task.
"""

import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token
from loguru import logger

from app.config import settings
from app.exceptions import RouteUnavailableError
from app.models.pedido import Order, OrderItem
from app.models.produto import Product
from app.services.directions import DirectionsResult
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str) -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


# Aluno fixo usado pelos testes que só precisam de UM dono consistente
# (ex.: a prova de vazamento do Step 8) — os demais testes geram um
# `uuid.uuid4()` novo por teste, como o resto do arquivo já fazia.
ALUNO = str(uuid.uuid4())


async def _tracked_order(
    db_session, aluno_id: str, status: str = StatusPedido.EM_SEPARACAO.value
) -> Order:
    """Pedido persistido, em andamento, de propriedade de `aluno_id`.

    `order_items.product_id` tem FK para `products` (medido rodando o Red
    desta suíte contra o Postgres real: um `uuid.uuid4()` solto, como o
    legacy usa, estoura `IntegrityError` — mesmo achado já documentado em
    `test_orders_routes.py::test_order_item_snapshots_the_product`). Por
    isso semeia um `Product` real antes do item.

    `status` é `EM_SEPARACAO` por padrão (o que os testes existentes
    esperavam); testes que precisam de outro estado (ex.: `CANCELADO`,
    para o campo `status` do rastreio) passam o valor explicitamente.
    """
    produto = Product(name="Apostila Ed. 5.0", price=Decimal("100.00"), type="apostila")
    db_session.add(produto)
    await db_session.flush()

    order = Order(
        user_id=aluno_id,
        total=Decimal("100.00"),
        payment_method="pix",
        status=status,
        items=[
            OrderItem(
                product_id=produto.id,
                product_name="Apostila Ed. 5.0",
                unit_price=Decimal("100.00"),
                quantity=1,
            )
        ],
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


async def _seed_pedido_com_endereco(db_session, user_id: str) -> Order:
    """Pedido persistido, de propriedade de `user_id`, COM snapshot de
    endereço de entrega — o que `_tracked_order` acima não tem, e o que
    `GET /orders/{id}/route` precisa para gerar uma rota (um pedido sem
    endereço é 503, não 404 — ver `test_get_order_route_without_address_returns_503`).
    """
    produto = Product(name="Apostila", price=Decimal("100.00"), type="apostila")
    db_session.add(produto)
    await db_session.flush()

    order = Order(
        user_id=user_id,
        total=Decimal("100.00"),
        payment_method="pix",
        status=StatusPedido.EM_TRANSITO.value,
        ship_label="Casa",
        ship_zip_code="13201-005",
        ship_street="Rua das Flores",
        ship_number="42",
        ship_complement="Apto 3",
        ship_neighborhood="Centro",
        ship_city="Jundiaí",
        ship_state="SP",
        items=[
            OrderItem(
                product_id=produto.id,
                product_name="Apostila",
                unit_price=Decimal("100.00"),
                quantity=1,
            )
        ],
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


async def test_get_order_tracking_requires_auth(client) -> None:
    resp = await client.get(f"/orders/{uuid.uuid4()}/tracking")
    assert resp.status_code == 403


async def test_get_order_tracking_matches_flutter_contract(client, db_session) -> None:
    aluno_id = str(uuid.uuid4())
    order = await _tracked_order(db_session, aluno_id)

    resp = await client.get(
        f"/orders/{order.id}/tracking", headers=headers_for("student", aluno_id)
    )
    assert resp.status_code == 200

    body = resp.json()
    # Exatamente as chaves que `OrderModel.fromJson` lê
    # (front-end-flutter/lib/features/order_tracking/domain/order_model.dart).
    # `status` é divergência deliberada nº 7: o legacy não tem esse campo no
    # payload de rastreio (ver docs/back-end/commerce-parity.md).
    assert set(body) == {
        "id",
        "headline",
        "description",
        "estimated_arrival",
        "steps",
        "location",
        "kit",
        "carrier",
        "map_url",
        "status",
    }
    assert body["id"] == str(order.id)
    assert body["carrier"]
    # A timeline reflete o status real: EM_SEPARACAO -> contrato 'separating',
    # que é o passo corrente.
    steps = {s["code"]: s["status"] for s in body["steps"]}
    assert steps["separating"] == "current"
    assert steps["confirmed"] == "done"
    assert steps["out_for_delivery"] == "pending"
    # O kit é os itens reais do pedido.
    assert [k["name"] for k in body["kit"]] == ["Apostila Ed. 5.0"]

    raw_steps = body["steps"]
    assert {s["status"] for s in raw_steps} <= {"done", "current", "pending"}
    assert all({"code", "title", "status", "timestamp"} == set(s) for s in raw_steps)

    assert set(body["location"]) == {"name", "city", "state", "updated_at"}
    assert all(set(item) == {"name", "subtitle"} for item in body["kit"])


async def test_get_order_tracking_of_a_cancelled_order_returns_cancelled_status(
    client, db_session
) -> None:
    """Divergência deliberada nº 7: o campo `status` é o que o Flutter usa
    para parar o polling de rastreio de um pedido cancelado (a timeline
    inteira fica PENDING nesse caso, então `isDelivered` nunca vira
    verdadeiro sozinho — ver `order_provider.dart`)."""
    aluno_id = str(uuid.uuid4())
    order = await _tracked_order(db_session, aluno_id, status=StatusPedido.CANCELADO.value)

    resp = await client.get(
        f"/orders/{order.id}/tracking", headers=headers_for("student", aluno_id)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_get_order_tracking_unknown_order_returns_404(client) -> None:
    resp = await client.get(
        f"/orders/{uuid.uuid4()}/tracking", headers=headers_for("student", str(uuid.uuid4()))
    )
    assert resp.status_code == 404


async def test_get_order_tracking_malformed_id_returns_422(client) -> None:
    """Diferente do legacy (404): aqui `order_id: uuid.UUID` é o TIPO do path
    param, então o FastAPI rejeita um id não-UUID antes de chegar ao
    handler — mesmo padrão já coberto para `GET /orders/{id}` em
    `test_a_malformed_order_id_is_a_422_not_a_500` (test_orders_routes.py)."""
    resp = await client.get(
        "/orders/ED-99420/tracking", headers=headers_for("student", str(uuid.uuid4()))
    )
    assert resp.status_code == 422


async def test_get_order_tracking_other_users_order_returns_404(client, db_session) -> None:
    # Um pedido de outra pessoa tem que ser indistinguível de inexistente.
    owner = str(uuid.uuid4())
    stranger = str(uuid.uuid4())
    order = await _tracked_order(db_session, owner)

    resp = await client.get(
        f"/orders/{order.id}/tracking", headers=headers_for("student", stranger)
    )
    assert resp.status_code == 404


async def test_tracking_and_status_history_hit_different_routes(client, db_session) -> None:
    """Substitui o `curl` manual do Step 5 do brief: sem stack no ar para
    bater com curl (e subir uma é proibido nesta task), a prova equivalente
    é golpear os dois paths pelo `client` da suíte e conferir que cada um
    cai no handler certo — `/tracking` devolve o objeto de rastreio (dict
    com `steps`/`kit`/`location`), `/status-history` devolve a lista de
    histórico."""
    aluno_id = str(uuid.uuid4())
    order = await _tracked_order(db_session, aluno_id)
    headers = headers_for("student", aluno_id)

    tracking = await client.get(f"/orders/{order.id}/tracking", headers=headers)
    assert tracking.status_code == 200
    assert isinstance(tracking.json(), dict)
    assert set(tracking.json()) >= {"headline", "steps", "location", "kit"}

    historico = await client.get(f"/orders/{order.id}/status-history", headers=headers)
    assert historico.status_code == 200
    assert isinstance(historico.json(), list)


# --- predict-eta ---------------------------------------------------------


async def test_predict_eta_requires_auth(client) -> None:
    resp = await client.post(
        f"/orders/{uuid.uuid4()}/predict-eta",
        json={"latitude": -23.55, "longitude": -46.63},
    )
    assert resp.status_code == 403


async def test_predict_eta_happy_path(client, db_session) -> None:
    aluno_id = str(uuid.uuid4())
    order = await _tracked_order(db_session, aluno_id)

    # ~2 km do destino mockado.
    resp = await client.post(
        f"/orders/{order.id}/predict-eta",
        json={"latitude": -23.5750, "longitude": -46.6500},
        headers=headers_for("student", aluno_id),
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["eta_minutes"] >= 1
    assert body["eta_text"].endswith("min")
    # O fator de rota urbana torna a distância percorrida maior que a linha reta.
    assert body["distance_km"] > body["straight_line_distance_km"]
    assert body["traffic_level"] in {"light", "moderate", "heavy"}
    assert body["route_status"] in {"en_route", "nearby", "arrived"}
    assert body["destination_location"] == {
        "latitude": -23.561414,
        "longitude": -46.655881,
    }


async def test_predict_eta_at_destination_is_arrived(client, db_session) -> None:
    aluno_id = str(uuid.uuid4())
    order = await _tracked_order(db_session, aluno_id)

    resp = await client.post(
        f"/orders/{order.id}/predict-eta",
        json={"latitude": -23.561414, "longitude": -46.655881},
        headers=headers_for("student", aluno_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_status"] == "arrived"
    assert body["eta_minutes"] == 0
    assert body["eta_text"] == "chegando"


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": 91.0, "longitude": 0.0},  # latitude fora do intervalo
        {"latitude": 0.0, "longitude": 200.0},  # longitude fora do intervalo
        {"latitude": 0.0},  # longitude faltando
        {"latitude": 0.0, "longitude": 0.0, "extra": 1},  # campo extra proibido
    ],
)
async def test_predict_eta_validates_payload(client, payload: dict) -> None:
    # A validação do corpo roda antes do handler — nem precisa de pedido
    # existente para reprovar um payload malformado.
    resp = await client.post(
        f"/orders/{uuid.uuid4()}/predict-eta",
        json=payload,
        headers=headers_for("student", str(uuid.uuid4())),
    )
    assert resp.status_code == 422


async def test_predict_eta_unknown_order_returns_404(client) -> None:
    """Divergência deliberada nº 6 (decisão do usuário, 2026-08-08; não
    portada do legacy — lá `predict_eta` nunca carrega o pedido, então
    qualquer `order_id`, mesmo inexistente, respondia 200). Aqui
    `services.prever_eta` chama `buscar_pedido` antes de calcular, então um
    pedido inexistente vira 404, igual ao resto da API."""
    resp = await client.post(
        f"/orders/{uuid.uuid4()}/predict-eta",
        json={"latitude": -23.55, "longitude": -46.63},
        headers=headers_for("student", str(uuid.uuid4())),
    )
    assert resp.status_code == 404


async def test_predict_eta_foreign_order_returns_404(client, db_session) -> None:
    """Mesma divergência nº 6: um pedido de outro aluno tem que ser
    indistinguível de inexistente (regra 2 do CLAUDE.md), como em todo o
    resto da API. Sem equivalente no legacy — é desta task."""
    owner = str(uuid.uuid4())
    stranger = str(uuid.uuid4())
    order = await _tracked_order(db_session, owner)

    resp = await client.post(
        f"/orders/{order.id}/predict-eta",
        json={"latitude": -23.55, "longitude": -46.63},
        headers=headers_for("student", stranger),
    )
    assert resp.status_code == 404


# --- GET /orders/{id}/route ------------------------------------------------


async def test_get_order_route_requires_auth(client) -> None:
    resp = await client.get(f"/orders/{uuid.uuid4()}/route")
    assert resp.status_code == 403


async def test_get_order_route_happy_path(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    aluno_id = str(uuid.uuid4())
    order = await _seed_pedido_com_endereco(db_session, aluno_id)
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")

    async def fake_fetch(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="32 km",
            distance_km=32.0,
            duration_text="48 min",
            duration_minutes=48,
            destination_latitude=-23.1857,
            destination_longitude=-46.8978,
        )

    monkeypatch.setattr("app.services.rastreio.directions.fetch_directions", fake_fetch)

    resp = await client.get(f"/orders/{order.id}/route", headers=headers_for("student", aluno_id))
    assert resp.status_code == 200

    body = resp.json()
    assert set(body) == {
        "origin",
        "destination",
        "polyline",
        "distance_text",
        "distance_km",
        "duration_text",
        "duration_minutes",
    }
    assert set(body["origin"]) == {"label", "latitude", "longitude"}
    assert body["polyline"] == "enc-poly"
    assert body["origin"]["label"] == "Centro de Distribuição"
    assert body["destination"]["latitude"] == -23.1857
    assert body["destination"]["longitude"] == -46.8978
    assert body["duration_minutes"] == 48


async def test_get_order_route_unavailable_returns_503(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Falha do provedor vira RouteUnavailableError; a rota tem que mapear
    # isso para um 503 limpo, nunca um 500. Aqui a chave do Maps não está
    # configurada.
    aluno_id = str(uuid.uuid4())
    order = await _seed_pedido_com_endereco(db_session, aluno_id)
    monkeypatch.setattr(settings, "google_maps_api_key", "")

    resp = await client.get(f"/orders/{order.id}/route", headers=headers_for("student", aluno_id))
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Rota indisponível no momento"


async def test_get_order_route_unknown_order_returns_404(client) -> None:
    resp = await client.get(
        f"/orders/{uuid.uuid4()}/route", headers=headers_for("student", str(uuid.uuid4()))
    )
    assert resp.status_code == 404


async def test_get_order_route_without_address_returns_503(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _tracked_order não tem snapshot ship_* -> nada para rotear.
    aluno_id = str(uuid.uuid4())
    order = await _tracked_order(db_session, aluno_id)
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")
    resp = await client.get(f"/orders/{order.id}/route", headers=headers_for("student", aluno_id))
    assert resp.status_code == 503


async def test_get_order_route_cached_by_owner_is_not_served_to_a_stranger(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regressão do achado Important 2 da rodada de correção 1: o cache de
    rota tem que ficar atrás da checagem de ownership (`buscar_pedido`),
    nunca na frente dela. Popula o cache como o DONO primeiro, depois pede a
    mesma rota como um ESTRANHO — a resposta tem que ser 404, com o mesmo
    corpo de um pedido inexistente, cache ou não.

    Sob a reordenação que o revisor testou (bloco de cache movido para ANTES
    de `buscar_pedido` em `app/services/rastreio.py`), este teste FALHA: o
    estranho recebe 200 com a rota do dono. Ver task-C9-report.md, "Rodada
    de correção 1", achado Important 2, para as duas rodadas medidas
    (mutado e revertido).
    """
    owner = str(uuid.uuid4())
    stranger = str(uuid.uuid4())
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")
    order = await _seed_pedido_com_endereco(db_session, user_id=owner)

    async def fake_fetch(client, *, origin, destination, api_key):
        return DirectionsResult(
            polyline="enc-poly",
            distance_text="32 km",
            distance_km=32.0,
            duration_text="48 min",
            duration_minutes=48,
            destination_latitude=-23.1857,
            destination_longitude=-46.8978,
        )

    monkeypatch.setattr("app.services.rastreio.directions.fetch_directions", fake_fetch)

    # O dono pede a rota primeiro — isso popula o cache.
    owner_resp = await client.get(
        f"/orders/{order.id}/route", headers=headers_for("student", owner)
    )
    assert owner_resp.status_code == 200

    # O estranho pede a MESMA rota depois. Tem que ser indistinguível de um
    # pedido que nunca existiu.
    stranger_resp = await client.get(
        f"/orders/{order.id}/route", headers=headers_for("student", stranger)
    )
    unknown_resp = await client.get(
        f"/orders/{uuid.uuid4()}/route", headers=headers_for("student", stranger)
    )
    assert stranger_resp.status_code == 404
    assert stranger_resp.json() == unknown_resp.json()


async def test_route_503_never_echoes_the_provider_detail(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova da constraint 11 do CLAUDE.md (comparação em tempo constante é
    outra regra — esta é "nenhum segredo vaza"): o handler de
    `RouteUnavailableError` sempre devolve o detail genérico "Rota
    indisponível no momento", nunca `str(exc)` — que pode carregar a chave
    da API ou o endereço completo do pedido. Prova por mutação: ver
    task-C9-report.md para as duas rodadas (com e sem a guarda)."""
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")
    pedido = await _seed_pedido_com_endereco(db_session, user_id=ALUNO)

    async def _falha(*args, **kwargs):
        raise RouteUnavailableError("directions status: REQUEST_DENIED key=SEGREDO")

    monkeypatch.setattr("app.services.rastreio.directions.fetch_directions", _falha)

    response = await client.get(
        f"/orders/{pedido.id}/route", headers=headers_for("student", sub=ALUNO)
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Rota indisponível no momento"
    assert "SEGREDO" not in response.text


async def test_route_503_never_logs_the_provider_detail(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Minor promovido 4, rodada de correção 1: estende a prova acima (corpo
    da resposta) para o LOG, que é a propriedade que o usuário nomeou como a
    mais importante da C9 — nada do provedor de mapas pode chegar ao
    cliente, nem no corpo do 503, nem em log, nem encadeado em `__cause__`,
    porque o texto de erro do Google pode carregar a chave da API ou o
    endereço completo do aluno.

    O revisor acrescentou `logger.error("...", str(exc))` ao handler de
    `RouteUnavailableError` em `app/routers/rastreio.py` e os 34 testes de
    tracking existentes passaram — nenhum deles olhava o log, só
    `response.text`. Este teste fecha esse buraco anexando um sink temporário
    ao `loguru.logger` (o app não configura nenhum sink de captura por
    padrão) durante a requisição.
    """
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key")
    pedido = await _seed_pedido_com_endereco(db_session, user_id=ALUNO)

    async def _falha(*args, **kwargs):
        raise RouteUnavailableError("directions status: REQUEST_DENIED key=SEGREDO_LOG")

    monkeypatch.setattr("app.services.rastreio.directions.fetch_directions", _falha)

    log_lines: list[str] = []
    sink_id = logger.add(lambda message: log_lines.append(str(message)), level="DEBUG")
    try:
        response = await client.get(
            f"/orders/{pedido.id}/route", headers=headers_for("student", sub=ALUNO)
        )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 503
    assert not any("SEGREDO_LOG" in line for line in log_lines)
