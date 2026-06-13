import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/products_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore implements TokenStore {
  @override
  Future<String?> readAccessToken() async => 'tkn';
  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('list parses products envelope', () async {
    final client = MockClient((req) async {
      expect(req.headers['Authorization'], 'Bearer tkn');
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 'p1',
              'name': 'Guia',
              'type': 'apostila',
              'subtype': '',
              'description': '',
              'price': '49.90',
              'image_url': '',
              'rating_avg': 0.0,
              'rating_count': 0,
            }
          ],
          'total': 1,
          'limit': 20,
          'offset': 0,
        }),
        200,
      );
    });
    final api = ProductsApi(client: client, tokenStore: _FakeTokenStore());
    final products = await api.list();
    expect(products.length, 1);
    expect(products.first.id, 'p1');
  });

  test('list throws ProductsException on error status', () async {
    final client = MockClient((req) async => http.Response('boom', 500));
    final api = ProductsApi(client: client, tokenStore: _FakeTokenStore());
    expect(api.list(), throwsA(isA<ProductsException>()));
  });
}
