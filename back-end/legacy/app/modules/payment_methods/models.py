import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import new_uuid


class PaymentMethod(Base):
    """A user's saved payment method.

    PCI/LGPD: this table stores ONLY non-secret, masked display data. It never
    holds a full card number (PAN), CVV, or tax id (CPF). Clients are expected
    to send already-masked data (last 4 digits + brand), so sensitive card data
    never reaches the server.
    """

    __tablename__ = "payment_methods_methods"
    __table_args__ = (
        CheckConstraint(
            "type IN ('credit_card', 'pix', 'boleto')",
            name="ck_payment_methods_type",
        ),
        CheckConstraint(
            "card_last4 IS NULL OR char_length(card_last4) = 4",
            name="ck_payment_methods_card_last4_len",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Card display fields (masked). card_last4 is the LAST 4 digits only.
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cardholder_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    card_expiry: Mapped[str | None] = mapped_column(String(4), nullable=True)  # MMYY
    pix_key: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
