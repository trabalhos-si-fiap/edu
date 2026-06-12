"""Firebase Admin SDK integration for sending push notifications.

The ``firebase_admin`` import is kept lazy so the rest of the app (and the test
suite) never depends on the package being installed unless a push is actually
sent. Business logic mocks :func:`send_multicast`, not the SDK internals.
"""

from dataclasses import dataclass
from threading import Lock
from typing import Any

from loguru import logger

from app.core.config import settings

_app: Any = None
_lock = Lock()


class FirebaseNotConfiguredError(RuntimeError):
    """FIREBASE_CREDENTIALS_PATH is unset, so the Admin SDK cannot start."""


def get_app() -> Any:
    """Return a lazily-initialised, process-wide Firebase app singleton."""
    global _app
    if _app is not None:
        return _app
    with _lock:
        if _app is None:
            if not settings.FIREBASE_CREDENTIALS_PATH:
                raise FirebaseNotConfiguredError(
                    "FIREBASE_CREDENTIALS_PATH is not set; cannot initialise Firebase Admin SDK"
                )
            import firebase_admin
            from firebase_admin import credentials

            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            _app = firebase_admin.initialize_app(cred)
    return _app


@dataclass(frozen=True)
class PushResult:
    """Per-token outcome of a multicast send."""

    token: str
    success: bool
    # True when FCM reports the token is permanently invalid and must be purged.
    invalid: bool


def send_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> list[PushResult]:
    """Send one notification to many device tokens, returning per-token results.

    Tokens flagged ``invalid`` (unregistered / sender-id mismatch) should be
    deleted by the caller so the database does not accumulate dead tokens.
    """
    if not tokens:
        return []

    from firebase_admin import messaging

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
    )
    batch = messaging.send_each_for_multicast(message, app=get_app())

    results: list[PushResult] = []
    for token, resp in zip(tokens, batch.responses, strict=True):
        invalid = not resp.success and isinstance(
            resp.exception,
            (messaging.UnregisteredError, messaging.SenderIdMismatchError),
        )
        results.append(PushResult(token=token, success=resp.success, invalid=invalid))

    logger.info(
        "notifications: multicast sent total={} success={} invalid={}",
        len(results),
        sum(r.success for r in results),
        sum(r.invalid for r in results),
    )
    return results
