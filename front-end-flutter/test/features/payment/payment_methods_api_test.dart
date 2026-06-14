import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/payment/data/payment_methods_api.dart';
import 'package:edu_ia/features/payment/domain/payment_method.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

class _NoTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => null;
}

void main() {
  test('list parses /payment-methods into PaymentMethod models', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      return http.Response(
        jsonEncode([
          {
            'id': 'pm-1',
            'type': 'credit_card',
            'is_default': true,
            'card_last4': '4492',
            'card_brand': 'Visa',
            'cardholder_name': 'MARIA SILVA',
            'card_expiry': '1228',
          },
          {'id': 'pm-2', 'type': 'pix', 'is_default': false, 'pix_key': 'a@b.c'},
        ]),
        200,
      );
    });
    final api = PaymentMethodsApi(client: client, tokenStore: _FakeTokenStore());

    final methods = await api.list();

    expect(calls, ['GET /api/payment-methods']);
    expect(methods, hasLength(2));
    expect(methods.first.type, PaymentMethodType.creditCard);
    expect(methods.first.isDefault, isTrue);
    expect(methods.first.cardLast4, '4492');
    expect(methods[1].type, PaymentMethodType.pix);
    expect(methods[1].pixKey, 'a@b.c');
  });

  test('create posts only schema-allowed fields and returns the saved method',
      () async {
    Map<String, dynamic>? sentBody;
    final client = MockClient((req) async {
      sentBody = jsonDecode(req.body) as Map<String, dynamic>;
      return http.Response(
        jsonEncode({
          'id': 'pm-9',
          'type': 'credit_card',
          'is_default': false,
          'card_last4': '1111',
          'card_brand': 'Visa',
          'cardholder_name': 'JOAO',
          'card_expiry': '0130',
        }),
        201,
      );
    });
    final api = PaymentMethodsApi(client: client, tokenStore: _FakeTokenStore());

    final created = await api.create(
      const PaymentMethodInput(
        type: PaymentMethodType.creditCard,
        isDefault: false,
        cardLast4: '1111',
        cardBrand: 'Visa',
        cardholderName: 'JOAO',
        cardExpiry: '0130',
      ),
    );

    expect(created.id, 'pm-9');
    expect(sentBody!['type'], 'credit_card');
    expect(sentBody!['card_last4'], '1111');
    // Sensitive fields must never be sent (backend uses extra="forbid").
    expect(sentBody!.containsKey('cardholder_tax_id'), isFalse);
    expect(sentBody!.containsKey('card_number'), isFalse);
    expect(sentBody!.containsKey('cvv'), isFalse);
  });

  test('setDefault patches is_default=true', () async {
    final calls = <String>[];
    Map<String, dynamic>? sentBody;
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      sentBody = jsonDecode(req.body) as Map<String, dynamic>;
      return http.Response(
        jsonEncode({'id': 'pm-1', 'type': 'pix', 'is_default': true}),
        200,
      );
    });
    final api = PaymentMethodsApi(client: client, tokenStore: _FakeTokenStore());

    final updated = await api.setDefault('pm-1');

    expect(calls, ['PATCH /api/payment-methods/pm-1']);
    expect(sentBody, {'is_default': true});
    expect(updated.isDefault, isTrue);
  });

  test('delete accepts 204', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      return http.Response('', 204);
    });
    final api = PaymentMethodsApi(client: client, tokenStore: _FakeTokenStore());

    await api.delete('pm-1');

    expect(calls, ['DELETE /api/payment-methods/pm-1']);
  });

  test('throws PaymentMethodException on non-2xx', () async {
    final client = MockClient((req) async => http.Response('boom', 500));
    final api = PaymentMethodsApi(client: client, tokenStore: _FakeTokenStore());

    expect(() => api.list(), throwsA(isA<PaymentMethodException>()));
  });

  test('throws PaymentMethodException when there is no session token', () async {
    final client = MockClient((req) async => http.Response('', 200));
    final api = PaymentMethodsApi(client: client, tokenStore: _NoTokenStore());

    expect(() => api.list(), throwsA(isA<PaymentMethodException>()));
  });
}
