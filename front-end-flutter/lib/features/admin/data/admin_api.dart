import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../../logistics/domain/order.dart';
import '../domain/analytics.dart';
import '../domain/shipment.dart';

/// Lançada quando uma chamada ao analytics-service falha; carrega mensagem
/// amigável pronta para exibir ao usuário.
class AdminApiException implements Exception {
  AdminApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP para os endpoints do Analytics Service (`/analytics/*`),
/// todos protegidos por `role=admin` no backend. Segue a mesma convenção
/// dos demais serviços do app: usa [appAuthClient] (refresh automático de
/// token em 401) em vez de gerenciar o header de autorização manualmente.
class AdminApi {
  AdminApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw AdminApiException('Sessão expirada. Entre novamente.');
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
    } on AdminApiException {
      rethrow;
    } on Exception {
      throw AdminApiException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 403) {
      throw AdminApiException(
        'Seu usuário não tem permissão de administrador.',
      );
    }
    if (res.statusCode != 200) {
      throw AdminApiException(
        'Falha ao carregar dados do painel (${res.statusCode})',
      );
    }
    return jsonDecode(res.body);
  }

  Future<dynamic> _post(
    String path,
    Map<String, dynamic> body, {
    int expect = 200,
  }) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}$path'),
        headers: {'Content-Type': 'application/json', ...await _headers()},
        body: jsonEncode(body),
      );
    } on AdminApiException {
      rethrow;
    } on Exception {
      throw AdminApiException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 403) {
      throw AdminApiException(
        'Seu usuário não tem permissão de administrador.',
      );
    }
    // 409 é regra de negócio do carregamento (origem divergente do pedido,
    // ou pedido já atribuído a outro carregamento): o backend manda a
    // mensagem PRONTA para exibir. Mesma convenção de
    // `CartService._detailOrNull` para o carrinho de origem mista — a
    // mensagem é contrato de UI, o app não reescreve.
    if (res.statusCode == 409) {
      final message = _detailOrNull(res.body);
      if (message != null) throw AdminApiException(message);
    }
    if (res.statusCode != expect) {
      throw AdminApiException(
        'Falha ao processar solicitação (${res.statusCode})',
      );
    }
    return res.body.isEmpty ? null : jsonDecode(res.body);
  }

  /// Relatório executivo (métricas agregadas + resumo em texto gerado por
  /// LLM) do período dos últimos [dias] dias. Alimenta a tela inicial do
  /// admin.
  Future<ResumoExecutivo> fetchResumoExecutivo({int dias = 7}) async {
    final json = await _get('/analytics/executive-summary?dias=$dias');
    return ResumoExecutivo.fromJson(json as Map<String, dynamic>);
  }

  /// Contagem de eventos do event log por tipo (ex: order.created,
  /// order.delivered, diagnostic.answered...). Alimenta os KPIs do Painel
  /// Analítico.
  Future<List<TipoContagem>> fetchResumoEventos() async {
    final json = await _get('/analytics/summary');
    return (json as List<dynamic>)
        .map((e) => TipoContagem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Contagem de pedidos por status atual (criado, confirmado,
  /// despachado, em trânsito, entregue...). Alimenta o mini gráfico da
  /// tela inicial e os KPIs do Painel Analítico.
  Future<List<StatusContagem>> fetchEntregasPorStatus() async {
    final json = await _get('/analytics/deliveries');
    return (json as List<dynamic>)
        .map((e) => StatusContagem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Detecção de anomalias: compara a contagem de eventos de hoje com a
  /// média histórica dos últimos [diasHistorico] dias (z-score). Alimenta
  /// a seção de alertas do Painel Analítico.
  Future<AnomaliasResponse> fetchAnomalias({int diasHistorico = 30}) async {
    final json = await _get(
      '/analytics/anomalies?dias_historico=$diasHistorico',
    );
    return AnomaliasResponse.fromJson(json as Map<String, dynamic>);
  }

  /// Carregamentos existentes (mais recentes primeiro, no critério do
  /// backend). Alimenta a listagem da aba Carregamentos — o item do
  /// backend (`CarregamentoOut`) nunca carrega `senha`, só a criação.
  Future<List<Shipment>> fetchCarregamentos() async {
    final json = await _get('/shipments?limit=50');
    final items = (json as Map<String, dynamic>)['items'] as List<dynamic>;
    return items
        .map((e) => Shipment.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Cria um carregamento para a transportadora [transportadoraId]. A
  /// senha só existe em [ShipmentCriado.senha], nesta resposta — nenhuma
  /// leitura posterior a devolve.
  Future<ShipmentCriado> criarCarregamento(int transportadoraId) async {
    final json = await _post('/shipments', {
      'transportadora_id': transportadoraId,
    }, expect: 201);
    return ShipmentCriado.fromJson(json as Map<String, dynamic>);
  }

  /// Atribui o pedido [pedidoId] ao carregamento [carregamentoId]. Lança
  /// [AdminApiException] com a mensagem do servidor (verbatim) quando o
  /// pedido é de outra origem ou já está em outro carregamento (409).
  Future<void> atribuirPedido({
    required int carregamentoId,
    required String pedidoId,
  }) async {
    await _post('/shipments/$carregamentoId/orders', {'pedido_id': pedidoId});
  }

  /// Pedidos já atribuídos a um carregamento. Reaproveita [Pedido.fromJson]
  /// (logistics/domain/order.dart) — é a mesma visão de staff que a fila de
  /// separação/entrega já lê, o backend devolve o mesmo `PedidoStaffOut`.
  Future<List<Pedido>> fetchPedidosDoCarregamento(int carregamentoId) async {
    final json = await _get('/shipments/$carregamentoId/orders?limit=100');
    return (json as List<dynamic>)
        .map((e) => Pedido.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Transportadoras parceiras, para o seletor de criação de carregamento.
  Future<List<Carrier>> fetchTransportadoras() async {
    final json = await _get('/carriers?limit=100');
    final items = (json as Map<String, dynamic>)['items'] as List<dynamic>;
    return items
        .map((e) => Carrier.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}

/// Lê `detail` do corpo, ou `null` se o corpo não for um JSON com `detail`
/// legível. Sem isso, uma página de erro HTML de um proxy viraria a
/// mensagem que o admin lê. Mesma função de `cart_service.dart` — três
/// linhas repetidas, não uma abstração compartilhada prematura (KISS).
String? _detailOrNull(String body) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) {
      final detail = decoded['detail'];
      if (detail is String && detail.trim().isNotEmpty) return detail;
    }
  } on FormatException {
    return null;
  }
  return null;
}
