class AuthError(Exception):
    """Base class for auth domain errors."""


class EmailAlreadyRegistered(AuthError):
    """Registration attempted with an email already in use."""


class InvalidCredentials(AuthError):
    """Login credentials did not match any active user."""


class InvalidToken(AuthError):
    """JWT was missing, expired, malformed, or carried the wrong type."""


class UserInactive(AuthError):
    """Authenticated user exists but is_active is False."""


class RateLimitExceeded(AuthError):
    """Too many login attempts within the configured window."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Too many attempts, retry after {retry_after}s")
        self.retry_after = retry_after
