import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/session_store.dart';
import '../../../core/network/token_store.dart';

/// Raised when authentication fails; carries a user-facing message.
class AuthException implements Exception {
  AuthException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Thin client for the backend auth endpoints.
class AuthApi {
  AuthApi({
    http.Client? client,
    TokenStore? tokenStore,
    SessionStore? sessionStore,
  }) : _client = client ?? http.Client(),
       _tokenStore = tokenStore ?? TokenStore(),
       _sessionStore = sessionStore ?? SessionStore();

  final http.Client _client;
  final TokenStore _tokenStore;
  final SessionStore _sessionStore;

  /// Creates an account via `POST /auth/register` and persists the JWT pair.
  ///
  /// [educationLevel] must be one of the backend `EducationLevel` values and
  /// [birthDate] is sent as `DD/MM/AAAA` (parsed server-side).
  Future<void> register({
    required String name,
    required String email,
    required String phone,
    required String birthDate,
    required String educationLevel,
    required String password,
  }) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/auth/register'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({
          'name': name,
          'email': email,
          'phone': phone,
          'birth_date': birthDate,
          'education_level': educationLevel,
          'password': password,
        }),
      );
    } on Exception {
      throw AuthException('Não foi possível conectar ao servidor');
    }

    if (res.statusCode == 409) {
      throw AuthException('Este e-mail já está cadastrado');
    }
    if (res.statusCode == 422) {
      throw AuthException('Verifique os dados informados');
    }
    if (res.statusCode == 429) {
      throw AuthException('Muitas tentativas. Tente novamente mais tarde');
    }
    if (res.statusCode != 201) {
      throw AuthException('Falha ao cadastrar (código ${res.statusCode})');
    }

    await _persistAuth(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Authenticates against `POST /auth/login` and persists the JWT pair.
  Future<void> login({required String email, required String password}) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/auth/login'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email, 'password': password}),
      );
    } on Exception {
      throw AuthException('Não foi possível conectar ao servidor');
    }

    if (res.statusCode == 401) {
      throw AuthException('E-mail ou senha inválidos');
    }
    if (res.statusCode == 429) {
      throw AuthException('Muitas tentativas. Tente novamente mais tarde');
    }
    if (res.statusCode != 200) {
      throw AuthException('Falha ao entrar (código ${res.statusCode})');
    }

    await _persistAuth(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Saves the JWT pair and caches the user's display name from an
  /// `AuthResponse` body (`{user, tokens}`).
  Future<void> _persistAuth(Map<String, dynamic> body) async {
    final tokens = body['tokens'] as Map<String, dynamic>;
    await _tokenStore.save(
      accessToken: tokens['access_token'] as String,
      refreshToken: tokens['refresh_token'] as String,
    );
    final user = body['user'] as Map<String, dynamic>?;
    final name = user?['name'] as String?;
    if (name != null && name.isNotEmpty) {
      await _sessionStore.saveName(name);
    }
  }

  /// Display name of the signed-in user: the cached value when present, else
  /// fetched from `GET /auth/me` and cached. Returns `null` when unavailable
  /// (no session or the request fails) so callers can fall back to a neutral
  /// greeting.
  Future<String?> currentDisplayName() async {
    final cached = await _sessionStore.readName();
    if (cached != null && cached.isNotEmpty) return cached;

    final access = await _tokenStore.readAccessToken();
    if (access == null) return null;

    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}/auth/me'),
        headers: {'Authorization': 'Bearer $access'},
      );
    } on Exception {
      return null;
    }
    if (res.statusCode != 200) return null;

    final user = jsonDecode(res.body) as Map<String, dynamic>;
    final name = user['name'] as String?;
    if (name != null && name.isNotEmpty) {
      await _sessionStore.saveName(name);
    }
    return name;
  }
}
