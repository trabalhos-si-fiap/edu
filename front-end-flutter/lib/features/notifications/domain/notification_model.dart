/// A notification as returned by `GET /api/notifications`.
class NotificationModel {
  const NotificationModel({
    required this.id,
    required this.title,
    required this.body,
    required this.createdAt,
    this.data,
    this.readAt,
  });

  final String id;
  final String title;
  final String body;
  final Map<String, dynamic>? data;
  final DateTime? readAt;
  final DateTime createdAt;

  /// Logical category used to pick an icon (e.g. `order_status`). Comes from
  /// the backend `data.type` payload; empty when absent.
  String get type => (data?['type'] as String?) ?? '';

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    final rawData = json['data'];
    return NotificationModel(
      id: json['id'] as String,
      title: json['title'] as String? ?? '',
      body: json['body'] as String? ?? '',
      data: rawData is Map<String, dynamic> ? rawData : null,
      readAt: _parseDate(json['read_at']),
      createdAt: _parseDate(json['created_at']) ?? DateTime.now(),
    );
  }

  static DateTime? _parseDate(Object? value) {
    if (value is String) return DateTime.tryParse(value);
    return null;
  }
}
