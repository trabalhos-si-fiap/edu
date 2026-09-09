import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/partner.dart';
import '../domain/product.dart';

/// Lançada quando uma operação de parceiros falha; carrega mensagem amigável.
class PartnerException implements Exception {
  PartnerException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Cliente HTTP de parceiros (`GET /partners`, `GET /products?partner_id=`).
/// Segue o mesmo molde de [ProductService]: mesmo [appAuthClient], mesmo
/// [TokenStore], mesmo padrão de `_get`/`_headers`.
class PartnerService {
  PartnerService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Quais parceiros o app deve mostrar. A resposta é dado, não configuração
  /// do app: hoje ela tem um elemento, e o app não sabe disso.
  Future<List<Partner>> fetchActivePartners() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/partners?active=true&limit=50');
    final body = await _get(uri, 'Falha ao carregar parceiros');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items
        .map((e) => Partner.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Product>> fetchPartnerProducts(int partnerId) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/products?partner_id=$partnerId&limit=50',
    );
    final body = await _get(uri, 'Falha ao carregar o catálogo do parceiro');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items
        .map((e) => Product.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<String> _get(Uri uri, String errorLabel) async {
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on PartnerException {
      rethrow;
    } on Exception {
      throw PartnerException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw PartnerException('$errorLabel (${res.statusCode})');
    }
    return res.body;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw PartnerException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
