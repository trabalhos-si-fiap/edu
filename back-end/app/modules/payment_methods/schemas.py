import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.payment_methods.enums import PaymentMethodType

_CARD_LAST4_RE = r"^\d{4}$"
_EXPIRY_RE = r"^\d{4}$"  # MMYY


class PaymentMethodIn(BaseModel):
    # extra="forbid" rejects unexpected fields such as a full card number or
    # CVV — sensitive card data must never reach the server (security rule #5).
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: PaymentMethodType
    is_default: bool = False
    card_last4: str | None = Field(default=None, pattern=_CARD_LAST4_RE)
    card_brand: str | None = Field(default=None, max_length=40)
    cardholder_name: str | None = Field(default=None, max_length=120)
    card_expiry: str | None = Field(default=None, pattern=_EXPIRY_RE)
    pix_key: str | None = Field(default=None, max_length=140)

    @model_validator(mode="after")
    def _require_fields_by_type(self) -> "PaymentMethodIn":
        if self.type is PaymentMethodType.CREDIT_CARD:
            missing = [
                name
                for name in ("card_last4", "card_brand", "cardholder_name", "card_expiry")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"credit_card requires: {', '.join(missing)}")
        elif self.type is PaymentMethodType.PIX and not self.pix_key:
            raise ValueError("pix requires pix_key")
        return self


class PaymentMethodPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_default: bool | None = None


class PaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: PaymentMethodType
    is_default: bool = False
    card_last4: str | None = None
    card_brand: str | None = None
    cardholder_name: str | None = None
    card_expiry: str | None = None
    pix_key: str | None = None
