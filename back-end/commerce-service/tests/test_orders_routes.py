"""NOTA (task C6): este arquivo testava o contrato ANTIGO de `/orders`
(`POST /orders` com `{"itens": [...]}` fornecido pelo cliente, `GET
/orders/mine` para listagem) — o contrato que a task C6 apaga porque a
rota antiga compunha `valor_total` a partir do `preco_unitario` do
cliente, sem nunca importar o model de produto. `test_my_orders_*` foram
adaptados para bater em `GET /orders` (bare, sem `/mine`), e
`test_creating_an_order_publishes_a_serialisable_event` foi reescrito para
montar o pedido a partir do carrinho (o único jeito de criar um pedido
agora). `test_my_orders_requires_authentication` foi REMOVIDO: media
`GET /orders/mine`, que sem a rota `/mine` passa a casar com `GET
/orders/{order_id}` (`order_id="mine"`, um UUID inválido) — continuava
"passando" com 403, mas só porque a dependência de auth roda antes da
validação do path param, não porque provava o que o nome promete. A
cobertura real de "listar pedidos exige autenticação" já existe, portada
do legacy, em `test_orders_parity.py::TestAuthRequired::test_list_requires_auth`.
Ver task-C6-report.md para a lista completa de testes apagados/adaptados
e a razão de cada um."""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Order, OrderItem
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_create_order_requires_authentication(client):
    response = await client.post("/orders", json={"itens": []})
    assert response.status_code == 403


async def test_order_detail_requires_authentication(client):
    assert (await client.get("/orders/1")).status_code == 403


async def test_order_tracking_requires_authentication(client):
    assert (await client.get("/orders/1/tracking")).status_code == 403


async def test_order_status_history_requires_authentication(client):
    """Cobertura nova da task C8: `/status-history` é o path novo que herdou
    o histórico de `/tracking` — precisa da mesma trava de auth explícita
    que todo outro endpoint de pedido tem (regra 2 do CLAUDE.md)."""
    assert (await client.get("/orders/1/status-history")).status_code == 403


async def test_delivery_estimate_requires_authentication(client):
    assert (await client.get("/orders/1/delivery-estimate")).status_code == 403


async def test_old_portuguese_order_path_is_gone(client):
    assert (await client.get("/pedidos/meus")).status_code == 404


# ── Cobertura adicional — não pedida literalmente pelo brief, mas exigida
# pelo comportamento que a task 11 introduz nestas rotas (paginação em
# /orders/mine, ownership por user_id já preexistente) ──────────────────


async def _seed_pedido(db_session, aluno_id: str) -> Order:
    pedido = Order(
        user_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


# ── C4: `ship_*`, `payment_method`, `status_updated_at` e o snapshot do
# item — ver task-C4-brief.md e app/services/pedidos.py::endereco_formatado.


async def test_order_carries_the_shipping_snapshot(db_session):
    pedido = Order(
        user_id=uuid.uuid4(),
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

    assert pedido.ship_city == "São Paulo"
    assert pedido.status_updated_at is not None


async def test_order_item_snapshots_the_product(db_session):
    """`product_id` no brief usava `uuid.uuid4()` solto — mas
    `order_items.product_id` já tinha FK para `products` ANTES desta task
    (`app/models/pedido.py`, medido: `ForeignKey("products.id")` já existia
    no model), e a suíte roda contra Postgres real (não sqlite), que
    aplica a constraint. Medido: rodar o teste como o brief escreveu
    estoura `IntegrityError: ... violates foreign key constraint
    "order_items_product_id_fkey"`, não o comportamento que este teste
    quer provar. Corrigido semeando um `Product` real, sem mudar o que o
    teste verifica."""
    from app.models.produto import Product

    aluno_id = str(uuid.uuid4())
    pedido = await _seed_pedido(db_session, aluno_id)
    produto = Product(name="Guia de Redação Nota 1000", price=Decimal("49.90"), type="apostila")
    db_session.add(produto)
    await db_session.flush()

    item = OrderItem(
        order_id=pedido.id,
        product_id=produto.id,
        product_name="Guia de Redação Nota 1000",
        unit_price=Decimal("49.90"),
        quantity=2,
        image_url="products/seed-0.jpg",
        rating_avg=4.5,
        rating_count=128,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    assert item.product_name == "Guia de Redação Nota 1000"
    assert item.supplier_id is None


async def test_order_id_is_a_uuid_string_in_the_response(client, db_session):
    aluno_id = str(uuid.uuid4())
    pedido = await _seed_pedido(db_session, aluno_id)
    response = await client.get(
        f"/orders/{pedido.id}", headers=headers_for("student", sub=aluno_id)
    )
    assert response.status_code == 200
    assert isinstance(response.json()["id"], str)
    uuid.UUID(response.json()["id"])


async def test_order_detail_of_an_unknown_id_is_404(client):
    """Cobertura nova da task C6: nenhum teste em nenhum arquivo batia no
    ramo `except OrderNotFoundError` de `detalhe_pedido` com um UUID
    sintaticamente válido mas inexistente (só havia o caso do UUID
    malformado, que para na validação do path antes de chegar ao service —
    ver `test_a_malformed_order_id_is_a_422_not_a_500` abaixo)."""
    response = await client.get(f"/orders/{uuid.uuid4()}", headers=headers_for("student"))
    assert response.status_code == 404


async def test_a_malformed_order_id_is_a_422_not_a_500(client):
    """O caso `nao-e-uuid` NÃO é guarda de regressão desta task: ele já era
    verde ANTES dela, com `pedido_id: int` em `app/routers/pedidos.py`. O
    FastAPI valida o path param antes de entrar na função, e `int` rejeita
    `nao-e-uuid` com o mesmo 422 que `uuid.UUID` rejeita. Medido isolando
    a versão do brief num arquivo temporário (`1 passed`) antes de tocar
    em qualquer código — ver task-C3-report.md, seção Red, para o comando
    e a saída literais.

    O SEGUNDO caso é o que ficou vermelho antes desta task e verde depois:
    `123` é um `int` válido, então antes ele passava da validação, chegava
    à query e devolvia 404. Com `pedido_id: uuid.UUID` ele para na
    validação do path e vira 422. O Red literal foi `assert 404 == 422` —
    e o fato de a execução ter CHEGADO nesta segunda asserção é a segunda
    prova, independente, de que a primeira já passava.
    """
    response = await client.get("/orders/nao-e-uuid", headers=headers_for("student"))
    assert response.status_code == 422

    inteiro = await client.get("/orders/123", headers=headers_for("student"))
    assert inteiro.status_code == 422


async def test_creating_an_order_publishes_a_serialisable_event(
    client, db_session, _stub_publish_event
):
    """Trava do publisher de `order.created`, que NÃO tinha nenhuma cobertura
    que chegasse até ele.

    Medido no fix round 1 da task C3: revertendo `str(pedido.id)` em
    `app/routers/pedidos.py` e rodando `uv run pytest -q`, a suíte ficava
    **204 passed** — verde. O único teste que batia em `POST /orders`
    (`test_create_order_requires_authentication`) para no 403 e nunca alcança
    o `publish_event`. Ou seja, o `json.dumps` do stub
    (`conftest.py::_stub_publish_event`) travava cinco dos seis publishes do
    serviço, mas não este — justamente o do evento mais importante.

    O `str()` do payload é verificado indiretamente e de propósito: quem
    reprova um payload impublicável é o `json.dumps` do stub, no mesmo lugar
    onde `edu_common/events.py` falharia em runtime.

    Reescrito na task C6: o corpo antigo (`{"itens": [...]}`, preço vindo do
    cliente) não existe mais — o pedido agora nasce do carrinho, então o
    setup vira "adiciona ao carrinho, depois faz checkout".
    """
    from app.models.produto import Product

    aluno_id = str(uuid.uuid4())

    produto = Product(name="Caderno", price=Decimal("10.00"), type="apostila")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    await client.post(
        "/cart/items",
        json={"product_id": str(produto.id), "quantity": 2},
        headers=headers_for("student", sub=aluno_id),
    )
    response = await client.post(
        "/orders",
        json={"payment_method": "PIX"},
        headers=headers_for("student", sub=aluno_id),
    )
    assert response.status_code == 201, response.text

    criados = [payload for chave, payload in _stub_publish_event if chave == "order.created"]
    assert len(criados) == 1
    # O id vai como string no payload e bate com o id devolvido na resposta.
    assert criados[0]["pedido_id"] == response.json()["id"]
    assert isinstance(criados[0]["pedido_id"], str)


async def test_my_orders_listing_is_paginated(client, db_session):
    aluno_id = str(uuid.uuid4())
    for _ in range(5):
        await _seed_pedido(db_session, aluno_id)

    # C6: `/orders/mine` some, absorvida por `GET /orders` (bare).
    response = await client.get("/orders?limit=2", headers=headers_for("student", aluno_id))
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_my_orders_listing_rejects_limit_above_the_cap(client):
    response = await client.get("/orders?limit=5000", headers=headers_for("student"))
    assert response.status_code == 422


async def test_my_orders_only_returns_orders_owned_by_the_caller(client, db_session):
    mine = str(uuid.uuid4())
    someone_elses = str(uuid.uuid4())
    pedido_meu = await _seed_pedido(db_session, mine)
    await _seed_pedido(db_session, someone_elses)

    response = await client.get("/orders", headers=headers_for("student", mine))
    assert response.status_code == 200
    # C6: `OrderOut` (contrato do aluno) não expõe `user_id` — a mesma
    # propriedade (isolamento entre alunos) agora é conferida pelo
    # CONJUNTO DE IDS de pedido, não pelo dono cru.
    ids = {row["id"] for row in response.json()}
    assert ids == {str(pedido_meu.id)}


async def test_my_orders_response_does_not_leak_staff_assignee_ids(client, db_session):
    """Fix round 1 (reviewer finding, MINOR #4): `picker_id`/
    `deliverer_id` (`separador_id`/`entregador_id` antes da task C2) são
    identificadores operacionais internos — quem está
    separando/entregando o pedido não é assunto do aluno. Mesma classe do
    vazamento de `descricao_ia` fechado no learning-service. `OrderOut`
    (contrato do aluno, ex-`PedidoOut`) não deve incluí-los; `PedidoStaffOut`
    (picking/delivery/admin) é quem os expõe.

    Adaptado na task C6: `GET /orders/mine` virou `GET /orders`, e o
    conjunto de campos esperado é o de `OrderOut` (`id, total, status,
    payment_method, created_at, items`) — `user_id`/`carrier_name`/
    `estimated_delivery_at` saíram do contrato do aluno junto com
    `PedidoOut`, não só `picker_id`/`deliverer_id`. A PROPRIEDADE que este
    teste trava (nenhum id operacional vaza para o aluno) continua valendo
    e seria quebrada silenciosamente se alguém expandisse `OrderOut` sem
    passar por este teste."""
    aluno_id = str(uuid.uuid4())
    await _seed_pedido(db_session, aluno_id)

    response = await client.get("/orders", headers=headers_for("student", aluno_id))
    assert response.status_code == 200
    order = response.json()[0]
    assert set(order) == {
        "id",
        "total",
        "status",
        "payment_method",
        "created_at",
        "items",
    }
    assert "picker_id" not in order
    assert "deliverer_id" not in order
    assert "user_id" not in order


async def test_order_status_history_of_another_students_order_returns_404(client, db_session):
    """Achado 1 da revisão da task C8: a guarda de ownership de
    `historico_status` (o try/except em torno de `services.buscar_pedido`,
    app/routers/pedidos.py) não tinha nenhum teste — apagando o bloco
    inteiro a suíte continuava 281 passed (medido). Mesmo padrão de
    `test_rebuy_of_another_students_order_returns_404`
    (test_orders_parity.py, achado 8 do code review da C7): compara o CORPO
    inteiro contra o caso de id inexistente, não só o status code — a
    propriedade de segurança real é que os dois casos são indistinguíveis
    de fora, e comparar só o status code deixaria passar um vazamento de
    informação pela string de `detail`."""
    owner = str(uuid.uuid4())
    stranger = str(uuid.uuid4())
    pedido = await _seed_pedido(db_session, owner)

    resposta_outro_aluno = await client.get(
        f"/orders/{pedido.id}/status-history", headers=headers_for("student", stranger)
    )
    resposta_id_inexistente = await client.get(
        f"/orders/{uuid.uuid4()}/status-history", headers=headers_for("student", owner)
    )
    assert resposta_outro_aluno.status_code == 404
    assert resposta_outro_aluno.json() == resposta_id_inexistente.json()


# ── B7: nada provava que o `.limit(limit).offset(offset)` de
# `historico_status` (app/routers/pedidos.py) roda — apagar a clausula
# deixava a suite verde. `PedidoStatusHistoricoOut` nao expoe `id`, entao
# a fronteira entre paginas e conferida por `observacao`, que vai unica
# por linha. `criado_em` vai explicito e crescente porque a rota ordena
# por `criado_em.asc()`: com o `server_default=func.now()` as 55 linhas
# empatariam no mesmo timestamp e a paginacao ficaria nao-deterministica.
#
# Migrado de `/tracking` para `/status-history` na task C8: o path antigo
# passou a devolver o objeto de rastreio (`OrderTrackingOut`), nao mais o
# historico — a propriedade que este teste protege (paginacao real, nao so
# aceita) continua valendo, so mudou de endereco.


async def test_order_status_history_actually_applies_limit_and_offset(client, db_session):
    from datetime import UTC, datetime, timedelta

    from app.models.pedido import PedidoStatusHistorico

    aluno_id = str(uuid.uuid4())
    pedido = Order(
        user_id=aluno_id,
        status=StatusPedido.CRIADO.value,
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    total = 55
    for i in range(total):
        db_session.add(
            PedidoStatusHistorico(
                order_id=pedido.id,
                status=StatusPedido.CRIADO.value,
                observacao=f"evento-{i}",
                criado_em=base + timedelta(minutes=i),
            )
        )
    await db_session.commit()

    headers = headers_for("student", aluno_id)

    first_page = await client.get(f"/orders/{pedido.id}/status-history?limit=10", headers=headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body) == 10
    assert first_body[0]["observacao"] == "evento-0"

    last_page = await client.get(
        f"/orders/{pedido.id}/status-history?limit=10&offset=50", headers=headers
    )
    assert last_page.status_code == 200
    last_body = last_page.json()
    assert len(last_body) == total - 50
    assert last_body[0]["observacao"] == "evento-50"

    marcas_first = {row["observacao"] for row in first_body}
    marcas_last = {row["observacao"] for row in last_body}
    assert marcas_first.isdisjoint(marcas_last)
