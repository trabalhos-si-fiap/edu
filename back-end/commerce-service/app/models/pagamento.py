from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.ids import new_uuid


class PaymentMethod(Base):
    """Forma de pagamento salva de um usuário. Porte de
    `legacy/app/modules/payment_methods/models.py::PaymentMethod` (task B9).

    PCI/LGPD: esta tabela guarda SÓ dado de exibição não sigiloso e mascarado.
    Nunca guarda o número completo do cartão (PAN), CVV ou CPF. O cliente
    manda o dado já mascarado (últimos 4 dígitos + bandeira) — dado sensível
    de cartão nunca alcança o servidor. `extra="forbid"` em
    `PaymentMethodIn` (app/schemas/pagamento.py) é o que barra isso na
    entrada; os dois `CheckConstraint` abaixo travam a forma no banco.

    `__tablename__` corrige o typo do legacy (`payment_methods_methods`,
    `models.py:21`) para `payment_methods` — pedido explícito do Step 3 do
    brief.

    Estilo `Column` clássico (não `Mapped`/`mapped_column` do legacy) —
    mesma decisão de B6/B7/B8 para `produto.py`/`review.py`/`carrinho.py`,
    por consistência com o resto do serviço.
    """

    __tablename__ = "payment_methods"
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

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    # FK lógica para o auth-users-service (banco diferente, sem FK física
    # possível) — mesmo padrão de `Review.user_id`/`Cart.user_id`.
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    type = Column(String(16), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    # Campos de exibição do cartão (mascarados). card_last4 são SÓ os
    # últimos 4 dígitos.
    card_last4 = Column(String(4), nullable=True)
    card_brand = Column(String(40), nullable=True)
    cardholder_name = Column(String(120), nullable=True)
    card_expiry = Column(String(4), nullable=True)  # MMYY
    pix_key = Column(String(140), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
