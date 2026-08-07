import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/quiz_models.dart';

/// Lançada quando uma chamada ao learning-service falha; carrega mensagem
/// amigável pronta para exibir ao usuário.
class QuizApiException implements Exception {
  QuizApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP do learning-service: catálogo de matérias/temas e o fluxo
/// de diagnóstico adaptativo (gera questionário -> submete respostas ->
/// recebe domínio calculado + recomendações + mensagem do tutor).
class QuizApi {
  QuizApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw QuizApiException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }

  Future<dynamic> _get(String path) async {
    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}$path'),
        headers: await _headers(),
      );
    } on QuizApiException {
      rethrow;
    } on Exception {
      throw QuizApiException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw QuizApiException('Nenhum conteúdo encontrado ainda.');
    }
    if (res.statusCode != 200) {
      throw QuizApiException('Falha ao carregar dados (${res.statusCode})');
    }
    return jsonDecode(res.body);
  }

  /// GET /subjects — lista de matérias disponíveis.
  Future<List<Materia>> fetchMaterias() async {
    final json = await _get('/subjects?limit=200');
    return (json as List<dynamic>)
        .map((e) => Materia.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /subjects/{id}/topics — temas de uma matéria.
  Future<List<Tema>> fetchTemas(int materiaId) async {
    final json = await _get('/subjects/$materiaId/topics?limit=200');
    return (json as List<dynamic>)
        .map((e) => Tema.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /topics/{tema_id}/quiz — monta o questionário de diagnóstico do
  /// tema inteiro (15 questões por padrão, distribuídas entre os
  /// subtemas). Nunca inclui o gabarito.
  Future<List<QuestaoQuiz>> fetchQuestoesDoTema(
    int temaId, {
    int quantidade = 15,
  }) async {
    final json = await _get('/topics/$temaId/quiz?quantidade=$quantidade');
    return (json as List<dynamic>)
        .map((e) => QuestaoQuiz.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /diagnostic/answer — submete todas as respostas do questionário
  /// de uma vez e recebe o resultado completo (domínio por subtema, ação
  /// recomendada, recomendações de conteúdo, mensagem do tutor).
  Future<DiagnosticoResultado> enviarDiagnostico({
    required int temaId,
    required List<RespostaItem> respostas,
  }) async {
    final headers = await _headers();
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/diagnostic/answer'),
        headers: {'Content-Type': 'application/json', ...headers},
        body: jsonEncode({
          'tema_id': temaId,
          'respostas': respostas.map((r) => r.toJson()).toList(),
        }),
      );
    } on Exception {
      throw QuizApiException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw QuizApiException(
        'Falha ao enviar suas respostas (${res.statusCode})',
      );
    }
    return DiagnosticoResultado.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }
}
