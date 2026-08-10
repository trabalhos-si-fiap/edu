"""Trava de tipo: as CINCO routing keys de pedido carregam `pedido_id` como
string de UUID, nunca como o valor cru.

Task C10. `orders.id` é UUID desde a task C3, e JSON não tem tipo UUID — o
transporte real (`edu_common/events.py`, `json.dumps(payload)`) estoura
`TypeError` se algum publish esquecer o `str(...)`. Este arquivo trava a
PROPRIEDADE do payload, não a implementação: se algum publish futuro
regredir para o valor cru, este teste pega, sem precisar saber qual dos
seis call sites (`ocorrencias.py` tem quatro) foi o culpado.

Os SEIS sites, não cinco — `order.status_changed` tem DOIS produtores:
`separacao.py:113` (via `transicionar_pedido`, alcançado abaixo pelo
braço `order.status_changed` do despachante, que passa por
`confirm-payment`) e `ocorrencias.py:366` (dentro de
`resolver_ocorrencia`, só alcançável com `resolucao="cancelar_pedido"`).
Achado da revisão (fix round 1, Important #1): o parametrize sozinho NÃO
mordia o segundo site — removendo o `str(...)` só dali, os cinco casos
parametrizados continuavam verdes.
`test_order_status_changed_via_occurrence_cancellation_carries_pedido_id_as_a_uuid_string`
(fora do parametrize) cobre esse call site especificamente; com ela, os
seis sites estão cobertos, um por um.

As CHAVES ficam em português — renomeá-las dessincronizaria produtor e
consumidor sem nenhum cliente pedindo. Só o tipo muda.
"""

import uuid
from decimal import Decimal

import pytest
from edu_common.security import create_access_token

from app.config import settings
from app.models.pedido import Order
from app.models.produto import Product
from app.services.status_pedido import StatusPedido

# Cópia local, não importada de outro módulo de teste: `tests/` não tem
# import cruzado entre módulos hoje (medido, `grep -rn "^from tests\." tests/`
# vazio) e o brief desta task aceita explicitamente duplicar helpers curtos
# em vez de criar uma oitava cópia de `headers_for` num módulo compartilhado.


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


ALUNO = "00000000-0000-0000-0000-000000000001"  # sub padrão de headers_for("student")
ADMIN = "00000000-0000-0000-0000-0000000000aa"
PICKER_A = "00000000-0000-0000-0000-0000000000e1"
DELIVERER_A = "00000000-0000-0000-0000-0000000000f1"


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


async def _seed_pedido_com_endereco(
    db_session,
    status: str = StatusPedido.CRIADO.value,
    picker_id: str | None = None,
    deliverer_id: str | None = None,
    user_id: str = ALUNO,
) -> Order:
    """Variante local de `test_admin_routes.py::_seed_pedido_com_endereco`
    com `status`/`picker_id`/`deliverer_id`/`user_id` como overrides — a
    versão de lá não os aceita, e os produtores de `order.stock_issue`/
    `order.delivery_delayed` exigem picker/deliverer donos do pedido
    (`ocorrencias.py`: `str(pedido.picker_id) != user["sub"]` etc.).
    `user_id` default = `ALUNO` porque `order.occurrence_resolved` só
    resolve para o aluno DONO do pedido (`ocorrencias.py::resolver_ocorrencia`).
    """
    pedido = Order(
        user_id=user_id,
        status=status,
        total=Decimal("100.00"),
        payment_method="PIX",
        picker_id=picker_id,
        deliverer_id=deliverer_id,
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


async def _exercitar_o_produtor_de(routing_key: str, client, db_session) -> None:
    """Aciona a rota que publica `routing_key`.

    Um despachante em vez de cinco testes quase iguais: o que está sendo
    travado é uma propriedade do PAYLOAD, idêntica nos cinco, e o que muda é
    só como se chega lá.

    Cada chamada HTTP confere o status 2xx antes de seguir — achado da
    revisão (fix round 1, Minor #6): sem isso, um schema que mudasse e
    fizesse um `POST` virar 422 apareceria como "nada publicou <key>" no
    assert de fora, a mesma mensagem enganosa que o brief original já tinha
    avisado para o caso de `FaltaEstoqueIn`/`AtrasoEntregaIn` mudarem.
    """
    if routing_key == "order.created":
        produto = await _seed_produto(db_session)
        add_item = await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for("student", sub=ALUNO),
        )
        assert add_item.status_code == 201, f"POST /cart/items: {add_item.text}"
        criar = await client.post("/orders", json={}, headers=headers_for("student", sub=ALUNO))
        assert criar.status_code == 201, f"POST /orders: {criar.text}"

    elif routing_key == "order.status_changed":
        pedido = await _seed_pedido_com_endereco(db_session)
        confirmar = await client.patch(
            f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin", sub=ADMIN)
        )
        assert confirmar.status_code == 200, f"PATCH .../confirm-payment: {confirmar.text}"

    elif routing_key == "order.stock_issue":
        produto = await _seed_produto(db_session)
        pedido = await _seed_pedido_com_endereco(
            db_session, status=StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A
        )
        reportar = await client.post(
            "/occurrences/stock-shortage",
            json={
                "pedido_id": str(pedido.id),
                "produto_id": str(produto.id),
                "motivo": "sem estoque",
            },
            headers=headers_for("separador", sub=PICKER_A),
        )
        assert reportar.status_code == 201, f"POST /occurrences/stock-shortage: {reportar.text}"

    elif routing_key == "order.delivery_delayed":
        pedido = await _seed_pedido_com_endereco(
            db_session, status=StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
        )
        reportar = await client.post(
            "/occurrences/delivery-delay",
            json={
                "pedido_id": str(pedido.id),
                "nova_data_sugerida": "2026-08-20T12:00:00+00:00",
                "motivo": "chuva",
            },
            headers=headers_for("entregador", sub=DELIVERER_A),
        )
        assert reportar.status_code == 201, f"POST /occurrences/delivery-delay: {reportar.text}"

    elif routing_key == "order.occurrence_resolved":
        pedido = await _seed_pedido_com_endereco(
            db_session, status=StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
        )
        criar = await client.post(
            "/occurrences/delivery-delay",
            json={
                "pedido_id": str(pedido.id),
                "nova_data_sugerida": "2026-08-20T12:00:00+00:00",
                "motivo": "chuva",
            },
            headers=headers_for("entregador", sub=DELIVERER_A),
        )
        assert criar.status_code == 201, f"POST /occurrences/delivery-delay: {criar.text}"
        resolver = await client.post(
            f"/occurrences/{criar.json()['id']}/resolve",
            json={"resolucao": "aceitar_nova_data"},
            headers=headers_for("student", sub=ALUNO),
        )
        assert resolver.status_code == 200, f"POST /occurrences/{{id}}/resolve: {resolver.text}"

    else:
        raise AssertionError(f"routing key sem produtor mapeado: {routing_key}")


@pytest.mark.parametrize(
    "routing_key",
    [
        "order.created",
        "order.status_changed",
        "order.stock_issue",
        "order.delivery_delayed",
        "order.occurrence_resolved",
    ],
)
async def test_every_order_event_carries_pedido_id_as_a_uuid_string(
    routing_key, client, db_session, _stub_publish_event
):
    """As CHAVES ficam em português — renomeá-las dessincronizaria produtor e
    consumidor sem nenhum cliente pedindo. Só o tipo muda."""
    await _exercitar_o_produtor_de(routing_key, client, db_session)

    payloads = [p for key, p in _stub_publish_event if key == routing_key]
    assert payloads, f"nada publicou {routing_key}"
    for payload in payloads:
        assert isinstance(payload["pedido_id"], str)
        uuid.UUID(payload["pedido_id"])


async def test_order_status_changed_via_occurrence_cancellation_carries_pedido_id_as_a_uuid_string(
    client, db_session, _stub_publish_event
):
    """`order.status_changed` tem DOIS produtores, não um só:
    `separacao.py:113` (via `transicionar_pedido`, coberto acima pelo braço
    `order.status_changed` do despachante, que passa por
    `confirm-payment`) e `ocorrencias.py:366` (dentro de
    `resolver_ocorrencia`, só alcançável com `resolucao="cancelar_pedido"`
    — `cancelou` só vira `True` nesse ramo).

    Achado da revisão (fix round 1, Important #1): removendo o `str(...)`
    só do segundo site e rodando o parametrize acima, os cinco casos
    continuavam verdes — nenhum deles alcança este call site. Este teste
    cobre especificamente ele, fora do parametrize porque não é uma NOVA
    routing key, é um segundo CAMINHO até a mesma."""
    pedido = await _seed_pedido_com_endereco(
        db_session, status=StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
    )
    criar = await client.post(
        "/occurrences/delivery-delay",
        json={
            "pedido_id": str(pedido.id),
            "nova_data_sugerida": "2026-08-20T12:00:00+00:00",
            "motivo": "chuva",
        },
        headers=headers_for("entregador", sub=DELIVERER_A),
    )
    assert criar.status_code == 201, f"POST /occurrences/delivery-delay: {criar.text}"

    resolver = await client.post(
        f"/occurrences/{criar.json()['id']}/resolve",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student", sub=ALUNO),
    )
    assert resolver.status_code == 200, f"POST /occurrences/{{id}}/resolve: {resolver.text}"

    payloads = [p for key, p in _stub_publish_event if key == "order.status_changed"]
    assert payloads, "nada publicou order.status_changed"
    for payload in payloads:
        assert isinstance(payload["pedido_id"], str)
        uuid.UUID(payload["pedido_id"])
