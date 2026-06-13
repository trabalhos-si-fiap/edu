import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/product_service.dart';
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

void main() {
  test('fetchProducts parses items and sends the bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {'id': 'a', 'name': 'Guia', 'type': 'apostila', 'price': '49.90'},
            {'id': 'b', 'name': 'Curso', 'type': 'curso', 'price': '189.90'},
          ],
          'total': 2,
          'limit': 100,
          'offset': 0,
        }),
        200,
      );
    });

    final service =
        ProductService(client: client, tokenStore: _FakeTokenStore());
    final products = await service.fetchProducts();

    expect(products, hasLength(2));
    expect(products.first.id, 'a');
    expect(captured.method, 'GET');
    expect(captured.url.path, endsWith('/products'));
    expect(captured.headers['Authorization'], 'Bearer fake-token');
  });

  test('fetchReviews parses the items array', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 'r1',
              'author': 'Ana',
              'rating': 5,
              'comment': 'Ótimo',
              'created_at': '2026-03-12T00:00:00Z',
            },
          ],
          'total': 1,
          'rating_avg': 5.0,
          'rating_count': 1,
        }),
        200,
      );
    });

    final service =
        ProductService(client: client, tokenStore: _FakeTokenStore());
    final reviews = await service.fetchReviews('prod-1');

    expect(reviews, hasLength(1));
    expect(reviews.first.author, 'Ana');
    expect(captured.url.path, endsWith('/products/prod-1/reviews'));
  });

  test('throws ProductException on non-200', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service =
        ProductService(client: client, tokenStore: _FakeTokenStore());
    expect(() => service.fetchProducts(), throwsA(isA<ProductException>()));
  });

  test('throws ProductException when there is no token', () async {
    final client = MockClient((req) async => http.Response('{}', 200));
    final service =
        ProductService(client: client, tokenStore: _NullTokenStore());
    expect(() => service.fetchProducts(), throwsA(isA<ProductException>()));
  });
}
