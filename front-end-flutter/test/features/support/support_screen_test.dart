import 'package:edu_ia/features/support/data/support_service.dart';
import 'package:edu_ia/features/support/domain/support_message.dart';
import 'package:edu_ia/features/support/presentation/support_provider.dart';
import 'package:edu_ia/features/support/presentation/support_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _FakeService extends SupportService {
  _FakeService(this.messages);
  final List<SupportMessage> messages;

  @override
  Future<List<SupportMessage>> fetchMessages() async => messages;

  @override
  Future<List<SupportMessage>> sendMessage(String body) async => messages;
}

Widget _harness(SupportProvider provider) => MaterialApp(
      home: ChangeNotifierProvider.value(
        value: provider,
        child: const SupportView(),
      ),
    );

void main() {
  testWidgets('shows empty greeting when there are no messages',
      (tester) async {
    final provider = SupportProvider(service: _FakeService(const []));
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(
      find.text('Olá! Como posso ajudar com seus pedidos hoje?'),
      findsOneWidget,
    );
  });

  testWidgets('renders message bubbles', (tester) async {
    final provider = SupportProvider(
      service: _FakeService([
        SupportMessage(
          id: 'a',
          sender: SupportSender.support,
          body: 'Posso ajudar com seu pedido?',
          createdAt: null,
        ),
      ]),
    );
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('Posso ajudar com seu pedido?'), findsOneWidget);
    expect(find.text('SUPORTE EDU'), findsOneWidget);
  });
}
