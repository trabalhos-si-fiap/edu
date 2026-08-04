"""Order delivery lifecycle: the ordered progression of statuses, the
push/in-app notification copy for each, and the transition helpers the Celery
state machine relies on.

For this demo the real logistics events ("em separação", "saiu para entrega"…)
are simulated by short timers, but the state machine itself is real: each
status is reached exactly once, in order, forward-only.
"""

from app.modules.orders.enums import OrderStatus

# Forward-only progression. Index order IS the transition order.
ORDER_FLOW: tuple[OrderStatus, ...] = (
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.SEPARATING,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
)

# User-facing pt-BR copy for the notification fired when each status is reached.
# PENDING has no entry: it is never the target of a transition, so it never
# notifies.
STATUS_NOTIFICATION: dict[OrderStatus, tuple[str, str]] = {
    OrderStatus.CONFIRMED: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    OrderStatus.SEPARATING: (
        "Pedido em separação",
        "Estamos separando os itens do seu pedido.",
    ),
    OrderStatus.OUT_FOR_DELIVERY: (
        "Saiu para entrega",
        "Seu pedido saiu para entrega. Chega já já!",
    ),
    OrderStatus.DELIVERED: (
        "Pedido entregue",
        "Seu pedido foi entregue. Bons estudos!",
    ),
}


def _index(status: OrderStatus) -> int:
    return ORDER_FLOW.index(status)


def next_status(status: OrderStatus) -> OrderStatus | None:
    """Return the status that follows ``status``, or ``None`` if terminal."""
    i = _index(status)
    return ORDER_FLOW[i + 1] if i + 1 < len(ORDER_FLOW) else None


def can_advance_to(current: OrderStatus, target: OrderStatus) -> bool:
    """True only when ``target`` is the immediate successor of ``current``.

    Forward-only and exact-step. This is what makes the transition task both
    idempotent (a replay finds the order already at/after ``target``, so it
    no-ops) and safe against out-of-order delivery.
    """
    return _index(target) == _index(current) + 1
