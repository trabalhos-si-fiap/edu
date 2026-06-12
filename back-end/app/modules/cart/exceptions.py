class CartError(Exception):
    """Base class for cart domain errors."""


class CartProductNotFound(CartError):
    """Attempted to add a product that does not exist in the catalog."""


class CartItemNotFound(CartError):
    """Attempted to remove an item that is not in the cart."""
