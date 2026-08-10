"""Mapeia um `Order` persistido no payload de rastreio que a tela do
Flutter renderiza.

Este é o único lugar que traduz o status real do pedido — forward-only —
na timeline que o app mostra. É uma função pura (sem I/O), então a lógica
status -> timeline é testável sem banco. A camada de serviço é dona de
carregar o pedido e impor ownership; esta função só é dona da forma.

Porte de `legacy/app/modules/tracking/builders.py` (task C8), adaptado ao
contrato de SEIS valores: o legacy opera sobre `OrderStatus`/`ORDER_FLOW`
(cinco valores, que também É o status interno por lá). Aqui o construtor
opera sobre `status_do_contrato(order.status)` e `FLUXO_CONTRATO`, e há um
caso que o legacy não tem: `cancelled` não está em `FLUXO_CONTRATO` — ver
`_step_status` e `_COPY` abaixo.
"""

from datetime import datetime, timedelta

from app.models.pedido import Order
from app.schemas.rastreio import (
    KitItemOut,
    OrderTrackingOut,
    TrackingLocationOut,
    TrackingStepOut,
    TrackingStepStatus,
)
from app.services.status_pedido import FLUXO_CONTRATO, StatusContrato, status_do_contrato

_CARRIER = "Logistics Intel Express"
# Janela de entrega aproximada, mostrada enquanto o pedido ainda está em
# trânsito. O pipeline de demo termina em minutos; em produção isso viria
# da ETA real da logística.
_DELIVERY_WINDOW = timedelta(days=4)

# Os quatro passos visíveis da timeline, na ordem de progresso. PENDING é
# transitório (o pipeline sai dele em segundos), então fica colapsado em
# CONFIRMED. Cada `code` é o id estável que o app mapeia para um ícone
# (tracking_timeline.dart).
_STEPS: tuple[tuple[str, str, StatusContrato], ...] = (
    ("confirmed", "Confirmado", StatusContrato.CONFIRMED),
    ("separating", "Em separação", StatusContrato.SEPARATING),
    ("out_for_delivery", "Saiu para entrega", StatusContrato.OUT_FOR_DELIVERY),
    ("delivered", "Entregue", StatusContrato.DELIVERED),
)

# Headline + descrição mostrados no topo da tela, por status atual.
_COPY: dict[StatusContrato, tuple[str, str]] = {
    StatusContrato.PENDING: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    StatusContrato.CONFIRMED: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    StatusContrato.SEPARATING: (
        "Em separação",
        "Estamos separando os itens do seu pedido com carinho.",
    ),
    StatusContrato.OUT_FOR_DELIVERY: (
        "Saiu para entrega",
        "Seu pedido está a caminho do seu endereço. Chega já já!",
    ),
    StatusContrato.DELIVERED: (
        "Pedido entregue",
        "Seu pedido foi entregue. Bons estudos!",
    ),
    # Entrada que o legacy não tem: lá `cancelled` não existe. Sem ela,
    # `_COPY[status]` levantaria `KeyError` e o rastreio de um pedido
    # cancelado viraria 500.
    StatusContrato.CANCELLED: (
        "Pedido cancelado",
        "Este pedido foi cancelado. Se você não reconhece o cancelamento, fale com o suporte.",
    ),
}

# Rótulo de última localização conhecida, por status. Cidade/estado vêm do
# snapshot de endereço do pedido quando ele já saiu para entrega (ver
# `build_order_tracking`); este dict só decide o texto do nome do card.
_LOCATION_NAME: dict[StatusContrato, str] = {
    StatusContrato.OUT_FOR_DELIVERY: "Em rota de entrega",
    StatusContrato.DELIVERED: "Entregue no endereço",
}
_DEFAULT_LOCATION_NAME = "Centro de Distribuição"


def _step_status(atual: StatusContrato, passo: StatusContrato) -> TrackingStepStatus:
    """Onde um passo da timeline está em relação ao status real do pedido."""
    # `CANCELLED` não pertence a FLUXO_CONTRATO — `.index()` sobre ele
    # levantaria ValueError. Um pedido cancelado não tem passo corrente: a
    # timeline inteira fica pendente e o headline conta o que houve.
    if atual == StatusContrato.CANCELLED:
        return TrackingStepStatus.PENDING
    if atual == StatusContrato.DELIVERED:
        return TrackingStepStatus.DONE

    idx_atual = FLUXO_CONTRATO.index(atual)
    idx_passo = FLUXO_CONTRATO.index(passo)
    if idx_passo < idx_atual:
        return TrackingStepStatus.DONE
    if idx_passo == idx_atual:
        return TrackingStepStatus.CURRENT
    # PENDING (índice 0) não tem passo visível próprio: expõe CONFIRMED como
    # o ativo, para a tela nunca mostrar uma timeline toda pendente.
    if idx_atual == 0 and passo == StatusContrato.CONFIRMED:
        return TrackingStepStatus.CURRENT
    return TrackingStepStatus.PENDING


def _step_timestamp(
    code: str,
    step_status: TrackingStepStatus,
    *,
    created_at: datetime,
    status_updated_at: datetime,
) -> datetime | None:
    """Timestamps reais onde existem, `None` no resto.

    Só persistimos o horário da última transição (`status_updated_at`),
    então o passo corrente mostra ele, e o primeiro passo é ancorado na
    criação. Passos intermediários mais antigos não têm horário registrado
    e ficam em branco (o app os esconde).
    """
    if step_status == TrackingStepStatus.CURRENT or code == "delivered":
        return status_updated_at
    if code == "confirmed":
        return created_at
    return None


def build_order_tracking(order: Order) -> OrderTrackingOut:
    """Monta o payload da tela de rastreio a partir do status atual do pedido."""
    status = status_do_contrato(order.status)
    created_at = order.created_at
    # Defensivo: linhas de antes de alguma migration poderiam não ter isso;
    # cai para a criação.
    status_updated_at = order.status_updated_at or created_at

    steps = []
    for code, title, step_status_contrato in _STEPS:
        step_status = _step_status(status, step_status_contrato)
        steps.append(
            TrackingStepOut(
                code=code,
                title=title,
                status=step_status,
                timestamp=_step_timestamp(
                    code,
                    step_status,
                    created_at=created_at,
                    status_updated_at=status_updated_at,
                ),
            )
        )

    headline, description = _COPY[status]
    estimated_arrival = (
        status_updated_at if status == StatusContrato.DELIVERED else created_at + _DELIVERY_WINDOW
    )

    # Uma vez que o pacote saiu para entrega / foi entregue, a última
    # localização conhecida é a cidade de destino; antes disso fica no
    # centro de distribuição. `cancelled` cai no default (`_DEFAULT_LOCATION_NAME`
    # / Cajamar-SP), que é o comportamento certo: um pedido cancelado nunca
    # chegou a sair.
    at_destination = status in (StatusContrato.OUT_FOR_DELIVERY, StatusContrato.DELIVERED)
    location_city = order.ship_city if (at_destination and order.ship_city) else "Cajamar"
    location_state = order.ship_state if (at_destination and order.ship_state) else "SP"

    return OrderTrackingOut(
        id=str(order.id),
        headline=headline,
        description=description,
        estimated_arrival=estimated_arrival,
        steps=steps,
        location=TrackingLocationOut(
            name=_LOCATION_NAME.get(status, _DEFAULT_LOCATION_NAME),
            city=location_city,
            state=location_state,
            updated_at=status_updated_at,
        ),
        kit=[KitItemOut(name=item.product_name) for item in order.items],
        carrier=_CARRIER,
        map_url=None,
        status=status,
    )
