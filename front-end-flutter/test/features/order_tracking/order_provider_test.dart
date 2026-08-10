import 'package:edu_ia/features/order_tracking/data/order_service.dart';
import 'package:edu_ia/features/order_tracking/domain/order_model.dart';
import 'package:edu_ia/features/order_tracking/presentation/order_provider.dart';
import 'package:flutter_test/flutter_test.dart';

/// Builds a tracking payload whose last step ('delivered') is [delivered],
/// mirroring the backend contract. [status] is the top-level contract
/// status (e.g. 'cancelled'); omitted entirely when null, to also exercise
/// the tolerant fallback for a backend that doesn't send the key yet.
OrderModel _order({required bool delivered, String? status}) {
  final now = DateTime.now();
  return OrderModel.fromJson({
    'id': 'order-1',
    'headline': 'Pedido',
    'description': '...',
    'estimated_arrival': now.toIso8601String(),
    if (status != null) 'status': status,
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

/// Returns 'separating' until [cancelAfter] calls have happened, then a
/// cancelled order. Mirrors _SequenceService but for the cancel path: a
/// cancelled order's timeline stays entirely pending, so isDelivered alone
/// never fires and the provider must key off the status field instead.
class _CancelSequenceService extends OrderService {
  _CancelSequenceService({required this.cancelAfter}) : super();

  final int cancelAfter;
  int calls = 0;

  @override
  Future<OrderModel> fetchTracking(String orderId) async {
    calls++;
    return _order(
      delivered: false,
      status: calls >= cancelAfter ? 'cancelled' : 'separating',
    );
  }
}

void main() {
  test('OrderModel.fromJson reads the status field, tolerating a missing key', () {
    expect(_order(delivered: false, status: 'cancelled').isCancelled, isTrue);
    expect(_order(delivered: false, status: 'separating').isCancelled, isFalse);
    expect(_order(delivered: false).isCancelled, isFalse); // key omitted entirely
  });

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

  test('polls until cancelled, then stops fetching', () async {
    final service = _CancelSequenceService(cancelAfter: 3);
    final provider = OrderProvider(
      service: service,
      pollInterval: const Duration(milliseconds: 20),
    );

    await provider.load('order-1'); // call #1: separating
    // Let the periodic polling run past the cancellation point.
    await Future<void>.delayed(const Duration(milliseconds: 120));

    expect(provider.order!.isCancelled, isTrue);
    final callsAtCancel = service.calls;
    expect(callsAtCancel, greaterThanOrEqualTo(3));

    // Once cancelled, polling must stop — no further calls.
    await Future<void>.delayed(const Duration(milliseconds: 80));
    expect(service.calls, callsAtCancel);
    provider.dispose();
  });

  test('load() does not poll when the order is already cancelled', () async {
    final service = _CancelSequenceService(cancelAfter: 0); // cancelled from call #1
    final provider = OrderProvider(
      service: service,
      pollInterval: const Duration(milliseconds: 20),
    );

    await provider.load('order-1');
    expect(provider.order!.isCancelled, isTrue);

    final callsAfterLoad = service.calls;
    await Future<void>.delayed(const Duration(milliseconds: 80));
    expect(service.calls, callsAfterLoad);
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
