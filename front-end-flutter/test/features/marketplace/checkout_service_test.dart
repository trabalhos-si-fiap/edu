import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/data/checkout_service.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

Product _p(String id, double price) => Product(
  id: id, name: 'P', type: 'curso', subtype: '', description: '', price: price,
);

void main() {
  test('placeOrder clears the cart, posts each item, creates the order',
      () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      if (req.method == 'GET' && req.url.path.endsWith('/cart')) {
        return http.Response(
          jsonEncode({
            'items': [
              {'product_id': 'old', 'name': 'Old', 'type': 't', 'price': '5.00',
               'quantity': 1, 'subtotal': '5.00'},
            ],
            'total': '5.00',
          }),
          200,
        );
      }
      if (req.method == 'DELETE') return http.Response('{}', 200);
      if (req.method == 'POST' && req.url.path.endsWith('/cart/items')) {
        return http.Response('{}', 201);
      }
      if (req.method == 'POST' && req.url.path.endsWith('/orders')) {
        return http.Response(
          jsonEncode({
            'id': 'order-9', 'total': '20.00', 'status': 'pending',
            'created_at': '2026-06-13T00:00:00Z', 'items': [],
          }),
          201,
        );
      }
      return http.Response('nope', 500);
    });

    final cart = CartStore()..add(_p('a', 10.0), 2);

    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());
    final orderId = await service.placeOrder(
      items: cart.items,
      paymentMethod: 'PIX',
    );

    expect(orderId, 'order-9');
    expect(calls, containsAllInOrder(<String>[
      'GET /api/cart',
      'DELETE /api/cart/items/old',
      'POST /api/cart/items',
      'POST /api/orders',
    ]));
  });

  test('throws CheckoutException when order creation fails', () async {
    final client = MockClient((req) async {
      if (req.url.path.endsWith('/cart') && req.method == 'GET') {
        return http.Response(jsonEncode({'items': [], 'total': '0.00'}), 200);
      }
      if (req.method == 'POST' && req.url.path.endsWith('/cart/items')) {
        return http.Response('{}', 201);
      }
      return http.Response('Cart is empty', 400); // POST /orders fails
    });

    final cart = CartStore()..add(_p('a', 10.0));
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.placeOrder(items: cart.items, paymentMethod: 'PIX'),
      throwsA(isA<CheckoutException>()),
    );
  });
}
