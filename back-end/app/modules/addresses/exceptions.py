class AddressError(Exception):
    """Base class for address domain errors."""


class AddressNotFound(AddressError):
    """No address with the given id belongs to the user."""
