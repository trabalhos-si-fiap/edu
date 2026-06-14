import 'dart:convert';

import 'package:edu_ia/core/network/token_refresher.dart';
import 'package:edu_ia/core/network/token_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  _FakeTokenStore({this.refreshToken});

  String? refreshToken;
  String? savedAccess;
  String? savedRefresh;

  @override
  Future<String?> readRefreshToken() async => refreshToken;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    savedAccess = accessToken;
    savedRefresh = refreshToken;
  }
}

void main() {
  test('returns false and makes no request without a stored refresh token',
      () async {
    var called = false;
    final client = MockClient((req) async {
      called = true;
      return http.Response('{}', 200);
    });
    final refresher = TokenRefresher(
      client: client,
      tokenStore: _FakeTokenStore(refreshToken: null),
    );

    final ok = await refresher.refresh();

    expect(ok, isFalse);
    expect(called, isFalse);
  });

  test('posts the refresh token and saves the new pair on 200', () async {
    final store = _FakeTokenStore(refreshToken: 'old-refresh');
    String? capturedPath;
    Object? capturedBody;
    final client = MockClient((req) async {
      capturedPath = req.url.path;
      capturedBody = jsonDecode(req.body);
      return http.Response(
        jsonEncode({
          'access_token': 'new-access',
          'refresh_token': 'new-refresh',
          'token_type': 'bearer',
        }),
        200,
      );
    });
    final refresher = TokenRefresher(client: client, tokenStore: store);

    final ok = await refresher.refresh();

    expect(ok, isTrue);
    expect(capturedPath, '/api/auth/refresh');
    expect(capturedBody, {'refresh_token': 'old-refresh'});
    expect(store.savedAccess, 'new-access');
    expect(store.savedRefresh, 'new-refresh');
  });

  test('returns false and saves nothing on a non-200 response', () async {
    final store = _FakeTokenStore(refreshToken: 'old-refresh');
    final client = MockClient((req) async => http.Response('bad', 401));
    final refresher = TokenRefresher(client: client, tokenStore: store);

    final ok = await refresher.refresh();

    expect(ok, isFalse);
    expect(store.savedAccess, isNull);
  });

  test('returns false on a network error', () async {
    final store = _FakeTokenStore(refreshToken: 'old-refresh');
    final client = MockClient((req) async {
      throw http.ClientException('down');
    });
    final refresher = TokenRefresher(client: client, tokenStore: store);

    final ok = await refresher.refresh();

    expect(ok, isFalse);
  });
}
