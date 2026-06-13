import 'package:edu_ia/features/support/data/support_service.dart';
import 'package:edu_ia/features/support/domain/support_message.dart';
import 'package:edu_ia/features/support/presentation/support_provider.dart';
import 'package:flutter_test/flutter_test.dart';

SupportMessage _msg(String id, SupportSender sender, String body) =>
    SupportMessage(id: id, sender: sender, body: body, createdAt: null);

/// Service de teste com comportamento configurável (sem rede).
class _FakeService extends SupportService {
  _FakeService({
    this.onList,
    this.onSend,
  });

  Future<List<SupportMessage>> Function()? onList;
  Future<List<SupportMessage>> Function(String body)? onSend;

  @override
  Future<List<SupportMessage>> fetchMessages() =>
      onList?.call() ?? Future.value(const []);

  @override
  Future<List<SupportMessage>> sendMessage(String body) =>
      onSend?.call(body) ?? Future.value(const []);
}

void main() {
  test('load success populates messages', () async {
    final service = _FakeService(
      onList: () async => [_msg('a', SupportSender.support, 'olá')],
    );
    final provider = SupportProvider(service: service);

    await provider.load();

    expect(provider.state, SupportViewState.success);
    expect(provider.messages, hasLength(1));
  });

  test('load failure sets error state', () async {
    final service = _FakeService(
      onList: () async => throw SupportException('boom'),
    );
    final provider = SupportProvider(service: service);

    await provider.load();

    expect(provider.state, SupportViewState.error);
    expect(provider.errorMessage, 'boom');
  });

  test('send replaces messages with the returned list', () async {
    final service = _FakeService(
      onList: () async => [_msg('a', SupportSender.user, 'oi')],
      onSend: (body) async => [
        _msg('a', SupportSender.user, 'oi'),
        _msg('b', SupportSender.support, 'resposta'),
      ],
    );
    final provider = SupportProvider(service: service);
    await provider.load();

    await provider.send('oi de novo');

    expect(provider.messages, hasLength(2));
    expect(provider.sending, isFalse);
  });

  test('send ignores empty/blank input', () async {
    var called = false;
    final service = _FakeService(
      onList: () async => const [],
      onSend: (body) async {
        called = true;
        return const [];
      },
    );
    final provider = SupportProvider(service: service);
    await provider.load();

    await provider.send('   ');

    expect(called, isFalse);
  });

  test('send failure keeps existing messages and clears sending', () async {
    final service = _FakeService(
      onList: () async => [_msg('a', SupportSender.user, 'oi')],
      onSend: (body) async => throw SupportException('falhou'),
    );
    final provider = SupportProvider(service: service);
    await provider.load();

    await provider.send('tentativa');

    expect(provider.messages, hasLength(1));
    expect(provider.sending, isFalse);
    expect(provider.errorMessage, 'falhou');
  });
}
