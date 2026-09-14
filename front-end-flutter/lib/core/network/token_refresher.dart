import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'token_store.dart';

/// Exchanges the stored refresh token for a fresh JWT pair via
/// `POST /auth/refresh` and persists it.
///
/// Uses a plain [http.Client] (never the authenticated wrapper) to avoid
/// recursing back into the 401 refresh flow.
class TokenRefresher {
  TokenRefresher({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Returns `true` when a new token pair was obtained and saved.
  Future<bool> refresh() async {
    final refreshToken = await _tokenStore.readRefreshToken();
    if (refreshToken == null) return false;

    final pair = await exchange(refreshToken);
    if (pair == null) return false;

    await _tokenStore.save(
      accessToken: pair.accessToken,
      refreshToken: pair.refreshToken,
    );
    return true;
  }

  /// Exchanges [refreshToken] for a fresh pair WITHOUT persisting it, or
  /// returns `null` on a network error or non-200 response.
  ///
  /// For a refresh token that is not the active session's (the multi-session
  /// demo keeps other saved sessions alive): the caller decides where the new
  /// pair goes, so the active [TokenStore] is never overwritten.
  Future<TokenPair?> exchange(String refreshToken) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/auth/refresh'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': refreshToken}),
      );
    } on Exception {
      return null;
    }

    if (res.statusCode != 200) return null;

    final tokens = jsonDecode(res.body) as Map<String, dynamic>;
    return (
      accessToken: tokens['access_token'] as String,
      refreshToken: tokens['refresh_token'] as String,
    );
  }
}
