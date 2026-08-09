"""Testes de endpoint do rastreio de pedido.

Porte PARCIAL de `legacy/tests/test_tracking_routes.py` (task C8): o
arquivo legacy também cobre `predict-eta` e `GET /orders/{id}/route`, que
são construídos pela task C9 (rota e ETA) — não existem ainda neste
serviço. Só os cinco testes de `GET /orders/{id}/tracking` foram portados;
ver task-C8-report.md para a lista nominal do que ficou para a C9.

Adaptações: sem prefixo `/api`; autenticação via header `Authorization:
Bearer <jwt>` (`edu_common.security.create_access_token`), não via
`app.dependency_overrides[get_current_user]` como no legacy — este serviço
não tem uma tabela de usuários própria, o `sub` do token é o `user_id`
direto. Ids de pedido são `uuid.UUID` no path (não string opaca como no
legacy), então um id malformado nunca chega ao service: cai na validação
do FastAPI e vira 422, não 404 — ver
`test_get_order_tracking_malformed_id_returns_422` abaixo.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Order, OrderItem
from app.models.produto import Product
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str) -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _tracked_order(db_session, aluno_id: str) -> Order:
    """Pedido persistido, em andamento, de propriedade de `aluno_id`.

    `order_items.product_id` tem FK para `products` (medido rodando o Red
    desta suíte contra o Postgres real: um `uuid.uuid4()` solto, como o
    legacy usa, estoura `IntegrityError` — mesmo achado já documentado em
    `test_orders_routes.py::test_order_item_snapshots_the_product`). Por
    isso semeia um `Product` real antes do item.
    """
    produto = Product(name="Apostila Ed. 5.0", price=Decimal("100.00"), type="apostila")
    db_session.add(produto)
    await db_session.flush()

    order = Order(
        user_id=aluno_id,
        total=Decimal("100.00"),
        payment_method="pix",
        status=StatusPedido.EM_SEPARACAO.value,
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
