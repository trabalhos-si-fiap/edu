import 'dart:async';

import 'package:edu_ia/features/order_tracking/data/order_service.dart';
import 'package:edu_ia/features/order_tracking/data/route_service.dart';
import 'package:edu_ia/features/order_tracking/domain/order_model.dart';
import 'package:edu_ia/features/order_tracking/domain/order_route.dart';
import 'package:edu_ia/features/order_tracking/presentation/route_provider.dart';
import 'package:flutter_test/flutter_test.dart';

/// Payload de rastreio sem `courier_position`, espelhando o contrato do
/// backend antes do pedido ser despachado (ou sem posição registrada).
Map<String, dynamic> _payloadSemPosicao() {
  final now = DateTime.now();
  return {
    'id': 'pedido-1',
    'headline': 'Pedido',
    'description': '...',
    'estimated_arrival': now.toIso8601String(),
    'steps': [
      {'code': 'confirmed', 'title': 'Confirmado', 'status': 'done'},
      {'code': 'in_transit', 'title': 'Em trânsito', 'status': 'current'},
      {'code': 'delivered', 'title': 'Entregue', 'status': 'pending'},
    ],
    'location': {'name': 'CD', 'city': 'Cajamar', 'state': 'SP'},
    'kit': [
      {'name': 'Apostila'},
    ],
    'carrier': 'Carrier',
  };
}

/// Mesmo payload, em trânsito, com uma posição de transportadora na
/// [latitude] dada (longitude fixa, só a latitude varia entre chamadas nos
/// testes de polling).
Map<String, dynamic> _pedidoEmTransitoCom({required double latitude}) => {
  ..._payloadSemPosicao(),
  'courier_position': {
    'latitude': latitude,
    'longitude': -46.7,
    'updated_at': DateTime.now().toIso8601String(),
  },
};

/// Payload de um pedido já entregue (última etapa 'delivered'/'done'), com
/// posição — usado para testar que o polling para nesse estado.
Map<String, dynamic> _pedidoEntregue() => {
  ..._payloadSemPosicao(),
  'steps': [
    {'code': 'confirmed', 'title': 'Confirmado', 'status': 'done'},
    {'code': 'in_transit', 'title': 'Em trânsito', 'status': 'done'},
    {'code': 'delivered', 'title': 'Entregue', 'status': 'done'},
  ],
  'courier_position': {
    'latitude': -23.5,
    'longitude': -46.7,
    'updated_at': DateTime.now().toIso8601String(),
  },
};

/// Rota mockada, mesmo padrão de `_OkService` em route_provider_test.dart.
class _FakeRouteService extends RouteService {
  _FakeRouteService() : super(useMock: true);
}

/// Rota mínima, só para satisfazer o tipo de retorno de [_PendingRouteService]
/// — o teste que a usa nunca chega a ler `provider.route`.
OrderRoute _fakeRoute() => OrderRoute.fromJson({
  'origin': {'label': 'CD', 'latitude': -23.35, 'longitude': -46.87},
  'destination': {'label': 'Destino', 'latitude': -23.5, 'longitude': -46.6},
  'polyline': '',
  'distance_text': '10 km',
  'distance_km': 10.0,
  'duration_text': '20 min',
  'duration_minutes': 20,
});

/// Rota cujo `fetchRoute` só resolve quando o teste manda ([release]) — usada
/// para simular um `dispose()` no meio de uma busca ainda em andamento.
class _PendingRouteService extends RouteService {
  _PendingRouteService() : super();

  final _completer = Completer<OrderRoute>();

  @override
  Future<OrderRoute> fetchRoute(String orderId) => _completer.future;

  void release() => _completer.complete(_fakeRoute());
}

/// Retorna uma posição que caminha para o sul a cada chamada, simulando o
/// pedido em trânsito. Contagem em campo de instância — sem estático, mesmo
/// padrão de `_SequenceService` em order_provider_test.dart.
class _MovingPositionService extends OrderService {
  _MovingPositionService() : super();

  int calls = 0;

  @override
  Future<OrderModel> fetchTracking(String orderId) async {
    calls++;
    return OrderModel.fromJson(
      _pedidoEmTransitoCom(latitude: -23.4 - calls * 0.01),
    );
  }
}

/// Sempre devolve um pedido já entregue — usado para verificar que o
/// polling para depois da primeira leitura.
class _DeliveredPositionService extends OrderService {
  _DeliveredPositionService() : super();

  int calls = 0;

  @override
  Future<OrderModel> fetchTracking(String orderId) async {
    calls++;
    return OrderModel.fromJson(_pedidoEntregue());
  }
}

/// Primeira chamada bem-sucedida, todas as demais falham — mesma tolerância
/// que `OrderProvider._poll` já tem para uma falha transitória de rede.
class _FlakyPositionService extends OrderService {
  _FlakyPositionService() : super();

  int calls = 0;

  @override
  Future<OrderModel> fetchTracking(String orderId) async {
    calls++;
    if (calls == 1) {
      return OrderModel.fromJson(_pedidoEmTransitoCom(latitude: -23.41));
    }
    throw OrderException('boom');
  }
}

void main() {
  test('posição ausente no payload vira null, não exceção', () {
    final model = OrderModel.fromJson(_payloadSemPosicao());
    expect(model.courierPosition, isNull);
  });

  test('posição presente é lida com latitude e longitude', () {
    final model = OrderModel.fromJson({
      ..._payloadSemPosicao(),
      'courier_position': {
        'latitude': -23.45,
        'longitude': -46.7,
        'updated_at': '2026-09-09T12:00:00Z',
      },
    });
    expect(model.courierPosition!.latitude, -23.45);
    expect(model.courierPosition!.longitude, -46.7);
  });

  test('o provider do mapa segue a posição enquanto o pedido anda', () async {
    final orderService = _MovingPositionService();
    final provider = RouteProvider(
      service: _FakeRouteService(),
      orderService: orderService,
      positionInterval: const Duration(milliseconds: 10),
    );

    await provider.load('pedido-1');
    await Future<void>.delayed(const Duration(milliseconds: 35));

    expect(orderService.calls, greaterThan(1));
    expect(provider.courierPosition!.latitude, lessThan(-23.4));
    provider.dispose();
  });

  test('o provider para de seguir quando o pedido é entregue', () async {
    final orderService = _DeliveredPositionService();
    final provider = RouteProvider(
      service: _FakeRouteService(),
      orderService: orderService,
      positionInterval: const Duration(milliseconds: 10),
    );

    await provider.load('pedido-1');
    await Future<void>.delayed(const Duration(milliseconds: 40));
    final callsAposEntrega = orderService.calls;
    await Future<void>.delayed(const Duration(milliseconds: 40));

    expect(orderService.calls, callsAposEntrega);
    provider.dispose();
  });

  test('falha de rede no polling preserva a última posição boa', () async {
    final orderService = _FlakyPositionService();
    final provider = RouteProvider(
      service: _FakeRouteService(),
      orderService: orderService,
      positionInterval: const Duration(milliseconds: 10),
    );

    await provider.load('pedido-1');
    await Future<void>.delayed(const Duration(milliseconds: 45));

    expect(orderService.calls, greaterThan(1));
    expect(provider.courierPosition!.latitude, -23.41);
    provider.dispose();
  });

  test('latitude não numérica na posição vira null, não exceção', () {
    final model = OrderModel.fromJson({
      ..._payloadSemPosicao(),
      'courier_position': {
        'latitude': 'not-a-number',
        'longitude': -46.7,
        'updated_at': '2026-09-09T12:00:00Z',
      },
    });
    expect(model.courierPosition, isNull);
  });

  test(
    'dispose() enquanto a rota ainda carrega evita timer de posição órfão',
    () async {
      final routeService = _PendingRouteService();
      final orderService = _MovingPositionService();
      final provider = RouteProvider(
        service: routeService,
        orderService: orderService,
        positionInterval: const Duration(milliseconds: 10),
      );

      final loadFuture = provider.load('pedido-1');
      provider.dispose();
      routeService.release();
      await loadFuture;

      // Se um timer órfão tivesse sido criado, ele teria disparado várias
      // vezes nessa janela.
      await Future<void>.delayed(const Duration(milliseconds: 40));
      expect(orderService.calls, 0);
    },
  );
}
