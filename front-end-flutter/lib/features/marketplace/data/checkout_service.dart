import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
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
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Retorna o id do pedido criado.
  Future<String> placeOrder({
    required String paymentMethod,
    String? addressId,
  }) async {
    final headers = await _headers();
    final res = await _send(
      () => _client.post(
        Uri.parse('${ApiConfig.baseUrl}/orders'),
        headers: {'Content-Type': 'application/json', ...headers},
        body: jsonEncode({
          'payment_method': paymentMethod,
          'address_id': ?addressId,
        }),
      ),
      accept: const {200, 201},
      error: 'Falha ao finalizar o pedido',
    );
    return (jsonDecode(res.body) as Map<String, dynamic>)['id'] as String;
  }

  /// Pede ao backend o código copia-e-cola do pedido. `null` quando não há
  /// nada para copiar (cartão).
  ///
  /// O app NÃO gera mais código de pagamento. Os dois geradores mock que
  /// viviam em `checkout_screen.dart` foram para
  /// `commerce-service/app/services/codigos_pagamento.py`, onde o dado
  /// nasce. Se esta chamada falhar, a tela mostra o erro — ela nunca monta o
  /// payload por conta própria, porque isso reintroduziria o mock.
  Future<String?> confirmPayment(String orderId) async {
    final headers = await _headers();
    final res = await _send(
      () => _client.post(
        Uri.parse('${ApiConfig.baseUrl}/orders/$orderId/confirm-payment'),
        headers: {'Content-Type': 'application/json', ...headers},
      ),
      accept: const {200},
      error: 'Falha ao emitir o código de pagamento',
    );
    return (jsonDecode(res.body) as Map<String, dynamic>)['payment_code']
        as String?;
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
