class ProductError(Exception):
    """Base class for product domain errors."""


class ProductNotFound(ProductError):
    """No product exists with the given id."""
