class TrackingError(Exception):
    """Base class for delivery-tracking domain errors."""


class OrderNotFound(TrackingError):
    """No trackable order with the given id belongs to the user."""
