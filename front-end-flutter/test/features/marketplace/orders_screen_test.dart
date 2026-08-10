import 'package:edu_ia/features/marketplace/data/order_list_service.dart';
import 'package:edu_ia/features/marketplace/domain/order_summary.dart';
import 'package:edu_ia/features/marketplace/presentation/orders_provider.dart';
import 'package:edu_ia/features/marketplace/presentation/orders_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

OrderSummary _order({
  required String id,
  required OrderSummaryStatus status,
  String total = '242.00',
  List<OrderItemSummary> items = const [],
}) =>
    OrderSummary(
      id: id,
      total: total,
      status: status,
      createdAt: DateTime.utc(2026, 4, 22),
      items: items,
    );

class _FakeService extends OrderListService {
  _FakeService(this.orders);
  final List<OrderSummary> orders;

  @override
  Future<List<OrderSummary>> fetchOrders() async => orders;
}

class _FailingService extends OrderListService {
  @override
  Future<List<OrderSummary>> fetchOrders() async =>
      throw OrderListException('falhou');
}

Widget _harness(OrdersProvider provider) => MaterialApp(
      home: ChangeNotifierProvider.value(
        value: provider,
        child: const OrdersView(),
      ),
    );

void main() {
  testWidgets('renders an active order with real data', (tester) async {
    final provider = OrdersProvider(
      service: _FakeService([
        _order(id: 'a1b2c3d4', status: OrderSummaryStatus.outForDelivery),
      ]),
    );
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('Pedido ativo'), findsOneWidget);
    expect(find.text(r'R$ 242,00'), findsOneWidget);
    expect(find.text('Saiu para entrega'), findsOneWidget);
    expect(find.text('Rastrear pedido'), findsOneWidget);

    // Active order => the provider started a polling timer; dispose it within
    // the test body so no timer is left pending when the tree is torn down.
    provider.dispose();
  });

  testWidgets('renders a delivered order card', (tester) async {
    final provider = OrdersProvider(
      service: _FakeService([
        _order(
          id: 'd1',
          status: OrderSummaryStatus.delivered,
          total: '128.00',
          items: const [
            OrderItemSummary(
                productName: 'Apostila', imageUrl: '', quantity: 4),
          ],
        ),
      ]),
    );
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('ENTREGUE'), findsOneWidget);
    expect(find.text('4 itens no pedido'), findsOneWidget);
    expect(find.text('Comprar novamente'), findsOneWidget);
  });

  testWidgets(
      'a cancelled order shows a Cancelado badge, not a green Entregue one',
      (tester) async {
    final provider = OrdersProvider(
      service: _FakeService([
        _order(id: 'c1', status: OrderSummaryStatus.cancelled),
      ]),
    );
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    // Regression for review round 1, Important 1: the finished-order card
    // used to hardcode the literal 'ENTREGUE' regardless of status, so a
    // cancelled order rendered with a green "delivered" badge.
    expect(find.text('CANCELADO'), findsOneWidget);
    expect(find.text('ENTREGUE'), findsNothing);

    // Recomprar um pedido cancelado é legítimo; avaliar itens que nunca
    // chegaram não é.
    expect(find.text('Comprar novamente'), findsOneWidget);
    expect(find.text('Avaliar itens'), findsNothing);
  });

  testWidgets('shows an empty state when there are no orders',
      (tester) async {
    final provider = OrdersProvider(service: _FakeService(const []));
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('Você ainda não tem pedidos'), findsOneWidget);
  });

  testWidgets('shows an error view with a retry action', (tester) async {
    final provider = OrdersProvider(service: _FailingService());
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('falhou'), findsOneWidget);
    expect(find.text('Tentar novamente'), findsOneWidget);
  });
}
