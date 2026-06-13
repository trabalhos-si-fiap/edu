import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/notifications/data/notifications_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  _FakeTokenStore(this._token);

  final String? _token;

  @override
  Future<String?> readAccessToken() async => _token;
}

void main() {
  test('list parses notifications and sends the bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode([
          {
            'id': 'n1',
            'title': 'Saiu para entrega',
            'body': 'Seu pedido saiu para entrega.',
            'data': {'type': 'order_status', 'order_id': 'o1'},
            'read_at': null,
            'created_at': '2026-06-13T10:00:00Z',
          },
        ]),
        200,
        headers: {'content-type': 'application/json'},
      );
    });

    final api = NotificationsApi(client: client, tokenStore: _FakeTokenStore('fake'));
    final items = await api.list();

    expect(items, hasLength(1));
    expect(items.first.title, 'Saiu para entrega');
    expect(items.first.type, 'order_status');
    expect(items.first.readAt, isNull);
    expect(captured.headers['Authorization'], 'Bearer fake');
    expect(captured.url.path, endsWith('/notifications'));
  });

  test('list throws when not authenticated', () async {
    final client = MockClient((req) async => http.Response('[]', 200));
    final api = NotificationsApi(client: client, tokenStore: _FakeTokenStore(null));

    expect(() => api.list(), throwsA(isA<NotificationsException>()));
  });

  test('list throws NotificationsException on non-200', () async {
    final client = MockClient((req) async => http.Response('boom', 500));
    final api = NotificationsApi(client: client, tokenStore: _FakeTokenStore('fake'));

    expect(() => api.list(), throwsA(isA<NotificationsException>()));
  });
}
