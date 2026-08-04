/// Network configuration for talking to the backend.
class ApiConfig {
  const ApiConfig._();

  /// Base URL of the backend API.
  ///
  /// Defaults to the Android emulator alias for the host machine (10.0.2.2),
  /// where the backend is published on port 8001 (see
  /// `back-end/docker-compose.yml`, `API_PORT_EXTERNAL` defaults to 8001).
  ///
  /// This default only applies to a bare `flutter run`; `make front` always
  /// passes the port read from `back-end/.env`. It is 8001 and not 8000
  /// because other projects on this machine occupy the 80xx range — pointing
  /// at 8000 would silently reach a different backend and return wrong data
  /// instead of failing to connect.
  ///
  /// Override at build/run time with:
  /// `flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8001/api`
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8001/api',
  );
}
