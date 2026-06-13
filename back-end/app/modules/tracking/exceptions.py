class TrackingError(Exception):
    """Base class for delivery-tracking domain errors."""


class OrderNotFound(TrackingError):
    """No trackable order with the given id belongs to the user."""


class RouteUnavailable(TrackingError):
    """The routing provider could not return a route for the given points."""
