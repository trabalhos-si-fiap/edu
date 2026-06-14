/// Tipos de método de pagamento. Portado de edu-kt `PaymentMethodType`.
enum PaymentMethodType { creditCard, pix, boleto }

/// Valor em snake_case usado pelo backend (`PaymentMethodType` em
/// `back-end/app/modules/payment_methods/enums.py`).
extension PaymentMethodTypeApi on PaymentMethodType {
  String get apiValue {
    switch (this) {
      case PaymentMethodType.creditCard:
        return 'credit_card';
      case PaymentMethodType.pix:
        return 'pix';
      case PaymentMethodType.boleto:
        return 'boleto';
    }
  }
}

PaymentMethodType _typeFromApi(String value) {
  switch (value) {
    case 'credit_card':
      return PaymentMethodType.creditCard;
    case 'pix':
      return PaymentMethodType.pix;
    case 'boleto':
      return PaymentMethodType.boleto;
    default:
      return PaymentMethodType.creditCard;
  }
}

/// Método de pagamento salvo. Portado de edu-kt `PaymentMethod`.
class PaymentMethod {
  final String id;
  final PaymentMethodType type;
  final bool isDefault;
  final String? cardLast4;
  final String? cardBrand;
  final String? cardholderName;
  final String? cardExpiry; // MMYY
  final String? pixKey;

  const PaymentMethod({
    required this.id,
    required this.type,
    this.isDefault = false,
    this.cardLast4,
    this.cardBrand,
    this.cardholderName,
    this.cardExpiry,
    this.pixKey,
  });

  /// Espelha o schema `PaymentMethodOut` do backend
  /// (`back-end/app/modules/payment_methods/schemas.py`); o `id` é o UUID
  /// retornado pela API e `card_expiry` vem como MMYY.
  factory PaymentMethod.fromJson(Map<String, dynamic> json) {
    return PaymentMethod(
      id: json['id'] as String,
      type: _typeFromApi(json['type'] as String),
      isDefault: (json['is_default'] as bool?) ?? false,
      cardLast4: json['card_last4'] as String?,
      cardBrand: json['card_brand'] as String?,
      cardholderName: json['cardholder_name'] as String?,
      cardExpiry: json['card_expiry'] as String?,
      pixKey: json['pix_key'] as String?,
    );
  }

  PaymentMethod copyWith({
    String? id,
    bool? isDefault,
    String? cardLast4,
    String? cardBrand,
    String? cardholderName,
    String? cardExpiry,
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
