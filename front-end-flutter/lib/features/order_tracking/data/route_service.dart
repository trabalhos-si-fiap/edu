import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/order_route.dart';

/// Lançada quando a busca da rota do mapa falha; carrega mensagem amigável.
class RouteException implements Exception {
  RouteException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP para a rota do pedido no mapa
/// (`GET /orders/{id}/route`, resposta JSON `RouteOut`).
///
/// Mesmo padrão do [OrderService]: consome a API real por padrão; injete
/// `useMock: true` para desenvolver a tela do mapa sem backend/chave.
class RouteService {
  RouteService({
    http.Client? client,
    TokenStore? tokenStore,
    this.useMock = false,
  }) : _client = client ?? http.Client(),
       _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Quando `true`, retorna uma rota mockada em vez de chamar o backend.
  final bool useMock;

  Future<OrderRoute> fetchRoute(String orderId) {
    return useMock ? _fetchMock(orderId) : _fetchRemote(orderId);
  }

  Future<OrderRoute> _fetchRemote(String orderId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/orders/$orderId/route');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on RouteException {
      rethrow;
    } on Exception {
      throw RouteException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw RouteException('Rota não encontrada para este pedido');
    }
    if (res.statusCode != 200) {
      throw RouteException('Falha ao carregar o mapa (${res.statusCode})');
    }
    return OrderRoute.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw RouteException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }

  // --- Mock temporário ------------------------------------------------------

  Future<OrderRoute> _fetchMock(String orderId) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    return OrderRoute.fromJson({
      'origin': {
        'label': 'Centro de Distribuição',
        'latitude': -23.3558,
        'longitude': -46.8769,
      },
      'destination': {
        'label': 'Endereço de entrega',
        'latitude': -23.561414,
        'longitude': -46.655881,
      },
      'polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
      'distance_text': '32 km',
      'distance_km': 32.0,
      'duration_text': '48 min',
      'duration_minutes': 48,
    });
  }
}
