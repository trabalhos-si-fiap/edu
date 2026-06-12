import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';

/// Client for registering/unregistering this device's FCM token with the
/// backend. All calls require a stored access token (the user must be logged
/// in); without one they no-op and return false.
class NotificationsApi {
  NotificationsApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

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
