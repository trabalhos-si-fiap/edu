import 'package:edu_ia/features/marketplace/presentation/incident_resolution_screen.dart';
import 'package:edu_ia/features/notifications/data/notifications_api.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

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

void main() {
  testWidgets('uma notificação com occurrence_id é tocável e abre a resolução', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: NotificationsScreen(
          api: _ApiComOcorrencia(const {'type': 'order_status', 'occurrence_id': 7}),
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
          api: _ApiComOcorrencia(const {'type': 'order_status', 'order_id': 'o1'}),
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
}
