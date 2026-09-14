import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/notification_model.dart';

/// Raised when fetching the notification history fails; carries a
/// user-friendly message ready to render.
class NotificationsException implements Exception {
  NotificationsException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Raised by [NotificationsApi.listWithToken] when the backend answers `401`:
/// the token expired (or was revoked), so the caller can refresh and retry.
class NotificationsUnauthorizedException extends NotificationsException {
  NotificationsUnauthorizedException()
    : super('Falha ao carregar notificações (401)');
}

/// Client for the notifications backend: fetching the user's notification
/// history, and registering/unregistering a device token.
///
/// `registerDevice`/`unregisterDevice` ficaram **sem chamador** na spec A,
/// que tirou o Firebase do app — não há mais de onde tirar um token FCM. Os
/// dois endpoints continuam de pé e testados no `notification-service`, e os
/// métodos ficam aqui porque a spec C, ao ligar push de verdade, precisa
/// exatamente deles. Apagá-los agora seria reescrevê-los depois.
class NotificationsApi {
  NotificationsApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Fetches the user's notification history (newest first). Throws
  /// [NotificationsException] on auth/connection/server errors so the UI can
  /// show a dedicated error state.
  Future<List<NotificationModel>> list() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw NotificationsException('Sessão expirada. Entre novamente.');
    }
    return listWithToken(access);
  }

  /// Same as [list], but authenticated with [accessToken] instead of the
  /// active session's — the multi-session demo polls saved sessions that are
  /// not on screen. Throws [NotificationsUnauthorizedException] on `401` so
  /// the caller can refresh that session's pair itself.
  ///
  /// Build this API with a plain [http.Client] for that: `appAuthClient`
  /// rewrites `Authorization` with the ACTIVE token and, on `401`, refreshes
  /// (or logs out) the active session.
  Future<List<NotificationModel>> listWithToken(String accessToken) async {
    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}/notifications'),
        headers: {'Authorization': 'Bearer $accessToken'},
      );
    } on Exception {
      throw NotificationsException('Não foi possível conectar ao servidor');
    }

    if (res.statusCode == 401) throw NotificationsUnauthorizedException();
    if (res.statusCode != 200) {
      throw NotificationsException(
        'Falha ao carregar notificações (${res.statusCode})',
      );
    }

    final decoded = jsonDecode(res.body) as List<dynamic>;
    return decoded
        .map((e) => NotificationModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<bool> registerDevice(String fcmToken, {String platform = 'android'}) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) return false;

    try {
      final res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/notifications/devices'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $access',
        },
        body: jsonEncode({'token': fcmToken, 'platform': platform}),
      );
      return res.statusCode == 201;
    } on Exception {
      // Registration is best-effort; a failure must never block the user.
      return false;
    }
  }

  Future<bool> unregisterDevice(String fcmToken) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) return false;

    try {
      final res = await _client.delete(
        Uri.parse('${ApiConfig.baseUrl}/notifications/devices/$fcmToken'),
        headers: {'Authorization': 'Bearer $access'},
      );
      return res.statusCode == 204;
    } on Exception {
      return false;
    }
  }
}
