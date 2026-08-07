import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

/// Network configuration for talking to the backend.
class ApiConfig {
  const ApiConfig._();

  /// Override at build/run time with:
  /// `flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8100/api`
  ///
  /// Useful for physical devices (which don't share the host machine's
  /// network) or when the backend runs on a non-default host/port (e.g.
  /// a custom `GATEWAY_PORT_EXTERNAL` in `back-end/.env`).
  static const String _override = String.fromEnvironment('API_BASE_URL');

  /// Base URL of the backend API, through the **API Gateway** (the new
  /// microservices stack — `back-end/api-gateway`), not the legacy
  /// monolith. Port 8100 is `GATEWAY_PORT_EXTERNAL`'s default in
  /// `back-end/docker-compose.yml` (`"${GATEWAY_PORT_EXTERNAL:-8100}:8000"`)
  /// — 8000 is only the container's *internal* port, never reachable
  /// directly from the host. If your `back-end/.env` overrides
  /// `GATEWAY_PORT_EXTERNAL`, pass the matching `--dart-define=API_BASE_URL=...`.
  ///
  /// Auto-detects per platform so `flutter run` works out of the box on
  /// both emulators/simulators without any `--dart-define`:
  /// - Android emulator: `10.0.2.2` is the special alias for the host
  ///   machine's `localhost` (the emulator runs in its own virtualized
  ///   network namespace).
  /// - iOS Simulator: unlike Android, it shares the Mac's network stack
  ///   directly, so `localhost` from inside the simulator already points
  ///   at the Mac itself — no alias needed.
  /// - Web (Chrome, etc.): also `localhost`, same machine.
  static String get baseUrl {
    if (_override.isNotEmpty) return _override;
    if (kIsWeb) return 'http://localhost:8100/api';
    if (Platform.isAndroid) return 'http://10.0.2.2:8100/api';
    // iOS Simulator (and macOS/Linux/Windows desktop builds) — localhost
    // already resolves to this same machine.
    return 'http://localhost:8100/api';
  }
}
