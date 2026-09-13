import 'dart:async';
import 'dart:convert';

import 'package:edu_ia/features/marketplace/presentation/incident_resolution_screen.dart';
import 'package:edu_ia/features/notifications/data/notifications_api.dart';
import 'package:edu_ia/features/notifications/domain/local_notifier.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_poller.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

/// A chave que o backend manda de verdade é `occurrence_id`
/// (`notification-service/app/schemas/notificacao.py::NotificationDataOut`,
/// contrato público em inglês, o mesmo motivo de `order_id`). A tela lia
/// `ocorrencia_id` — o nome interno do model — e por isso NENHUMA
/// notificação era tocável: `OcorrenciaResolucaoScreen`, a única tela onde o
/// aluno aceita um substituto ou cancela, não tinha porta de entrada.
class _ApiComOcorrencia extends NotificationsApi {
  _ApiComOcorrencia(this.data);

  final Map<String, dynamic> data;

  @override
  Future<List<NotificationModel>> list() async => [
    NotificationModel(
      id: 'n1',
      title: 'Pedido #ABCDEF12: item em falta',
      body: 'Um item do seu pedido está em falta.',
      createdAt: DateTime(2026, 9, 9),
      data: data,
    ),
  ];
}

/// A lista que a própria tela busca ao abrir — fixa, para que qualquer item
/// a mais na tela só possa ter vindo do polling.
class _ApiFixa extends NotificationsApi {
  _ApiFixa(this.itens);

  final List<NotificationModel> itens;

  @override
  Future<List<NotificationModel>> list() async => itens;
}

class _TimerParado implements Timer {
  @override
  void cancel() {}

  @override
  bool get isActive => false;

  @override
  int get tick => 0;
}

NotificationModel _n(String id, String titulo) => NotificationModel(
  id: id,
  title: titulo,
  body: 'Corpo $id',
  createdAt: DateTime(2026, 9, 13),
  data: const {'type': 'order_status'},
);

String _token() {
  String parte(Map<String, Object> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  return '${parte({'alg': 'HS256'})}.${parte({'sub': 'aluno-1', 'role': 'student'})}.x';
}

void main() {
  testWidgets('uma notificação com occurrence_id é tocável e abre a resolução', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: NotificationsScreen(
          api: _ApiComOcorrencia(const {
            'type': 'order_status',
            'occurrence_id': 7,
          }),
        ),
      ),
    );
    await tester.pump();

    // A afordância de toque: o card só a mostra quando reconhece a ocorrência.
    expect(find.text('Toque para decidir'), findsOneWidget);

    await tester.tap(find.text('Toque para decidir'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(find.byType(OcorrenciaResolucaoScreen), findsOneWidget);
  });

  testWidgets('uma notificação sem ocorrência não vira ação', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: NotificationsScreen(
          api: _ApiComOcorrencia(const {
            'type': 'order_status',
            'order_id': 'o1',
          }),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Toque para decidir'), findsNothing);

    await tester.tap(find.text('Pedido #ABCDEF12: item em falta'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(find.byType(OcorrenciaResolucaoScreen), findsNothing);
  });

  testWidgets(
    'a lista aberta recebe o que o polling encontrou, sem puxar para atualizar',
    (tester) async {
      final confirmado = _n('1', 'Pedido confirmado');
      var doServidor = [confirmado];
      final poller = NotificationsPoller(
        notifier: const LocalNotifierInerte(),
        buscar: () async => doServidor,
        lerAccessToken: () async => _token(),
        criarTimer: (_, _) => _TimerParado(),
      );
      await poller.iniciar();

      await tester.pumpWidget(
        ChangeNotifierProvider<NotificationsPoller>.value(
          value: poller,
          child: MaterialApp(
            home: NotificationsScreen(api: _ApiFixa([confirmado])),
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Pedido confirmado'), findsOneWidget);

      doServidor = [_n('2', 'Saiu para entrega'), confirmado];
      await poller.verificar();
      await tester.pump();

      // A lista antiga fica na tela enquanto a nova entra: sem spinner no meio.
      expect(find.byType(CircularProgressIndicator), findsNothing);
      await tester.pump();
      expect(find.text('Saiu para entrega'), findsOneWidget);
      expect(find.text('Pedido confirmado'), findsOneWidget);
    },
  );
}
