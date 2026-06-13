import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import new_uuid


class DeviceToken(Base):
    __tablename__ = "notifications_device_tokens"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('android', 'ios', 'web')",
            name="ck_notifications_device_tokens_platform",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    # Logical FK to auth_users; ownership is always enforced in queries.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # FCM registration tokens are opaque and can be long; cap defensively.
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Notification(Base):
    """An in-app/push notification delivered to a user.

    Persisted unconditionally (even when the user has no device token) so the
    in-app history is complete. ``data`` mirrors the FCM data payload used for
    client-side deep-linking (e.g. ``{"type": "order_status", "order_id": …}``).
    """

    __tablename__ = "notifications_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    # Logical FK to auth_users; ownership is always enforced in queries.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
