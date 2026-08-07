import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/review.dart';

class ReviewApiException implements Exception {
  ReviewApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP de GET /reviews/today (learning-service) — lista os
/// subtemas com repetição espaçada (SM-2) vencida hoje para o aluno
/// logado.
class ReviewApi {
  ReviewApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<List<Review>> fetchReviewsToday() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw ReviewApiException('Sessão expirada. Entre novamente.');
    }
    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}/reviews/today?limit=100'),
        headers: {'Authorization': 'Bearer $access'},
      );
    } on Exception {
      throw ReviewApiException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ReviewApiException('Falha ao carregar revisões (${res.statusCode})');
    }
    final json = jsonDecode(res.body) as List<dynamic>;
    return json.map((e) => Review.fromJson(e as Map<String, dynamic>)).toList();
  }
}
