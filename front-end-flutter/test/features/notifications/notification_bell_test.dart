import 'dart:async';
import 'dart:convert';

import 'package:edu_ia/features/components/top_bar.dart';
import 'package:edu_ia/features/notifications/domain/local_notifier.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_poller.dart';
import 'package:edu_ia/features/notifications/presentation/widgets/notification_bell.dart';
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

NotificationModel _n(String id, {bool lida = false}) => NotificationModel(
  id: id,
  title: 'Título $id',
  body: 'Corpo $id',
  createdAt: DateTime(2026, 9, 13),
  readAt: lida ? DateTime(2026, 9, 13) : null,
);

String _token() {
  String parte(Map<String, Object> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  return '${parte({'alg': 'HS256'})}.${parte({'sub': 'aluno-1', 'role': 'student'})}.x';
}

/// Um poller de verdade, com a busca, o token e o relógio nas mãos do teste.
Future<NotificationsPoller> _pollerCom(
  List<NotificationModel> Function() lista,
) async {
  final poller = NotificationsPoller(
    notifier: const LocalNotifierInerte(),
    buscar: () async => lista(),
    lerAccessToken: () async => _token(),
    criarTimer: (_, _) => _TimerParado(),
  );
  await poller.iniciar();
  return poller;
}

Widget _app(Widget sino, {NotificationsPoller? poller}) {
  final app = MaterialApp(
    routes: {
      '/': (_) => Scaffold(appBar: AppBar(actions: [sino])),
      '/notifications': (_) =>
          const Scaffold(body: Text('lista de notificações')),
    },
  );
  if (poller == null) return app;
  return ChangeNotifierProvider<NotificationsPoller>.value(
    value: poller,
    child: app,
  );
}

bool _contadorVisivel(WidgetTester tester) =>
    tester.widget<Badge>(find.byType(Badge)).isLabelVisible;

void main() {
  testWidgets('mostra quantas notificações não foram lidas', (tester) async {
    final poller = await _pollerCom(
      () => [_n('3'), _n('2', lida: true), _n('1'), _n('0')],
    );

    await tester.pumpWidget(_app(const NotificationBell(), poller: poller));

    expect(_contadorVisivel(tester), isTrue);
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('sem nada por ler, o sino não mostra contador', (tester) async {
    final poller = await _pollerCom(() => [_n('1', lida: true)]);

    await tester.pumpWidget(_app(const NotificationBell(), poller: poller));

    expect(_contadorVisivel(tester), isFalse);
  });

  testWidgets('o contador acompanha o polling, sem recarregar a tela', (
    tester,
  ) async {
    var lista = [_n('1')];
    final poller = await _pollerCom(() => lista);
    await tester.pumpWidget(_app(const NotificationBell(), poller: poller));
    expect(find.text('1'), findsOneWidget);

    lista = [_n('2'), _n('1')];
    await poller.verificar();
    await tester.pump();

    expect(find.text('2'), findsOneWidget);
  });

  testWidgets('sem o poller na árvore o sino ainda funciona, sem contador', (
    tester,
  ) async {
    await tester.pumpWidget(_app(const NotificationBell()));

    expect(tester.takeException(), isNull);
    expect(_contadorVisivel(tester), isFalse);
  });

  testWidgets('tocar no sino abre as notificações', (tester) async {
    await tester.pumpWidget(_app(const NotificationBell()));

    await tester.tap(find.byType(NotificationBell));
    await tester.pumpAndSettle();

    expect(find.text('lista de notificações'), findsOneWidget);
  });

  testWidgets('a TopBar usa o sino com contador', (tester) async {
    final poller = await _pollerCom(() => [_n('2'), _n('1')]);

    await tester.pumpWidget(
      ChangeNotifierProvider<NotificationsPoller>.value(
        value: poller,
        child: const MaterialApp(home: Scaffold(appBar: TopBar())),
      ),
    );

    expect(
      find.descendant(
        of: find.byType(TopBar),
        matching: find.byType(NotificationBell),
      ),
      findsOneWidget,
    );
    expect(find.text('2'), findsOneWidget);
  });
}
