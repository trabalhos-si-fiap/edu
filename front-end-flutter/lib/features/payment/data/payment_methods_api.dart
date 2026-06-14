import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/payment_method.dart';

/// Lançada quando uma operação de método de pagamento falha; carrega mensagem
/// amigável para a UI.
class PaymentMethodException implements Exception {
  PaymentMethodException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP para o CRUD de métodos de pagamento do backend
/// (`/payment-methods`, em `back-end/app/modules/payment_methods/routes.py`).
///
/// Toda chamada exige um access token salvo (usuário autenticado); sem ele as
/// operações lançam [PaymentMethodException]. O backend suporta criar, listar,
/// definir o padrão (`PATCH is_default`) e remover — não há edição de campos.
class PaymentMethodsApi {
  PaymentMethodsApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  static final Uri _collection = Uri.parse(
    '${ApiConfig.baseUrl}/payment-methods',
  );

  Future<Map<String, String>> _headers({bool json = false}) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw PaymentMethodException('Sessão expirada. Entre novamente.');
    }
    return {
      if (json) 'Content-Type': 'application/json',
      'Authorization': 'Bearer $access',
    };
  }

  /// `GET /payment-methods` — métodos do usuário (padrão primeiro).
  Future<List<PaymentMethod>> list() async {
    final http.Response res;
    try {
      res = await _client.get(_collection, headers: await _headers());
    } on PaymentMethodException {
      rethrow;
    } on Exception {
      throw PaymentMethodException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw PaymentMethodException(
        'Falha ao carregar métodos de pagamento (${res.statusCode})',
      );
    }
    final body = jsonDecode(res.body) as List<dynamic>;
    return body
        .map((e) => PaymentMethod.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
  }

  /// `POST /payment-methods` — cria um método e retorna o registro salvo.
  Future<PaymentMethod> create(PaymentMethodInput input) async {
    final http.Response res;
    try {
      res = await _client.post(
        _collection,
        headers: await _headers(json: true),
        body: jsonEncode(input.toJson()),
      );
    } on PaymentMethodException {
      rethrow;
    } on Exception {
      throw PaymentMethodException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 201) {
      throw PaymentMethodException(_messageFor(res, 'salvar'));
    }
    return PaymentMethod.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// `PATCH /payment-methods/{id}` marcando como padrão.
  Future<PaymentMethod> setDefault(String id) async {
    final http.Response res;
    try {
      res = await _client.patch(
        Uri.parse('${ApiConfig.baseUrl}/payment-methods/$id'),
        headers: await _headers(json: true),
        body: jsonEncode({'is_default': true}),
      );
    } on PaymentMethodException {
      rethrow;
    } on Exception {
      throw PaymentMethodException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw PaymentMethodException('Método de pagamento não encontrado');
    }
    if (res.statusCode != 200) {
      throw PaymentMethodException('Falha ao definir padrão (${res.statusCode})');
    }
    return PaymentMethod.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// `DELETE /payment-methods/{id}`.
  Future<void> delete(String id) async {
    final http.Response res;
    try {
      res = await _client.delete(
        Uri.parse('${ApiConfig.baseUrl}/payment-methods/$id'),
        headers: await _headers(),
      );
    } on PaymentMethodException {
      rethrow;
    } on Exception {
      throw PaymentMethodException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw PaymentMethodException('Método de pagamento não encontrado');
    }
    if (res.statusCode != 204) {
      throw PaymentMethodException(
        'Falha ao remover método (${res.statusCode})',
      );
    }
  }

  String _messageFor(http.Response res, String action) {
    if (res.statusCode == 422) {
      return 'Confira os campos e tente novamente';
    }
    return 'Falha ao $action método de pagamento (${res.statusCode})';
  }
}

/// Payload de criação. Os nomes em snake_case casam com `PaymentMethodIn` do
/// backend, que usa `extra="forbid"` — só enviamos campos previstos pelo
/// schema (dados sensíveis como número completo, CVV e CPF/CNPJ nunca trafegam).
///
/// PIX e boleto não carregam dados salvos: o código de pagamento é gerado na
/// finalização do pedido, então só enviamos `type` e `is_default`.
class PaymentMethodInput {
  final PaymentMethodType type;
  final bool isDefault;
  final String? cardLast4;
  final String? cardBrand;
  final String? cardholderName;
  final String? cardExpiry; // MMYY

  const PaymentMethodInput({
    required this.type,
    required this.isDefault,
    this.cardLast4,
    this.cardBrand,
    this.cardholderName,
    this.cardExpiry,
  });

  Map<String, dynamic> toJson() => {
    'type': type.apiValue,
    'is_default': isDefault,
    if (cardLast4 != null) 'card_last4': cardLast4,
    if (cardBrand != null) 'card_brand': cardBrand,
    if (cardholderName != null) 'cardholder_name': cardholderName,
    if (cardExpiry != null) 'card_expiry': cardExpiry,
  };
}
