import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/product.dart';

/// Lançada quando uma operação do catálogo falha; carrega mensagem amigável.
class ProductException implements Exception {
  ProductException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Cliente HTTP do catálogo (`GET /products`, `GET /products/{id}/reviews`).
class ProductService {
  ProductService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Lista produtos. `limit` alto: o marketplace filtra client-side.
  Future<List<Product>> fetchProducts({int limit = 100}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/products?limit=$limit');
    final body = await _get(uri, 'Falha ao carregar produtos');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items
        .map((e) => Product.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Review>> fetchReviews(String productId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/products/$productId/reviews');
    final body = await _get(uri, 'Falha ao carregar avaliações');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items
        .map((e) => Review.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<String> _get(Uri uri, String errorLabel) async {
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on ProductException {
      rethrow;
    } on Exception {
      throw ProductException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ProductException('$errorLabel (${res.statusCode})');
    }
    return res.body;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw ProductException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
