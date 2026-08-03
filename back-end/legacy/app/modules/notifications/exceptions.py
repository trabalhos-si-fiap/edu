class NotificationError(Exception):
    """Base class for notification domain errors."""


class DeviceTokenNotFound(NotificationError):
    """No device token with the given value belongs to the user."""
