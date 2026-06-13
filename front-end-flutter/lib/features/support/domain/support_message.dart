/// Quem enviou a mensagem de suporte.
enum SupportSender { user, support }

/// Mensagem do chat de suporte ("Mentor Edu").
///
/// Espelha `SupportMessageOut` do backend: `id` é UUID (string), `sender` é
/// `"user"` ou `"support"`, `created_at` é ISO-8601.
class SupportMessage {
  final String id;
  final SupportSender sender;
  final String body;
  final DateTime? createdAt;

  const SupportMessage({
    required this.id,
    required this.sender,
    required this.body,
    required this.createdAt,
  });

  factory SupportMessage.fromJson(Map<String, dynamic> json) {
    final created = json['created_at'] as String?;
    return SupportMessage(
      id: (json['id'] as String?) ?? '',
      sender: (json['sender'] as String?) == 'support'
          ? SupportSender.support
          : SupportSender.user,
      body: (json['body'] as String?) ?? '',
      createdAt: (created == null || created.isEmpty)
          ? null
          : DateTime.tryParse(created),
    );
  }
}

/// Formata o horário da mensagem como `HH:mm` no fuso local.
/// Retorna string vazia quando não há data.
String formatMessageTime(DateTime? time) {
  if (time == null) return '';
  final local = time.toLocal();
  final hh = local.hour.toString().padLeft(2, '0');
  final mm = local.minute.toString().padLeft(2, '0');
  return '$hh:$mm';
}
