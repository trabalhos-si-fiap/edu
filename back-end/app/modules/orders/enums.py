from enum import StrEnum


class OrderStatus(StrEnum):
    """Delivery lifecycle of an order, in the order it progresses.

    ``PENDING`` is the transient just-created state; the status pipeline
    advances it to ``CONFIRMED`` immediately. ``DELIVERED`` is terminal.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEPARATING = "separating"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
