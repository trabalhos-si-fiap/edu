/// Tipos de método de pagamento. Portado de edu-kt `PaymentMethodType`.
enum PaymentMethodType { creditCard, pix, boleto }

/// Método de pagamento salvo. Portado de edu-kt `PaymentMethod`.
class PaymentMethod {
  final String id;
  final PaymentMethodType type;
  final bool isDefault;
  final String? cardLast4;
  final String? cardBrand;
  final String? cardholderName;
  final String? cardExpiry; // MMYY
  final String? cardholderTaxId;
  final String? pixKey;

  const PaymentMethod({
    required this.id,
    required this.type,
    this.isDefault = false,
    this.cardLast4,
    this.cardBrand,
    this.cardholderName,
    this.cardExpiry,
    this.cardholderTaxId,
    this.pixKey,
  });

  PaymentMethod copyWith({
    String? id,
    bool? isDefault,
    String? cardLast4,
    String? cardBrand,
    String? cardholderName,
    String? cardExpiry,
    String? cardholderTaxId,
    String? pixKey,
  }) {
    return PaymentMethod(
      id: id ?? this.id,
      type: type,
      isDefault: isDefault ?? this.isDefault,
      cardLast4: cardLast4 ?? this.cardLast4,
      cardBrand: cardBrand ?? this.cardBrand,
      cardholderName: cardholderName ?? this.cardholderName,
      cardExpiry: cardExpiry ?? this.cardExpiry,
      cardholderTaxId: cardholderTaxId ?? this.cardholderTaxId,
      pixKey: pixKey ?? this.pixKey,
    );
  }
}

/// Detecta a bandeira a partir do primeiro dígito. Portado de edu-kt
/// `brandFromNumber`.
String brandFromNumber(String digits) {
  if (digits.isEmpty) return 'Cartão';
  switch (digits[0]) {
    case '4':
      return 'Visa';
    case '5':
      return 'Mastercard';
    case '3':
      return 'Amex';
    case '6':
      return 'Elo';
    default:
      return 'Cartão';
  }
}
