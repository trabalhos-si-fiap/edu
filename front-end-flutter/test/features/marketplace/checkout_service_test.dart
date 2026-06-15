import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/checkout_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

void main() {
  test('placeOrder posts payment_method and address_id, returns the order id',
      () async {
    final calls = <String>[];
    Map<String, dynamic>? sentBody;
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      sentBody = jsonDecode(req.body) as Map<String, dynamic>;
      if (req.method == 'POST' && req.url.path.endsWith('/orders')) {
        return http.Response(jsonEncode({'id': 'order-9'}), 201);
      }
      return http.Response('nope', 500);
    });
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    final orderId =
        await service.placeOrder(paymentMethod: 'PIX', addressId: 'addr-1');

    expect(orderId, 'order-9');
    expect(calls, ['POST /api/orders']);
    expect(sentBody, {'payment_method': 'PIX', 'address_id': 'addr-1'});
  });

  test('throws CheckoutException when order creation fails', () async {
    final client =
        MockClient((req) async => http.Response('Cart is empty', 400));
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.placeOrder(paymentMethod: 'PIX', addressId: 'addr-1'),
      throwsA(isA<CheckoutException>()),
    );
  });
}
