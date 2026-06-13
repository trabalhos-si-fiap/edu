import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/support_message.dart';

/// Lançada quando uma operação de suporte falha; carrega mensagem amigável
/// pronta para exibir ao usuário.
class SupportException implements Exception {
  SupportException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP do chat de suporte (`GET /support`, `POST /support`).
///
/// Ambos os endpoints retornam a lista completa de mensagens do usuário
/// autenticado. O envio aceita `200` e `201` como sucesso.
class SupportService {
  SupportService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<List<SupportMessage>> fetchMessages() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/support');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on SupportException {
      rethrow;
    } on Exception {
      throw SupportException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw SupportException('Falha ao carregar o chat (${res.statusCode})');
    }
    return _parseList(res.body);
  }

  Future<List<SupportMessage>> sendMessage(String body) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/support');
    final http.Response res;
    try {
      res = await _client.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          ...await _headers(),
        },
        body: jsonEncode({'body': body}),
      );
    } on SupportException {
      rethrow;
    } on Exception {
      throw SupportException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw SupportException('Falha ao enviar a mensagem (${res.statusCode})');
    }
    return _parseList(res.body);
  }

  List<SupportMessage> _parseList(String body) {
    final list = jsonDecode(body) as List<dynamic>;
    return list
        .map((e) => SupportMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw SupportException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
