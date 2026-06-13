import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../../cart/domain/cart_item.dart';

/// Lançada quando a finalização da compra falha; carrega mensagem amigável.
class CheckoutException implements Exception {
  CheckoutException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Finaliza a compra: espelha o carrinho local no carrinho do backend e cria o
/// pedido (`POST /orders`).
///
/// O backend `POST /cart/items` *soma* quantidades, então primeiro esvaziamos
/// o carrinho do backend (idempotente em caso de retry) antes de enviar os
/// itens locais.
class CheckoutService {
  CheckoutService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Retorna o id do pedido criado.
  Future<String> placeOrder({
    required List<CartItem> items,
    required String paymentMethod,
  }) async {
    final headers = await _headers();
    await _clearBackendCart(headers);

    for (final item in items) {
      await _send(
        () => _client.post(
          Uri.parse('${ApiConfig.baseUrl}/cart/items'),
          headers: {'Content-Type': 'application/json', ...headers},
          body: jsonEncode({
            'product_id': item.product.id,
            'quantity': item.quantity,
          }),
        ),
        accept: const {200, 201},
        error: 'Falha ao montar o pedido',
      );
    }

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

  Future<void> _clearBackendCart(Map<String, String> headers) async {
    final res = await _send(
      () => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/cart'),
        headers: headers,
      ),
      accept: const {200},
      error: 'Falha ao ler o carrinho',
    );
    final items =
        (jsonDecode(res.body) as Map<String, dynamic>)['items'] as List;
    for (final item in items) {
      final id = (item as Map<String, dynamic>)['product_id'];
      await _send(
        () => _client.delete(
          Uri.parse('${ApiConfig.baseUrl}/cart/items/$id'),
          headers: headers,
        ),
        accept: const {200},
        error: 'Falha ao limpar o carrinho',
      );
    }
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
