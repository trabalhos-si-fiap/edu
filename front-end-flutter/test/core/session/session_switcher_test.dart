import 'dart:async';
import 'dart:convert';

import 'package:edu_ia/core/session/session_switcher.dart';
import 'package:edu_ia/features/notifications/domain/local_notifier.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_poller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TimerParado implements Timer {
  @override
  void cancel() {}

  @override
  bool get isActive => false;

  @override
  int get tick => 0;
}

String _token() {
  String parte(Map<String, Object> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  return '${parte({'alg': 'HS256'})}.${parte({'sub': 'aluno-1', 'role': 'student'})}.x';
}

/// Um botão que faz o que o login e a troca de sessão fazem ao entrar.
Widget _app({NotificationsPoller? poller}) {
  final app = MaterialApp(
    routes: {
      '/': (context) => Scaffold(
        body: TextButton(
          onPressed: () => irParaTelaDoPapel(context, 'student'),
          child: const Text('entrar'),
        ),
      ),
      '/home': (_) => const Scaffold(body: Text('home do aluno')),
    },
  );
  if (poller == null) return app;
  return ChangeNotifierProvider<NotificationsPoller>.value(
    value: poller,
    child: app,
  );
}

void main() {
  testWidgets('entrar numa sessão começa o acompanhamento de notificações', (
    tester,
  ) async {
    var buscas = 0;
    final poller = NotificationsPoller(
      notifier: const LocalNotifierInerte(),
      buscar: () async {
        buscas++;
        return const [];
      },
      lerAccessToken: () async => _token(),
      criarTimer: (_, _) => _TimerParado(),
    );
    await tester.pumpWidget(_app(poller: poller));
    expect(poller.ativo, isFalse);

    await tester.tap(find.text('entrar'));
    await tester.pumpAndSettle();

    expect(poller.ativo, isTrue);
    expect(buscas, 1);
    expect(find.text('home do aluno'), findsOneWidget);
  });

  testWidgets('sem o poller na árvore, a navegação pós-login segue igual', (
    tester,
  ) async {
    await tester.pumpWidget(_app());

    await tester.tap(find.text('entrar'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('home do aluno'), findsOneWidget);
  });

  test('os chips de sessão mostram o papel em português', () {
    expect(rotuloDoPapel('student'), 'aluno');
    expect(rotuloDoPapel('separador'), 'separador');
    expect(rotuloDoPapel('entregador'), 'entregador');
    expect(rotuloDoPapel('admin'), 'admin');
    // Papel que o app não conhece não some do chip: sai como veio.
    expect(rotuloDoPapel('carregamento'), 'carregamento');
  });
}
