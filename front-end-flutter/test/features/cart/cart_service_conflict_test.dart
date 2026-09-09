import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

void main() {
  test('a 409 surfaces the server message verbatim', () async {
    const mensagem =
        'Seu carrinho já tem itens de outro parceiro. '
        'Finalize ou esvazie o carrinho antes de misturar.';
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({'detail': mensagem}),
        409,
        headers: {'content-type': 'application/json; charset=utf-8'},
      ),
    );

    await expectLater(
      CartService(client: client, tokenStore: _FakeTokenStore())
          .addItem('produto', 1),
      throwsA(
        isA<CartException>().having((e) => e.message, 'message', mensagem),
      ),
    );
  });

  test('other failures keep the generic message with the status code',
      () async {
    final client = MockClient((_) async => http.Response('{}', 500));
    await expectLater(
      CartService(client: client, tokenStore: _FakeTokenStore())
          .addItem('produto', 1),
      throwsA(
        isA<CartException>().having(
          (e) => e.message,
          'message',
          contains('500'),
        ),
      ),
    );
  });

  test('a 409 with an unreadable body falls back to the generic message',
      () async {
    final client = MockClient((_) async => http.Response('<html>', 409));
    await expectLater(
      CartService(client: client, tokenStore: _FakeTokenStore())
          .addItem('produto', 1),
      throwsA(
        isA<CartException>().having((e) => e.message, 'message', contains('409')),
      ),
    );
  });
}
