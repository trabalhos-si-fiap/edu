class OrderError(Exception):
    """Base class for order domain errors."""


class OrderNotFound(OrderError):
    """No order with the given id belongs to the user."""


class EmptyCart(OrderError):
    """Checkout attempted with an empty cart."""
