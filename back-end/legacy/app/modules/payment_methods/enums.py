from enum import StrEnum


class PaymentMethodType(StrEnum):
    CREDIT_CARD = "credit_card"
    PIX = "pix"
    BOLETO = "boleto"
