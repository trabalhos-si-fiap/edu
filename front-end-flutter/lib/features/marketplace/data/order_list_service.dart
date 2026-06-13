import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/order_summary.dart';

/// Lançada quando a listagem de pedidos falha; carrega mensagem amigável
/// pronta para exibir ao usuário.
class OrderListException implements Exception {
  OrderListException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP da listagem de pedidos do usuário (`GET /orders`).
///
/// Retorna os pedidos do usuário autenticado, dos mais recentes aos mais
/// antigos (ordenação definida pelo backend).
class OrderListService {
  OrderListService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<List<OrderSummary>> fetchOrders() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/orders');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on OrderListException {
      rethrow;
    } on Exception {
      throw OrderListException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw OrderListException(
        'Falha ao carregar seus pedidos (${res.statusCode})',
      );
    }
    final list = jsonDecode(res.body) as List<dynamic>;
    return list
        .map((e) => OrderSummary.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw OrderListException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
