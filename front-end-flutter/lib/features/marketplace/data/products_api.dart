import 'dart:convert';

import 'package:edu_ia/core/network/api_config.dart';
import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:http/http.dart' as http;

/// Lançada quando uma operação de produtos falha; carrega mensagem amigável.
class ProductsException implements Exception {
  final String message;
  ProductsException(this.message);
  @override
  String toString() => message;
}

/// Cliente HTTP para o endpoint de produtos do backend
/// (`/products`, em `back-end/app/modules/products/routes.py`).
///
/// Toda chamada exige um access token salvo (usuário autenticado); sem ele as
/// operações lançam [ProductsException].
class ProductsApi {
  ProductsApi({http.Client? client, TokenStore? tokenStore})
      : _client = client ?? http.Client(),
        _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw ProductsException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }

  /// `GET /products` — lista paginada de produtos, com busca opcional.
  Future<List<Product>> list({String? q, int limit = 20, int offset = 0}) async {
    final headers = await _headers();
    final query = {
      'limit': '$limit',
      'offset': '$offset',
      if (q != null && q.trim().isNotEmpty) 'q': q.trim(),
    };
    final uri =
        Uri.parse('${ApiConfig.baseUrl}/products').replace(queryParameters: query);
    final http.Response res;
    try {
      res = await _client.get(uri, headers: headers);
    } on ProductsException {
      rethrow;
    } on Exception {
      throw ProductsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ProductsException('Falha ao carregar produtos (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final items = body['items'] as List<dynamic>;
    return items
        .map((e) => Product.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
  }

  /// `GET /products/{productId}/reviews` — avaliações de um produto.
  Future<List<Review>> reviews(String productId) async {
    final headers = await _headers();
    final uri = Uri.parse('${ApiConfig.baseUrl}/products/$productId/reviews');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: headers);
    } on ProductsException {
      rethrow;
    } on Exception {
      throw ProductsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ProductsException('Falha ao carregar avaliações (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final items = body['items'] as List<dynamic>;
    return items
        .map((e) => Review.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
  }
}
