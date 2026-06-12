import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'notifications_api.dart';

/// Owns the device-side FCM lifecycle: permission, token sync with the backend,
/// and rendering notifications that arrive while the app is in the foreground
/// (FCM only shows a system tray entry automatically in background/terminated).
class MessagingService {
  MessagingService({
    FirebaseMessaging? messaging,
    NotificationsApi? api,
    FlutterLocalNotificationsPlugin? localNotifications,
  }) : _messaging = messaging ?? FirebaseMessaging.instance,
       _api = api ?? NotificationsApi(),
       _local = localNotifications ?? FlutterLocalNotificationsPlugin();

  final FirebaseMessaging _messaging;
  final NotificationsApi _api;
  final FlutterLocalNotificationsPlugin _local;

  static const _channel = AndroidNotificationChannel(
    'edu_default',
    'Notificações',
    description: 'Notificações gerais do Edu IA',
    importance: Importance.high,
  );

  /// One-time setup: call once at startup, before any login.
  Future<void> init() async {
    await _messaging.requestPermission();

    await _local.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
    );
    await _local
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(_channel);

    FirebaseMessaging.onMessage.listen(_showForeground);
    // Keep the backend in sync if FCM rotates the token mid-session.
    _messaging.onTokenRefresh.listen(_api.registerDevice);
  }

  /// Registers the current device token with the backend. Call right after a
  /// successful login, once a JWT is available.
  Future<void> syncToken() async {
    final token = await _messaging.getToken();
    if (token != null) {
      await _api.registerDevice(token);
    }
  }

  void _showForeground(RemoteMessage message) {
    final notification = message.notification;
    if (notification == null) return;

    _local.show(
      id: notification.hashCode,
      title: notification.title,
      body: notification.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          _channel.id,
          _channel.name,
          channelDescription: _channel.description,
          icon: '@mipmap/ic_launcher',
        ),
      ),
    );
  }
}

/// Background/terminated handler. Must be a top-level function annotated with
/// `@pragma('vm:entry-point')` so it survives tree-shaking and runs in its own
/// isolate. Firebase must be re-initialised here.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Intentionally minimal: the system tray renders the notification itself.
  if (kDebugMode) {
    debugPrint('Background message: ${message.messageId}');
  }
}
