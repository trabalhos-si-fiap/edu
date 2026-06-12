/// Network configuration for talking to the backend.
class ApiConfig {
  const ApiConfig._();

  /// Base URL of the backend API.
  ///
  /// Defaults to the Android emulator alias for the host machine (10.0.2.2),
  /// where the backend is published on port 8001 (see
  /// `back-end/docker-compose.yml`). Override at build/run time with:
  /// `flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8001/api`
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8001/api',
  );
}
