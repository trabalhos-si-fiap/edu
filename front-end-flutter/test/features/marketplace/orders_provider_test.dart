import 'package:edu_ia/features/marketplace/data/order_list_service.dart';
import 'package:edu_ia/features/marketplace/domain/order_summary.dart';
import 'package:edu_ia/features/marketplace/presentation/orders_provider.dart';
import 'package:flutter_test/flutter_test.dart';

OrderSummary _order(String id, OrderSummaryStatus status) => OrderSummary(
  id: id,
  total: '100.00',
  status: status,
  createdAt: null,
  items: const [],
);

/// Service de teste com comportamento configurável (sem rede).
class _FakeService extends OrderListService {
  _FakeService({this.onFetch});

  Future<List<OrderSummary>> Function()? onFetch;

  @override
  Future<List<OrderSummary>> fetchOrders() =>
      onFetch?.call() ?? Future.value(const []);
}

void main() {
  test('load success populates orders', () async {
    final service = _FakeService(
      onFetch: () async => [_order('a', OrderSummaryStatus.separating)],
    );
    final provider = OrdersProvider(service: service);

    await provider.load();

    expect(provider.state, OrdersViewState.success);
    expect(provider.orders, hasLength(1));
  });

  test('load failure sets error state with the exception message', () async {
    final service = _FakeService(
      onFetch: () async => throw OrderListException('boom'),
    );
    final provider = OrdersProvider(service: service);

    await provider.load();

    expect(provider.state, OrdersViewState.error);
    expect(provider.errorMessage, 'boom');
  });

  test('splits orders into active and delivered, preserving order', () async {
    final service = _FakeService(
      onFetch: () async => [
        _order('a', OrderSummaryStatus.separating),
        _order('b', OrderSummaryStatus.delivered),
        _order('c', OrderSummaryStatus.outForDelivery),
        _order('d', OrderSummaryStatus.delivered),
      ],
    );
    final provider = OrdersProvider(service: service);

    await provider.load();

    expect(provider.activeOrders.map((o) => o.id), ['a', 'c']);
    expect(provider.deliveredOrders.map((o) => o.id), ['b', 'd']);
  });

  test('isEmpty is true only after a successful load with no orders', () async {
    final provider = OrdersProvider(service: _FakeService());

    expect(provider.isEmpty, isFalse); // still loading

    await provider.load();

    expect(provider.state, OrdersViewState.success);
    expect(provider.isEmpty, isTrue);
  });
}
