import 'package:edu_ia/features/marketplace/domain/order_summary.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _json({String status = 'separating'}) => {
  'id': 'a1b2c3',
  'total': '242.00',
  'status': status,
  'payment_method': 'PIX',
  'created_at': '2026-04-22T09:30:00Z',
  'items': [
    {
      'product_id': 'p1',
      'product_name': 'Apostila Ed. 5.0 Vol 2',
      'unit_price': '121.00',
      'quantity': 1,
      'image_url': 'https://img/1.png',
    },
    {
      'product_id': 'p2',
      'product_name': 'Caderno Editorial Pro',
      'unit_price': '60.50',
      'quantity': 2,
      'image_url': '',
    },
  ],
};

void main() {
  test('fromJson parses the core fields and items', () {
    final order = OrderSummary.fromJson(_json());

    expect(order.id, 'a1b2c3');
    expect(order.total, '242.00');
    expect(order.status, OrderSummaryStatus.separating);
    expect(order.createdAt, DateTime.utc(2026, 4, 22, 9, 30));
    expect(order.items, hasLength(2));
    expect(order.items.first.productName, 'Apostila Ed. 5.0 Vol 2');
    expect(order.items.first.imageUrl, 'https://img/1.png');
    expect(order.items[1].quantity, 2);
  });

  test('maps every backend status string to its enum', () {
    expect(OrderSummary.fromJson(_json(status: 'pending')).status,
        OrderSummaryStatus.pending);
    expect(OrderSummary.fromJson(_json(status: 'confirmed')).status,
        OrderSummaryStatus.confirmed);
    expect(OrderSummary.fromJson(_json(status: 'separating')).status,
        OrderSummaryStatus.separating);
    expect(OrderSummary.fromJson(_json(status: 'out_for_delivery')).status,
        OrderSummaryStatus.outForDelivery);
    expect(OrderSummary.fromJson(_json(status: 'delivered')).status,
        OrderSummaryStatus.delivered);
  });

  test('unknown or missing status falls back to pending', () {
    expect(OrderSummary.fromJson(_json(status: 'bogus')).status,
        OrderSummaryStatus.pending);
  });

  test('isDelivered is true only for the delivered status', () {
    expect(OrderSummary.fromJson(_json(status: 'delivered')).isDelivered,
        isTrue);
    expect(OrderSummary.fromJson(_json(status: 'out_for_delivery')).isDelivered,
        isFalse);
  });

  test('totalQuantity sums the quantity of every item', () {
    expect(OrderSummary.fromJson(_json()).totalQuantity, 3);
  });

  test('stepIndex collapses the 5 statuses onto the 3-step UI', () {
    expect(OrderSummary.fromJson(_json(status: 'pending')).stepIndex, 0);
    expect(OrderSummary.fromJson(_json(status: 'confirmed')).stepIndex, 0);
    expect(OrderSummary.fromJson(_json(status: 'separating')).stepIndex, 0);
    expect(OrderSummary.fromJson(_json(status: 'out_for_delivery')).stepIndex, 1);
    expect(OrderSummary.fromJson(_json(status: 'delivered')).stepIndex, 2);
  });

  test('statusLabel exposes a human-readable Portuguese label', () {
    expect(OrderSummary.fromJson(_json(status: 'pending')).statusLabel,
        'Pendente');
    expect(OrderSummary.fromJson(_json(status: 'confirmed')).statusLabel,
        'Confirmado');
    expect(OrderSummary.fromJson(_json(status: 'separating')).statusLabel,
        'Em separação');
    expect(OrderSummary.fromJson(_json(status: 'out_for_delivery')).statusLabel,
        'Saiu para entrega');
    expect(OrderSummary.fromJson(_json(status: 'delivered')).statusLabel,
        'Entregue');
  });

  group('formatOrderTotal', () {
    test('formats a plain decimal string as Brazilian currency', () {
      expect(formatOrderTotal('242.00'), r'R$ 242,00');
      expect(formatOrderTotal('128.50'), r'R$ 128,50');
    });

    test('inserts a thousands separator', () {
      expect(formatOrderTotal('1234.50'), r'R$ 1.234,50');
    });

    test('falls back to the raw value when it is not numeric', () {
      expect(formatOrderTotal('abc'), r'R$ abc');
    });
  });

  group('formatOrderDate', () {
    test('formats a date as "dd de <month>, yyyy"', () {
      expect(
        formatOrderDate(DateTime.utc(2026, 4, 22, 9, 30)),
        '22 de abril, 2026',
      );
    });

    test('returns empty string for null', () {
      expect(formatOrderDate(null), '');
    });
  });
}
