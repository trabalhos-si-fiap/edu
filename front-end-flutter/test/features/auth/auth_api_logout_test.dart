import 'package:edu_ia/core/network/session_store.dart';
import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/auth/data/auth_api.dart';
import 'package:flutter_test/flutter_test.dart';

class _SpyTokenStore extends TokenStore {
  bool cleared = false;

  @override
  Future<void> clear() async => cleared = true;
}

class _SpySessionStore extends SessionStore {
  bool cleared = false;

  @override
  Future<void> clear() async => cleared = true;
}

void main() {
  test('logout clears the stored tokens and the cached session', () async {
    final tokens = _SpyTokenStore();
    final session = _SpySessionStore();
    final api = AuthApi(tokenStore: tokens, sessionStore: session);

    await api.logout();

    expect(tokens.cleared, isTrue);
    expect(session.cleared, isTrue);
  });
}
