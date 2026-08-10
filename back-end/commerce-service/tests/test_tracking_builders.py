"""Testes unitários do construtor puro pedido -> payload de rastreio.

Sem banco: o construtor recebe uma instância de `Order` e devolve o
`OrderTrackingOut` que a tela de rastreio do Flutter consome. As asserções
conferem que a timeline reflete o status real do pedido.

Porte de `legacy/tests/test_tracking_builders.py` (task C8). Adaptações:
`OrderStatus` (legacy, cinco valores, é ao mesmo tempo o status interno e o
do contrato) vira dois conceitos aqui — o SEED do pedido usa o status
INTERNO (`StatusPedido`, nove valores, o que `order.status` guarda de
verdade) e as asserções sobre `payload.steps`/`headline` usam a linguagem
do CONTRATO (`StatusContrato`, seis valores), porque é sobre isso que
`build_order_tracking` opera (`status_do_contrato` traduz um no outro).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.pedido import Order, OrderItem
from app.schemas.rastreio import TrackingStepStatus
from app.services.rastreio_builder import build_order_tracking
from app.services.status_pedido import StatusContrato, StatusPedido, status_do_contrato

_CREATED = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
_UPDATED = _CREATED + timedelta(minutes=2)

# Os quatro passos visíveis da timeline, em ordem. PENDING é colapsado em CONFIRMED.
_STEP_CODES = ["confirmed", "separating", "out_for_delivery", "delivered"]


def _order_falso(status: str, *, items: int = 2) -> Order:
    return Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total=Decimal("100.00"),
        payment_method="pix",
        status=status,
        created_at=_CREATED,
        status_updated_at=_UPDATED,
        items=[
            OrderItem(
                product_id=uuid.uuid4(),
                product_name=f"Item {i}",
                unit_price=Decimal("50.00"),
                quantity=1,
            )
            for i in range(items)
        ],
    )


def _statuses(order: Order) -> dict[str, TrackingStepStatus]:
    payload = build_order_tracking(order)
    return {s.code: s.status for s in payload.steps}


def test_steps_always_cover_the_four_visible_stages() -> None:
    payload = build_order_tracking(_order_falso(StatusPedido.CONFIRMADO.value))
    assert [s.code for s in payload.steps] == _STEP_CODES


def test_pending_surfaces_confirmed_as_current() -> None:
    statuses = _statuses(_order_falso(StatusPedido.CRIADO.value))
    assert statuses["confirmed"] == TrackingStepStatus.CURRENT
    assert statuses["separating"] == TrackingStepStatus.PENDING
    assert statuses["delivered"] == TrackingStepStatus.PENDING


def test_separating_marks_confirmed_done_and_separating_current() -> None:
    statuses = _statuses(_order_falso(StatusPedido.EM_SEPARACAO.value))
    assert statuses["confirmed"] == TrackingStepStatus.DONE
    assert statuses["separating"] == TrackingStepStatus.CURRENT
    assert statuses["out_for_delivery"] == TrackingStepStatus.PENDING


def test_out_for_delivery_is_current() -> None:
    statuses = _statuses(_order_falso(StatusPedido.EM_TRANSITO.value))
    assert statuses["separating"] == TrackingStepStatus.DONE
    assert statuses["out_for_delivery"] == TrackingStepStatus.CURRENT
    assert statuses["delivered"] == TrackingStepStatus.PENDING


def test_delivered_marks_every_step_done() -> None:
    statuses = _statuses(_order_falso(StatusPedido.ENTREGUE.value))
    assert all(s == TrackingStepStatus.DONE for s in statuses.values())


def test_kit_is_built_from_order_items() -> None:
    payload = build_order_tracking(_order_falso(StatusPedido.EM_SEPARACAO.value, items=3))
    assert [k.name for k in payload.kit] == ["Item 0", "Item 1", "Item 2"]


def test_current_step_carries_the_status_timestamp() -> None:
    payload = build_order_tracking(_order_falso(StatusPedido.EM_TRANSITO.value))
    current = next(s for s in payload.steps if s.status == TrackingStepStatus.CURRENT)
    assert current.timestamp == _UPDATED


def test_payload_id_is_the_order_uuid() -> None:
    order = _order_falso(StatusPedido.CONFIRMADO.value)
    payload = build_order_tracking(order)
    assert payload.id == str(order.id)


@pytest.mark.parametrize("status", list(StatusPedido))
def test_exactly_one_current_step_unless_delivered_or_cancelled(status: StatusPedido) -> None:
    payload = build_order_tracking(_order_falso(status.value))
    currents = [s for s in payload.steps if s.status == TrackingStepStatus.CURRENT]
    if status in (StatusPedido.ENTREGUE, StatusPedido.CANCELADO):
        assert currents == []
    else:
        assert len(currents) == 1


def test_location_uses_snapshot_city_when_out_for_delivery() -> None:
    order = _order_falso(StatusPedido.EM_TRANSITO.value)
    order.ship_city = "Jundiaí"
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    assert payload.location.city == "Jundiaí"
    assert payload.location.state == "SP"


def test_location_uses_snapshot_city_when_delivered() -> None:
    order = _order_falso(StatusPedido.ENTREGUE.value)
    order.ship_city = "Campinas"
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    assert payload.location.city == "Campinas"


def test_location_falls_back_to_cd_before_dispatch() -> None:
    order = _order_falso(StatusPedido.EM_SEPARACAO.value)
    order.ship_city = "Jundiaí"
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    # Ainda no centro de distribuição, até sair para entrega.
    assert payload.location.city == "Cajamar"
    assert payload.location.state == "SP"


def test_location_city_up_to_the_order_column_length_does_not_raise() -> None:
    """Achado 5 da revisão da task C8: `TrackingLocationOut.city` tinha
    `max_length=80` enquanto `Order.ship_city` (app/models/pedido.py) é
    `String(120)` — uma cidade de 81 a 120 caracteres é armazenável no
    pedido e não serializável na resposta, então rastrear esse pedido
    estourava 500. Herdado do legacy (mesmo mismatch lá), mas aqui é bug
    corrigido, não copiado: `TrackingLocationOut.city` passa a
    `max_length=120`, batendo com a coluna que o alimenta."""
    order = _order_falso(StatusPedido.EM_TRANSITO.value)
    order.ship_city = "A" * 120  # tamanho máximo da coluna Order.ship_city
    order.ship_state = "SP"
    payload = build_order_tracking(order)
    assert payload.location.city == "A" * 120


def test_tracking_of_a_cancelled_order_does_not_raise() -> None:
    """`cancelled` não está em `FLUXO_CONTRATO`. Um `.index()` sobre ele
    levantaria `ValueError`, e o rastreio viraria 500."""
    order = _order_falso(StatusPedido.CANCELADO.value)
    tracking = build_order_tracking(order)
    assert tracking.headline == "Pedido cancelado"
    assert all(s.status == TrackingStepStatus.PENDING for s in tracking.steps)


@pytest.mark.parametrize("status", list(StatusPedido))
def test_payload_status_mirrors_the_contract_status(status: StatusPedido) -> None:
    """`OrderTrackingOut.status` (divergência deliberada nº 7 — o legacy não
    tem esse campo) espelha o valor público de `status_do_contrato`, para
    todos os nove estados internos, não só `cancelled`."""
    payload = build_order_tracking(_order_falso(status.value))
    assert payload.status == status_do_contrato(status.value)


def test_cancelled_order_tracking_status_is_cancelled() -> None:
    order = _order_falso(StatusPedido.CANCELADO.value)
    payload = build_order_tracking(order)
    assert payload.status == StatusContrato.CANCELLED


def test_cancelled_order_still_returns_an_estimated_arrival() -> None:
    """Achado 6 da revisão da task C8: TRAVA o comportamento atual, não
    muda nada — `build_order_tracking` não tem caso especial para
    `estimated_arrival` de pedido cancelado (herdado do legacy, que também
    não tem), então continua sendo `created_at + _DELIVERY_WINDOW`, nunca
    `None`.

    Nular pareceria mais "correto" à primeira vista, mas o Flutter
    (`front-end-flutter/lib/features/order_tracking/domain/order_model.dart:150-151`)
    faz `DateTime.tryParse(json['estimated_arrival'] ?? '') ??
    DateTime.now()` — mandar `null` faria a tela dizer que o pedido está
    chegando AGORA, pior que uma data futura obsoleta. A consequência de
    exibição (o que a tela deveria mostrar para um pedido cancelado) é
    pergunta do lado Flutter, não deste backend; aqui só travamos que o
    campo continua vindo preenchido.
    """
    order = _order_falso(StatusPedido.CANCELADO.value)
    tracking = build_order_tracking(order)
    assert tracking.estimated_arrival is not None
    assert tracking.estimated_arrival == _CREATED + timedelta(days=4)
