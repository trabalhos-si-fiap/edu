import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/order_model.dart';

/// Lançada quando o rastreio do pedido falha; carrega mensagem amigável
/// pronta para exibir ao usuário.
class OrderException implements Exception {
  OrderException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP para o rastreio de pedidos do backend FastAPI
/// (`GET /orders/{id}/tracking`, RESTful, resposta JSON).
///
/// Enquanto o endpoint real não está disponível, [useMock] mantém a tela
/// funcional devolvendo um [OrderModel] simulado com `Future.delayed`. Basta
/// virar a flag para `false` (ou injetar `useMock: false`) que a tela passa a
/// consumir a API real — a estrutura de chamada já está pronta.
class OrderService {
  OrderService({
    http.Client? client,
    TokenStore? tokenStore,
    this.useMock = true,
  }) : _client = client ?? http.Client(),
       _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Quando `true`, retorna dados mockados em vez de chamar o backend.
  final bool useMock;

  /// Busca o rastreio de um pedido pelo seu identificador.
  Future<OrderModel> fetchTracking(String orderId) {
    return useMock ? _fetchMock(orderId) : _fetchRemote(orderId);
  }

  // --- Integração real (FastAPI) -------------------------------------------

  Future<OrderModel> _fetchRemote(String orderId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/orders/$orderId/tracking');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on OrderException {
      rethrow;
    } on Exception {
      throw OrderException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw OrderException('Pedido não encontrado');
    }
    if (res.statusCode != 200) {
      throw OrderException('Falha ao carregar o rastreio (${res.statusCode})');
    }
    return OrderModel.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw OrderException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }

  // --- Mock temporário ------------------------------------------------------

  Future<OrderModel> _fetchMock(String orderId) async {
    await Future<void>.delayed(const Duration(milliseconds: 1200));

    // Para validar o estado de erro da UI manualmente, basta usar o id
    // 'error' (ex.: navegar com arguments: 'error').
    if (orderId == 'error') {
      throw OrderException(
        'Não conseguimos falar com a transportadora agora.',
      );
    }

    final now = DateTime.now();
    return OrderModel.fromJson({
      'id': orderId,
      'headline': 'Status do Rastreio',
      'description':
          'Seu material didático premium está em rota de entrega para '
          'sua residência.',
      'estimated_arrival': now.add(const Duration(days: 4)).toIso8601String(),
      'steps': [
        {
          'code': 'processed',
          'title': 'Processado',
          'status': 'done',
          'timestamp': now.subtract(const Duration(days: 6)).toIso8601String(),
        },
        {
          'code': 'in_transit',
          'title': 'Em Trânsito',
          'status': 'current',
          'timestamp': now.subtract(const Duration(days: 4)).toIso8601String(),
        },
        {
          'code': 'delivered',
          'title': 'Entregue',
          'status': 'pending',
          'timestamp': null,
        },
      ],
      'location': {
        'name': 'Centro de Distribuição',
        'city': 'Cajamar',
        'state': 'SP',
        'updated_at': now.subtract(const Duration(minutes: 12)).toIso8601String(),
      },
      'kit': [
        {'name': 'Apostila Ed. 5.0 Vol 2'},
        {'name': 'Caderno Editorial Pro'},
      ],
      'carrier': 'Logistics Intel Express',
      'map_url': null,
    });
  }
}
