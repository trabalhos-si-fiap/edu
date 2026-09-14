import 'package:edu_ia/features/marketplace/presentation/incident_resolution_screen.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/domain/notification_payload.dart';
import 'package:edu_ia/features/notifications/presentation/system_notification_tap.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

NotificationModel _n(Map<String, dynamic>? data) => NotificationModel(
  id: '1',
  title: 'Pedido #ABCDEF12',
  body: 'Corpo',
  createdAt: DateTime(2026, 9, 13),
  data: data,
);

Future<GlobalKey<NavigatorState>> _montarApp(WidgetTester tester) async {
  final chave = GlobalKey<NavigatorState>();
  await tester.pumpWidget(
    MaterialApp(
      navigatorKey: chave,
      routes: {
        '/': (_) => const Scaffold(body: Text('tela atual')),
        '/notifications': (_) =>
            const Scaffold(body: Text('lista de notificações')),
      },
    ),
  );
  return chave;
}

void main() {
  group('payload', () {
    test('leva só o id da ocorrência, quando há', () {
      final comOcorrencia = payloadDaNotificacao(
        _n(const {
          'type': 'order_status',
          'order_id': 'o1',
          'occurrence_id': 7,
        }),
      );

      expect(ocorrenciaDoPayload(comOcorrencia), 7);
      expect(
        ocorrenciaDoPayload(payloadDaNotificacao(_n(const {'order_id': 'o1'}))),
        isNull,
      );
      expect(ocorrenciaDoPayload(payloadDaNotificacao(_n(null))), isNull);
      expect(ocorrenciaDoPayload(null), isNull);
      expect(ocorrenciaDoPayload('não é número'), isNull);
    });

    test(
      'de outra sessão guardada leva só a marca, e nenhuma ocorrência',
      () {
        final payload = payloadDaNotificacao(
          _n(const {'occurrence_id': 7}),
          deOutraSessao: true,
        );

        expect(payload, payloadDeOutraSessao);
        expect(ocorrenciaDoPayload(payload), isNull);
      },
    );
  });

  testWidgets('com sessão ativa, o toque abre a lista de notificações', (
    tester,
  ) async {
    final chave = await _montarApp(tester);

    abrirNotificacaoDoSistema(
      navigator: chave.currentState,
      sessaoAtiva: true,
      payload: payloadDaNotificacao(_n(const {'order_id': 'o1'})),
    );
    await tester.pumpAndSettle();

    expect(find.text('lista de notificações'), findsOneWidget);
  });

  testWidgets(
    'uma notificação de ocorrência abre a resolução, com a lista por baixo',
    (tester) async {
      final chave = await _montarApp(tester);

      abrirNotificacaoDoSistema(
        navigator: chave.currentState,
        sessaoAtiva: true,
        payload: payloadDaNotificacao(_n(const {'occurrence_id': 7})),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));

      expect(find.byType(OcorrenciaResolucaoScreen), findsOneWidget);

      chave.currentState!.pop();
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('lista de notificações'), findsOneWidget);
    },
  );

  testWidgets('sem sessão ativa, o toque só traz o app para a frente', (
    tester,
  ) async {
    final chave = await _montarApp(tester);

    abrirNotificacaoDoSistema(
      navigator: chave.currentState,
      sessaoAtiva: false,
      payload: payloadDaNotificacao(_n(const {'occurrence_id': 7})),
    );
    await tester.pumpAndSettle();

    expect(find.text('tela atual'), findsOneWidget);
    expect(find.text('lista de notificações'), findsNothing);
  });

  testWidgets(
    'uma notificação de outra sessão guardada só traz o app para a frente',
    (tester) async {
      // Demonstração multi-sessão: a notificação é do aluno, mas quem está na
      // tela é o separador. Abrir a lista (ou a resolução) mostraria as
      // notificações de quem está na tela, não as do aluno.
      final chave = await _montarApp(tester);

      abrirNotificacaoDoSistema(
        navigator: chave.currentState,
        sessaoAtiva: true,
        payload: payloadDaNotificacao(
          _n(const {'occurrence_id': 7}),
          deOutraSessao: true,
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('tela atual'), findsOneWidget);
      expect(find.text('lista de notificações'), findsNothing);
      expect(find.byType(OcorrenciaResolucaoScreen), findsNothing);
    },
  );
}
