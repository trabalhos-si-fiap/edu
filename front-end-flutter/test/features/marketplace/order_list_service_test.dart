import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/order_list_service.dart';
import 'package:edu_ia/features/marketplace/domain/order_summary.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

class _NullTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => null;
}

final _list = [
  {
    'id': 'a1',
    'total': '242.00',
    'status': 'separating',
    'payment_method': 'PIX',
    'created_at': '2026-04-22T09:30:00Z',
    'items': [
      {
        'product_id': 'p1',
        'product_name': 'Apostila',
        'unit_price': '242.00',
        'quantity': 1,
        'image_url': '',
      },
    ],
  },
  {
    'id': 'b2',
    'total': '128.00',
    'status': 'delivered',
    'payment_method': 'Visa',
    'created_at': '2023-09-12T12:00:00Z',
    'items': <Map<String, dynamic>>[],
  },
];

void main() {
  test('fetchOrders parses the list and sends the bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_list), 200);
    });

    final service =
        OrderListService(client: client, tokenStore: _FakeTokenStore());
    final orders = await service.fetchOrders();

    expect(orders, hasLength(2));
    expect(orders.first.id, 'a1');
    expect(orders.first.status, OrderSummaryStatus.separating);
    expect(orders[1].isDelivered, isTrue);
    expect(captured.method, 'GET');
    expect(captured.url.path, endsWith('/orders'));
    expect(captured.headers['Authorization'], 'Bearer fake-token');
  });

  test('throws OrderListException on a non-200 status', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service =
        OrderListService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.fetchOrders(),
      throwsA(isA<OrderListException>()),
    );
  });

  test('throws OrderListException when there is no token', () async {
    final client = MockClient((req) async => http.Response('[]', 200));
    final service =
        OrderListService(client: client, tokenStore: _NullTokenStore());

    expect(
      () => service.fetchOrders(),
      throwsA(isA<OrderListException>()),
    );
  });
}
