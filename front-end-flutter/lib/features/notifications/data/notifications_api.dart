import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
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

/// Client for the notifications backend: registering/unregistering this
/// device's FCM token (best-effort, requires a stored access token) and
/// fetching the user's notification history.
class NotificationsApi {
  NotificationsApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
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

    final http.Response res;
    try {
      res = await _client.get(
        Uri.parse('${ApiConfig.baseUrl}/notifications'),
        headers: {'Authorization': 'Bearer $access'},
      );
    } on Exception {
      throw NotificationsException('Não foi possível conectar ao servidor');
    }

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
