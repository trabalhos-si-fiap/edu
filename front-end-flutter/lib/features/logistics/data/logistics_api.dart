import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/order.dart';
import '../domain/occurrence.dart';

/// Lançada quando uma operação de separação/entrega/ocorrência falha;
/// carrega mensagem amigável pronta para exibir ao usuário.
class LogisticsException implements Exception {
  LogisticsException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Sessão obtida por `LogisticsApi.entrarNoCarregamento` — o login por
/// código de carregamento (`POST /shipments/login`). `codigo` e
/// `origemRotulo` vêm da resposta do backend e servem só para exibição (ex.:
/// cabeçalho da fila de entrega); a lista de pedidos continua vindo,
/// intacta, de `/delivery/queue`.
class SessaoCarregamento {
  const SessaoCarregamento({
    required this.accessToken,
    required this.carregamentoId,
    required this.codigo,
    required this.origemRotulo,
  });

  final String accessToken;
  final int carregamentoId;
  final String codigo;
  final String origemRotulo;
}

/// Cliente HTTP para os endpoints de separação, entrega e ocorrências do
/// Commerce Service — `/picking`, `/delivery`, `/occurrences`, não
/// `/separacao`/`/entrega`/`/ocorrencias` (esses nomes eram do router
/// interno em português; o path exposto é em inglês, ver o comentário de
/// cada seção abaixo). Medido nos métodos deste arquivo:
/// `fetchFilaSeparacao` chama `/picking/queue`, `fetchFilaEntrega` chama
/// `/delivery/queue`, `reportarFaltaEstoque` chama
/// `/occurrences/stock-shortage`. Segue a mesma convenção dos demais
/// serviços do app: usa [appAuthClient] (que já cuida do refresh
/// automático de token em 401) em vez de gerenciar o header de
/// autorização manualmente.
class LogisticsApi {
  LogisticsApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<Map<String, String>> _headers({bool json = false}) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw LogisticsException('Sessão expirada. Entre novamente.');
    }
    return {
      if (json) 'Content-Type': 'application/json',
      'Authorization': 'Bearer $access',
    };
  }

  Future<List<Pedido>> _listaPedidos(String path) async {
    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}$path'),
        headers: await _headers(),
      );
    } on LogisticsException {
      rethrow;
    } on Exception {
      throw LogisticsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw LogisticsException('Falha ao carregar pedidos (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as List<dynamic>;
    return body.map((e) => Pedido.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Pedido> _patchPedido(String path) async {
    final http.Response res;
    try {
      res = await _client.patch(
        Uri.parse('${ApiConfig.baseUrl}$path'),
        headers: await _headers(),
      );
    } on LogisticsException {
      rethrow;
    } on Exception {
      throw LogisticsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw LogisticsException(_mensagemErro(res, 'atualizar pedido'));
    }
    return Pedido.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  String _mensagemErro(http.Response res, String acao) {
    try {
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      if (body['detail'] is String) return body['detail'] as String;
    } catch (_) {
      // corpo não é JSON, ignora
    }
    return 'Falha ao $acao (${res.statusCode})';
  }

  // ── Separador ──────────────────────────────────────────────
  // Commerce Service monta este router com prefixo /picking (inglês) —
  // ver back-end/commerce-service/app/routers/separacao.py.

  Future<List<Pedido>> fetchFilaSeparacao() => _listaPedidos('/picking/queue');

  /// O pedido com os itens de agora. A fila não traz itens, e a substituição
  /// troca ou remove item no meio da separação — a tela de separação lê
  /// daqui ao abrir, em vez de confiar no payload da fila.
  Future<Pedido> fetchPedidoSeparacao(String pedidoId) async {
    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}/picking/$pedidoId'),
        headers: await _headers(),
      );
    } on LogisticsException {
      rethrow;
    } on Exception {
      throw LogisticsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw LogisticsException(_mensagemErro(res, 'carregar o pedido'));
    }
    return Pedido.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Pedido> iniciarSeparacao(String pedidoId) =>
      _patchPedido('/picking/$pedidoId/start');

  Future<Pedido> finalizarSeparacao(String pedidoId) =>
      _patchPedido('/picking/$pedidoId/finish');

  // ── Entregador ─────────────────────────────────────────────
  // Prefixo /delivery — ver back-end/commerce-service/app/routers/entrega.py.

  Future<List<Pedido>> fetchFilaEntrega() => _listaPedidos('/delivery/queue');

  Future<List<Pedido>> fetchMinhasEntregas() => _listaPedidos('/delivery/mine');

  Future<Pedido> confirmarColeta(String pedidoId) =>
      _patchPedido('/delivery/$pedidoId/collect');

  Future<Pedido> confirmarEntrega(String pedidoId) =>
      _patchPedido('/delivery/$pedidoId/deliver');

  // ── Carregamento (login por código) ───────────────────────
  // Prefixo /shipments — ver back-end/commerce-service/app/routers/shipments.py.

  /// Login de quem não tem credencial de funcionário: entra com o código do
  /// lote/carregamento e uma senha própria dele, mais nome e contato para
  /// identificação. `POST /shipments/login` **sem** header de autorização —
  /// é o ponto de entrada, não há sessão prévia para autenticar essa
  /// chamada. Por isso quem instancia `LogisticsApi` para chamar este
  /// método deve passar um `http.Client()` simples (ver
  /// `ShipmentLoginScreen`), não o `appAuthClient` compartilhado: aquele
  /// client injeta `Authorization` a partir de uma sessão anterior guardada
  /// no `TokenStore` e, num 401 de credencial errada, tentaria refresh e
  /// derrubaria a sessão em vez de só devolver a mensagem do backend.
  ///
  /// Uma sessão de carregamento não tem refresh token (dura 12h fixas), daí
  /// o `refreshToken: ''` gravado no `TokenStore` — vazio por não existir,
  /// não por falha.
  Future<SessaoCarregamento> entrarNoCarregamento({
    required String codigo,
    required String senha,
    required String nome,
    required String contato,
  }) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/shipments/login'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({
          'codigo': codigo,
          'senha': senha,
          'nome': nome,
          'contato': contato,
        }),
      );
    } on Exception {
      throw LogisticsException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw LogisticsException(_mensagemErro(res, 'entrar no carregamento'));
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final accessToken = body['access_token'] as String;
    await _tokenStore.save(accessToken: accessToken, refreshToken: '');
    return SessaoCarregamento(
      accessToken: accessToken,
      carregamentoId: body['carregamento_id'] as int,
      codigo: body['codigo'] as String,
      origemRotulo: body['origem_rotulo'] as String,
    );
  }

  // ── Ocorrências ────────────────────────────────────────────
  // Prefixo /occurrences — ver back-end/commerce-service/app/routers/ocorrencias.py.
  // Os NOMES DE CAMPO no corpo JSON continuam em português (pedido_id,
  // produto_id, motivo, nova_data_sugerida, resolucao,
  // produto_escolhido_id) — só o path do router mudou para inglês.

  /// Reportado pelo separador quando um item do pedido está em falta no
  /// estoque. O backend já sugere produtos similares automaticamente.
  Future<Ocorrencia> reportarFaltaEstoque({
    required String pedidoId,
    required String produtoId,
    required String motivo,
  }) async {
    final res = await _client.post(
      Uri.parse('${ApiConfig.baseUrl}/occurrences/stock-shortage'),
      headers: await _headers(json: true),
      body: jsonEncode({
        'pedido_id': pedidoId,
        'produto_id': produtoId,
        'motivo': motivo,
      }),
    );
    if (res.statusCode != 201) {
      throw LogisticsException(_mensagemErro(res, 'reportar falta de estoque'));
    }
    return Ocorrencia.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Reportado pelo entregador quando há atraso, sugerindo uma nova data
  /// para o aluno aceitar ou cancelar o pedido.
  Future<Ocorrencia> reportarAtrasoEntrega({
    required String pedidoId,
    required String motivo,
    required DateTime novaDataSugerida,
  }) async {
    final res = await _client.post(
      Uri.parse('${ApiConfig.baseUrl}/occurrences/delivery-delay'),
      headers: await _headers(json: true),
      body: jsonEncode({
        'pedido_id': pedidoId,
        'motivo': motivo,
        'nova_data_sugerida': novaDataSugerida.toIso8601String(),
      }),
    );
    if (res.statusCode != 201) {
      throw LogisticsException(_mensagemErro(res, 'reportar atraso'));
    }
    return Ocorrencia.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Ocorrências de um pedido — usado para badge "aguardando decisão do
  /// aluno" nas telas de separação/entrega.
  Future<List<Ocorrencia>> fetchOcorrenciasPedido(
    String pedidoId, {
    bool apenasAbertas = false,
  }) async {
    final query = apenasAbertas ? '?apenas_abertas=true' : '';
    final res = await _client.get(
      Uri.parse('${ApiConfig.baseUrl}/occurrences/order/$pedidoId$query'),
      headers: await _headers(),
    );
    if (res.statusCode != 200) {
      throw LogisticsException('Falha ao carregar ocorrências (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as List<dynamic>;
    return body.map((e) => Ocorrencia.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Detalhe de uma ocorrência (com produtos sugeridos resolvidos) — usado
  /// na tela de resolução do aluno.
  Future<Ocorrencia> fetchOcorrencia(int ocorrenciaId) async {
    final res = await _client.get(
      Uri.parse('${ApiConfig.baseUrl}/occurrences/$ocorrenciaId'),
      headers: await _headers(),
    );
    if (res.statusCode != 200) {
      throw LogisticsException('Falha ao carregar ocorrência (${res.statusCode})');
    }
    return Ocorrencia.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Resolução pelo aluno: substituir produto, remover item, aceitar nova
  /// data de entrega, ou cancelar o pedido.
  Future<void> resolverOcorrencia({
    required int ocorrenciaId,
    required String resolucao,
    String? produtoEscolhidoId,
  }) async {
    final res = await _client.post(
      Uri.parse('${ApiConfig.baseUrl}/occurrences/$ocorrenciaId/resolve'),
      headers: await _headers(json: true),
      body: jsonEncode({
        'resolucao': resolucao,
        if (produtoEscolhidoId != null) 'produto_escolhido_id': produtoEscolhidoId,
      }),
    );
    if (res.statusCode != 200) {
      throw LogisticsException(_mensagemErro(res, 'resolver ocorrência'));
    }
  }
}
