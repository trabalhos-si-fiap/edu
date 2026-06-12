class PaymentMethodError(Exception):
    """Base class for payment method domain errors."""


class PaymentMethodNotFound(PaymentMethodError):
    """No payment method with the given id belongs to the user."""
