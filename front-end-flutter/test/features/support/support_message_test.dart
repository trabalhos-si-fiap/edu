import 'package:edu_ia/features/support/domain/support_message.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fromJson maps a support message', () {
    final msg = SupportMessage.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'sender': 'support',
      'body': 'Olá!',
      'created_at': '2026-06-13T12:30:00Z',
    });

    expect(msg.id, '11111111-1111-1111-1111-111111111111');
    expect(msg.sender, SupportSender.support);
    expect(msg.body, 'Olá!');
    expect(msg.createdAt, DateTime.parse('2026-06-13T12:30:00Z'));
  });

  test('fromJson treats any non-support sender as user', () {
    final msg = SupportMessage.fromJson({
      'id': 'x',
      'sender': 'user',
      'body': 'oi',
      'created_at': '2026-06-13T12:30:00Z',
    });
    expect(msg.sender, SupportSender.user);
  });

  test('fromJson tolerates missing/blank fields', () {
    final msg = SupportMessage.fromJson({});
    expect(msg.id, '');
    expect(msg.sender, SupportSender.user);
    expect(msg.body, '');
    expect(msg.createdAt, isNull);
  });

  test('formatMessageTime renders HH:mm and empty for null', () {
    final t = DateTime(2026, 6, 13, 9, 5);
    expect(formatMessageTime(t), '09:05');
    expect(formatMessageTime(null), '');
  });
}
