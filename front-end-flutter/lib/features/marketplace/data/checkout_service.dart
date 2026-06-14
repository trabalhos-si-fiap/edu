import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';

/// Lançada quando a finalização da compra falha; carrega mensagem amigável.
class CheckoutException implements Exception {
  CheckoutException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Finaliza a compra criando o pedido (`POST /orders`). O backend lê o próprio
/// carrinho do usuário e o esvazia na mesma transação, então não há staging
/// aqui — o carrinho do backend já está sincronizado com o [CartStore].
class CheckoutService {
  CheckoutService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Retorna o id do pedido criado.
  Future<String> placeOrder({required String paymentMethod}) async {
    final headers = await _headers();
    final res = await _send(
      () => _client.post(
        Uri.parse('${ApiConfig.baseUrl}/orders'),
        headers: {'Content-Type': 'application/json', ...headers},
        body: jsonEncode({'payment_method': paymentMethod}),
      ),
      accept: const {200, 201},
      error: 'Falha ao finalizar o pedido',
    );
    return (jsonDecode(res.body) as Map<String, dynamic>)['id'] as String;
  }

  Future<http.Response> _send(
    Future<http.Response> Function() request, {
    required Set<int> accept,
    required String error,
  }) async {
    final http.Response res;
    try {
      res = await request();
    } on CheckoutException {
      rethrow;
    } on Exception {
      throw CheckoutException('Não foi possível conectar ao servidor');
    }
    if (!accept.contains(res.statusCode)) {
      throw CheckoutException('$error (${res.statusCode})');
    }
    return res;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw CheckoutException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
