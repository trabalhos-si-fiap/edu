import 'package:edu_ia/features/order_tracking/data/order_service.dart';
import 'package:edu_ia/features/order_tracking/domain/order_model.dart';
import 'package:edu_ia/features/order_tracking/presentation/order_provider.dart';
import 'package:flutter_test/flutter_test.dart';

/// Builds a tracking payload whose last step ('delivered') is [delivered],
/// mirroring the backend contract.
OrderModel _order({required bool delivered}) {
  final now = DateTime.now();
  return OrderModel.fromJson({
    'id': 'order-1',
    'headline': 'Pedido',
    'description': '...',
    'estimated_arrival': now.toIso8601String(),
    'steps': [
      {'code': 'confirmed', 'title': 'Confirmado', 'status': 'done'},
      {
        'code': 'separating',
        'title': 'Em separação',
        'status': delivered ? 'done' : 'current',
      },
      {'code': 'out_for_delivery', 'title': 'Saiu', 'status': delivered ? 'done' : 'pending'},
      {
        'code': 'delivered',
        'title': 'Entregue',
        'status': delivered ? 'done' : 'pending',
      },
    ],
    'location': {'name': 'CD', 'city': 'Cajamar', 'state': 'SP'},
    'kit': [
      {'name': 'Apostila'},
    ],
    'carrier': 'Carrier',
  });
}

/// Returns 'separating' until [deliverAfter] calls have happened, then
/// 'delivered'. Counts how many times the endpoint was hit.
class _SequenceService extends OrderService {
  _SequenceService({required this.deliverAfter}) : super();

  final int deliverAfter;
  int calls = 0;

  @override
  Future<OrderModel> fetchTracking(String orderId) async {
    calls++;
    return _order(delivered: calls >= deliverAfter);
  }
}

class _FailingService extends OrderService {
  _FailingService() : super();
  @override
  Future<OrderModel> fetchTracking(String orderId) async =>
      throw OrderException('boom');
}

void main() {
  test('load() reaches success and exposes the order', () async {
    final provider = OrderProvider(
      service: _SequenceService(deliverAfter: 99),
      pollInterval: const Duration(milliseconds: 20),
    );
    await provider.load('order-1');

    expect(provider.state, OrderViewState.success);
    expect(provider.order, isNotNull);
    expect(provider.order!.isDelivered, isFalse);
    provider.dispose();
  });

  test('polls until delivered, then stops fetching', () async {
    final service = _SequenceService(deliverAfter: 3);
    final provider = OrderProvider(
      service: service,
      pollInterval: const Duration(milliseconds: 20),
    );

    await provider.load('order-1'); // call #1: separating
    // Let the periodic polling run past the delivery point.
    await Future<void>.delayed(const Duration(milliseconds: 120));

    expect(provider.order!.isDelivered, isTrue);
    final callsAtDelivery = service.calls;
    expect(callsAtDelivery, greaterThanOrEqualTo(3));

    // Once delivered, polling must stop — no further calls.
    await Future<void>.delayed(const Duration(milliseconds: 80));
    expect(service.calls, callsAtDelivery);
    provider.dispose();
  });

  test('load() maps OrderException to the error state and does not poll', () async {
    final provider = OrderProvider(
      service: _FailingService(),
      pollInterval: const Duration(milliseconds: 20),
    );
    await provider.load('order-1');

    expect(provider.state, OrderViewState.error);
    expect(provider.errorMessage, 'boom');

    // No successful load => no polling timer scheduled.
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(provider.state, OrderViewState.error);
    provider.dispose();
  });
}
