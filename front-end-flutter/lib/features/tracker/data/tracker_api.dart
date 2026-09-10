import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/roadmap_step.dart';
import '../domain/study_summary.dart';

/// Lançada quando uma chamada do tracker falha; carrega mensagem pronta
/// para exibir.
class TrackerException implements Exception {
  TrackerException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente do learning-service para objetivo, percurso e resumo de estudo.
///
/// Mesma convenção dos demais clientes do app: usa [appAuthClient], que já
/// cuida do refresh automático em 401.
class TrackerApi {
  TrackerApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<Map<String, String>> _headers({bool json = false}) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw TrackerException('Sessão expirada. Entre novamente.');
    }
    return {
      if (json) 'Content-Type': 'application/json',
      'Authorization': 'Bearer $access',
    };
  }

  /// Extrai a frase do servidor de um corpo de erro do FastAPI.
  ///
  /// `detail` chega como String nas exceções da aplicação e como LISTA de
  /// objetos `{loc, msg, type}` nas de validação (422) — é dessa lista que
  /// sai "A data-alvo não pode estar no passado". Uma mensagem genérica no
  /// lugar mandaria o aluno procurar no campo errado.
  String _mensagemErro(http.Response res, String acao) {
    try {
      final corpo = jsonDecode(res.body);
      if (corpo is Map<String, dynamic>) {
        final detalhe = corpo['detail'];
        if (detalhe is String) return detalhe;
        if (detalhe is List && detalhe.isNotEmpty) {
          final primeiro = detalhe.first;
          if (primeiro is Map && primeiro['msg'] is String) {
            return (primeiro['msg'] as String).replaceFirst('Value error, ', '');
          }
        }
      }
    } catch (_) {
      // corpo não é JSON — cai na mensagem genérica abaixo
    }
    return 'Falha ao $acao (${res.statusCode})';
  }

  Future<http.Response> _enviar(
    Future<http.Response> Function() chamada,
    String acao,
  ) async {
    try {
      return await chamada();
    } on TrackerException {
      rethrow;
    } on Exception {
      throw TrackerException('Não foi possível conectar ao servidor');
    }
  }

  Future<StudySummary> fetchSummary() async {
    final res = await _enviar(
      () async => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/profile/summary'),
        headers: await _headers(),
      ),
      'carregar seu resumo',
    );
    if (res.statusCode != 200) {
      throw TrackerException(_mensagemErro(res, 'carregar seu resumo'));
    }
    return StudySummary.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Roadmap> fetchRoadmap({int limit = 50, int offset = 0}) async {
    final res = await _enviar(
      () async => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/roadmap?limit=$limit&offset=$offset'),
        headers: await _headers(),
      ),
      'carregar seu percurso',
    );
    if (res.statusCode != 200) {
      throw TrackerException(_mensagemErro(res, 'carregar seu percurso'));
    }
    return Roadmap.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// O objetivo atual, ou `null` para quem pulou o onboarding.
  Future<Goal?> fetchGoal() async {
    final res = await _enviar(
      () async => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/onboarding'),
        headers: await _headers(),
      ),
      'carregar seu objetivo',
    );
    if (res.statusCode != 200) {
      throw TrackerException(_mensagemErro(res, 'carregar seu objetivo'));
    }
    final corpo = jsonDecode(res.body);
    if (corpo == null) return null;
    final mapa = corpo as Map<String, dynamic>;
    // `GET /onboarding` devolve o objetivo cru (sem os contadores de dias,
    // que são do resumo) — os dois campos entram como zero.
    return Goal.fromJson({
      'titulo': mapa['titulo'],
      'data_alvo': mapa['data_alvo'],
      'dias_decorridos': 0,
      'dias_totais': 0,
    });
  }

  /// Cria (`update: false`) ou altera (`update: true`) o objetivo.
  /// Devolve quantas etapas o percurso passou a ter.
  Future<int> saveGoal({
    required String title,
    required DateTime targetDate,
    required bool update,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/onboarding');
    // Data sem hora: o backend recebe `date`, e mandar o ISO completo com
    // fuso faria a data virar o dia anterior para quem está a oeste de
    // Greenwich.
    final corpo = jsonEncode({
      'titulo': title,
      'data_alvo':
          '${targetDate.year.toString().padLeft(4, '0')}-'
          '${targetDate.month.toString().padLeft(2, '0')}-'
          '${targetDate.day.toString().padLeft(2, '0')}',
    });
    final res = await _enviar(
      () async => update
          ? _client.put(uri, headers: await _headers(json: true), body: corpo)
          : _client.post(uri, headers: await _headers(json: true), body: corpo),
      'salvar seu objetivo',
    );
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw TrackerException(_mensagemErro(res, 'salvar seu objetivo'));
    }
    final mapa = jsonDecode(res.body) as Map<String, dynamic>;
    return (mapa['etapas_geradas'] as num?)?.toInt() ?? 0;
  }
}
