/// Endereço de entrega. Espelha o schema `AddressOut` do backend
/// (`back-end/app/modules/addresses/schemas.py`); o `id` é o UUID retornado
/// pela API.
class Address {
  final String id;
  final String label;
  final String zipCode;
  final String street;
  final String number;
  final String complement;
  final String neighborhood;
  final String city;
  final String state;
  final bool isFavorite;

  const Address({
    required this.id,
    required this.label,
    required this.zipCode,
    required this.street,
    required this.number,
    required this.complement,
    required this.neighborhood,
    required this.city,
    required this.state,
    required this.isFavorite,
  });

  factory Address.fromJson(Map<String, dynamic> json) {
    return Address(
      id: json['id'] as String,
      label: (json['label'] as String?) ?? '',
      zipCode: json['zip_code'] as String,
      street: json['street'] as String,
      number: json['number'] as String,
      complement: (json['complement'] as String?) ?? '',
      neighborhood: json['neighborhood'] as String,
      city: json['city'] as String,
      state: json['state'] as String,
      isFavorite: (json['is_favorite'] as bool?) ?? false,
    );
  }

  /// Resumo em uma linha (rua, número — bairro — cidade/UF).
  /// Portado de `addressSummary` da CheckoutScreen do edu-kt.
  String get summary {
    final line1 = [street, number].where((s) => s.trim().isNotEmpty).join(', ');
    final cityState = [city, state].where((s) => s.trim().isNotEmpty).join('/');
    final line2 =
        [neighborhood, cityState].where((s) => s.trim().isNotEmpty).join(' — ');
    return [line1, line2].where((s) => s.trim().isNotEmpty).join(' — ');
  }
}
