import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/support/data/support_service.dart';
import 'package:edu_ia/features/support/domain/support_message.dart';
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
    'id': 'a',
    'sender': 'user',
    'body': 'oi',
    'created_at': '2026-06-13T12:00:00Z',
  },
  {
    'id': 'b',
    'sender': 'support',
    'body': 'olá',
    'created_at': '2026-06-13T12:01:00Z',
  },
];

void main() {
  test('fetchMessages parses the list and sends bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_list), 200);
    });

    final service =
        SupportService(client: client, tokenStore: _FakeTokenStore());
    final messages = await service.fetchMessages();

    expect(messages, hasLength(2));
    expect(messages[1].sender, SupportSender.support);
    expect(captured.method, 'GET');
    expect(captured.url.path, endsWith('/support'));
    expect(captured.headers['Authorization'], 'Bearer fake-token');
  });

  test('sendMessage posts the body and accepts 201', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_list), 201);
    });

    final service =
        SupportService(client: client, tokenStore: _FakeTokenStore());
    final messages = await service.sendMessage('preciso de ajuda');

    expect(messages, hasLength(2));
    expect(captured.method, 'POST');
    expect(jsonDecode(captured.body), {'body': 'preciso de ajuda'});
    expect(captured.headers['Content-Type'], contains('application/json'));
  });

  test('throws SupportException on non-success status', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service =
        SupportService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.fetchMessages(),
      throwsA(isA<SupportException>()),
    );
  });

  test('throws SupportException when there is no token', () async {
    final client = MockClient((req) async => http.Response('[]', 200));
    final service =
        SupportService(client: client, tokenStore: _NullTokenStore());

    expect(
      () => service.fetchMessages(),
      throwsA(isA<SupportException>()),
    );
  });
}
