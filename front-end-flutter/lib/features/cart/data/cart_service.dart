import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../../marketplace/domain/product.dart';
import '../domain/cart_item.dart';

/// Lançada quando uma operação do carrinho falha; carrega mensagem amigável.
class CartException implements Exception {
  CartException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Cliente HTTP do carrinho do backend (`/cart`). Cada método retorna o
/// carrinho completo como o servidor o vê, mapeado para [CartItem].
class CartService {
  CartService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<List<CartItem>> fetch() async {
    final res = await _send(
      () async => _client.get(_uri(''), headers: await _headers()),
      'Falha ao carregar o carrinho',
    );
    return _parse(res.body);
  }

  Future<List<CartItem>> addItem(String productId, int quantity) async {
    final res = await _send(
      () async => _client.post(
        _uri('/items'),
        headers: {'Content-Type': 'application/json', ...await _headers()},
        body: jsonEncode({'product_id': productId, 'quantity': quantity}),
      ),
      'Falha ao adicionar ao carrinho',
    );
    return _parse(res.body);
  }

  Future<List<CartItem>> removeItem(String productId, {int? quantity}) async {
    final query = quantity == null ? '' : '?quantity=$quantity';
    final res = await _send(
      () async =>
          _client.delete(_uri('/items/$productId$query'), headers: await _headers()),
      'Falha ao remover do carrinho',
    );
    return _parse(res.body);
  }

  Uri _uri(String suffix) => Uri.parse('${ApiConfig.baseUrl}/cart$suffix');

  List<CartItem> _parse(String body) {
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items.map((e) {
      final m = e as Map<String, dynamic>;
      return CartItem(
        product: Product(
          id: m['product_id'] as String,
          name: (m['name'] as String?) ?? '',
          type: (m['type'] as String?) ?? '',
          subtype: (m['subtype'] as String?) ?? '',
          description: '',
          price: double.tryParse('${m['price']}') ?? 0.0,
          imageUrl: (m['image_url'] as String?) ?? '',
          ratingAvg: (m['rating_avg'] as num?)?.toDouble() ?? 0.0,
          ratingCount: (m['rating_count'] as num?)?.toInt() ?? 0,
        ),
        quantity: (m['quantity'] as num?)?.toInt() ?? 0,
      );
    }).toList();
  }

  Future<http.Response> _send(
    Future<http.Response> Function() request,
    String error,
  ) async {
    final http.Response res;
    try {
      res = await request();
    } on CartException {
      rethrow;
    } on Exception {
      throw CartException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw CartException('$error (${res.statusCode})');
    }
    return res;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw CartException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
