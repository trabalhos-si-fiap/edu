"""Schemas de formas de pagamento. Porte de
`legacy/app/modules/payment_methods/schemas.py` e
`legacy/app/modules/payment_methods/enums.py` (task B9).

`PaymentMethodType` fica junto do resto dos schemas, não em módulo próprio —
pedido explícito da seção "Files" do brief ("schemas (inclui o enum
`PaymentMethodType`)").
"""

import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

_CARD_LAST4_RE = r"^\d{4}$"
_EXPIRY_RE = r"^\d{4}$"  # MMYY


class PaymentMethodType(StrEnum):
    CREDIT_CARD = "credit_card"
    PIX = "pix"
    BOLETO = "boleto"


class PaymentMethodIn(BaseModel):
    # extra="forbid" rejeita campo inesperado — como número de cartão
    # completo (PAN) ou CVV — dado sensível de cartão nunca pode alcançar o
    # servidor (regra de segurança #5 do CLAUDE.md). NÃO AFROUXAR: provado
    # por mutação em task-B9-report.md (trocar para "ignore" faz
    # TestPciSafety aceitar 201 em vez de rejeitar 422).
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
        # PIX e boleto não guardam dado nenhum — o código de pagamento é
        # gerado no checkout — então só cartão de crédito tem campo de
        # exibição obrigatório.
        if self.type is PaymentMethodType.CREDIT_CARD:
            missing = [
                name
                for name in ("card_last4", "card_brand", "cardholder_name", "card_expiry")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"credit_card requires: {', '.join(missing)}")
        return self


class PaymentMethodPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_default: bool | None = None


class PaymentMethodOut(BaseModel):
    # Campos explícitos (regra 6 do CLAUDE.md) — `from_attributes=True` é
    # seguro aqui porque a lista de campos é exatamente a lista de dado não
    # sigiloso do model (nenhum PAN/CVV é armazenado, então não há nada a
    # vazar mesmo espelhando todos os atributos declarados).
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: PaymentMethodType
    is_default: bool = False
    card_last4: str | None = None
    card_brand: str | None = None
    cardholder_name: str | None = None
    card_expiry: str | None = None
    pix_key: str | None = None
