/// Network configuration for talking to the backend.
class ApiConfig {
  const ApiConfig._();

  /// Base URL of the backend API.
  ///
  /// Defaults to the Android emulator alias for the host machine (10.0.2.2),
  /// where the backend is published on port 8000 (see
  /// `back-end/docker-compose.yml`, `API_PORT_EXTERNAL` defaults to 8000).
  /// Override at build/run time with:
  /// `flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8000/api`
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api',
  );
}
