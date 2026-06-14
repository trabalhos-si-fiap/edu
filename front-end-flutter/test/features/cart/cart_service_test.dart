import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_service.dart';
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

String _cartJson() => jsonEncode({
      'items': [
        {
          'product_id': 'a', 'name': 'Apostila', 'type': 'apostila',
          'subtype': 'Digital', 'price': '49.90', 'quantity': 2,
          'subtotal': '99.80', 'image_url': 'http://img', 'rating_avg': 4.5,
          'rating_count': 10,
        },
      ],
      'total': '99.80',
    });

void main() {
  test('fetch maps CartOut items to CartItems', () async {
    final client = MockClient((req) async {
      expect(req.method, 'GET');
      expect(req.url.path, '/api/cart');
      return http.Response(_cartJson(), 200);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    final items = await service.fetch();

    expect(items, hasLength(1));
    expect(items.first.product.id, 'a');
    expect(items.first.product.name, 'Apostila');
    expect(items.first.product.price, 49.90);
    expect(items.first.quantity, 2);
  });

  test('addItem posts product_id and quantity and parses the cart', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      expect(jsonDecode(req.body), {'product_id': 'a', 'quantity': 2});
      return http.Response(_cartJson(), 201);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    final items = await service.addItem('a', 2);

    expect(calls, ['POST /api/cart/items']);
    expect(items.first.quantity, 2);
  });

  test('removeItem with quantity sends a decrement query', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}?${req.url.query}');
      return http.Response(_cartJson(), 200);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    await service.removeItem('a', quantity: 1);

    expect(calls, ['DELETE /api/cart/items/a?quantity=1']);
  });

  test('removeItem without quantity omits the query', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}?${req.url.query}');
      return http.Response(_cartJson(), 200);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    await service.removeItem('a');

    expect(calls, ['DELETE /api/cart/items/a?']);
  });

  test('non-2xx throws CartException', () async {
    final client = MockClient((req) async => http.Response('boom', 500));
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    expect(() => service.fetch(), throwsA(isA<CartException>()));
  });

  test('missing token throws CartException', () async {
    final client = MockClient((req) async => http.Response(_cartJson(), 200));
    final service = CartService(client: client, tokenStore: _NullTokenStore());

    expect(() => service.fetch(), throwsA(isA<CartException>()));
  });
}
