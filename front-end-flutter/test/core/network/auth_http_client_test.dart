import 'dart:async';

import 'package:edu_ia/core/network/auth_http_client.dart';
import 'package:edu_ia/core/network/token_refresher.dart';
import 'package:edu_ia/core/network/token_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  _FakeTokenStore({this.access});

  String? access;
  bool cleared = false;

  @override
  Future<String?> readAccessToken() async => access;

  @override
  Future<void> clear() async => cleared = true;
}

class _FakeRefresher extends TokenRefresher {
  _FakeRefresher(this._fn);

  final Future<bool> Function() _fn;

  @override
  Future<bool> refresh() => _fn();
}

void main() {
  test('injects the access token as a Bearer header', () async {
    String? sentAuth;
    final inner = MockClient((req) async {
      sentAuth = req.headers['Authorization'];
      return http.Response('ok', 200);
    });
    final client = AuthHttpClient(
      inner: inner,
      tokenStore: _FakeTokenStore(access: 'abc'),
      refresher: _FakeRefresher(() async => false),
      onSessionExpired: () {},
    );

    await client.get(Uri.parse('http://x/y'));

    expect(sentAuth, 'Bearer abc');
  });

  test('on 401 refreshes and retries with the new token', () async {
    final store = _FakeTokenStore(access: 'expired');
    final auths = <String?>[];
    final inner = MockClient((req) async {
      final auth = req.headers['Authorization'];
      auths.add(auth);
      return http.Response('', auth == 'Bearer fresh' ? 200 : 401);
    });
    final client = AuthHttpClient(
      inner: inner,
      tokenStore: store,
      refresher: _FakeRefresher(() async {
        store.access = 'fresh';
        return true;
      }),
      onSessionExpired: () {},
    );

    final res = await client.get(Uri.parse('http://x/y'));

    expect(res.statusCode, 200);
    expect(auths, ['Bearer expired', 'Bearer fresh']);
  });

  test('concurrent 401s trigger a single shared refresh', () async {
    final store = _FakeTokenStore(access: 'expired');
    var refreshCalls = 0;
    final gate = Completer<void>();
    final client = AuthHttpClient(
      inner: MockClient((req) async {
        final auth = req.headers['Authorization'];
        return http.Response('', auth == 'Bearer fresh' ? 200 : 401);
      }),
      tokenStore: store,
      refresher: _FakeRefresher(() async {
        refreshCalls++;
        await gate.future;
        store.access = 'fresh';
        return true;
      }),
      onSessionExpired: () {},
    );

    final f1 = client.get(Uri.parse('http://x/a'));
    final f2 = client.get(Uri.parse('http://x/b'));
    await Future<void>.delayed(Duration.zero);
    gate.complete();
    final r1 = await f1;
    final r2 = await f2;

    expect(refreshCalls, 1);
    expect(r1.statusCode, 200);
    expect(r2.statusCode, 200);
  });

  test('clears the session and signals expiry when refresh fails', () async {
    final store = _FakeTokenStore(access: 'expired');
    var expired = false;
    final client = AuthHttpClient(
      inner: MockClient((req) async => http.Response('nope', 401)),
      tokenStore: store,
      refresher: _FakeRefresher(() async => false),
      onSessionExpired: () => expired = true,
    );

    final res = await client.get(Uri.parse('http://x/y'));

    expect(res.statusCode, 401);
    expect(store.cleared, isTrue);
    expect(expired, isTrue);
  });

  test('passes non-401 responses through without refreshing', () async {
    var refreshCalls = 0;
    final client = AuthHttpClient(
      inner: MockClient((req) async => http.Response('boom', 500)),
      tokenStore: _FakeTokenStore(access: 'abc'),
      refresher: _FakeRefresher(() async {
        refreshCalls++;
        return true;
      }),
      onSessionExpired: () {},
    );

    final res = await client.get(Uri.parse('http://x/y'));

    expect(res.statusCode, 500);
    expect(refreshCalls, 0);
  });

  test('retries only once even if the retry also returns 401', () async {
    var requests = 0;
    var refreshCalls = 0;
    final client = AuthHttpClient(
      inner: MockClient((req) async {
        requests++;
        return http.Response('', 401);
      }),
      tokenStore: _FakeTokenStore(access: 'abc'),
      refresher: _FakeRefresher(() async {
        refreshCalls++;
        return true;
      }),
      onSessionExpired: () {},
    );

    final res = await client.get(Uri.parse('http://x/y'));

    expect(res.statusCode, 401);
    expect(requests, 2);
    expect(refreshCalls, 1);
  });
}
