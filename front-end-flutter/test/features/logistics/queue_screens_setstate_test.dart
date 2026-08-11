import 'package:edu_ia/features/logistics/presentation/delivery_queue_screen.dart';
import 'package:edu_ia/features/logistics/presentation/picking_queue_screen.dart';
import 'package:edu_ia/features/logistics/presentation/tracking_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/incident_resolution_screen.dart';
import 'package:edu_ia/features/notifications/data/notifications_api.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// `setState(() => _future = api.algumaCoisa())` compila, mas o corpo em
/// seta DEVOLVE o valor da atribuição — um Future. O `setState` do Flutter
/// afirma que o callback devolve null e derruba a tela inteira:
///
///   setState() callback argument returned a Future.
///
/// Medido no aparelho: a Fila de Separação caía na tela vermelha de erro
/// logo após o login do separador. O corpo em bloco (`{ _future = ...; }`)
/// devolve void e é a única diferença entre as telas que quebram e as do
/// admin, que sempre usaram bloco.
///
/// Estes testes não exercitam a rede: a asserção do `setState` dispara de
/// forma síncrona, antes de a requisição sair. O que a chamada HTTP
/// devolver (ou o erro que ela levantar) fica com o `FutureBuilder`.
class _ApiVazia extends NotificationsApi {
  @override
  Future<List<NotificationModel>> list() async => const [];
}

void main() {
  /// Nas quatro telas abaixo o `setState` roda dentro do `initState`, então
  /// a asserção estoura no primeiro frame — a tela nunca chega a aparecer.
  Future<void> monta(WidgetTester tester, Widget tela) async {
    await tester.pumpWidget(MaterialApp(home: tela));
    expect(tester.takeException(), isNull);
  }

  testWidgets('a fila de separação monta sem estourar o setState', (tester) async {
    await monta(tester, const SeparadorFilaScreen());
  });

  testWidgets('a fila de entrega monta sem estourar o setState', (tester) async {
    await monta(tester, const EntregadorFilaScreen());
  });

  testWidgets('minhas entregas monta sem estourar o setState', (tester) async {
    await monta(tester, const EntregadorEmRotaScreen());
  });

  testWidgets('a resolução de ocorrência monta sem estourar o setState', (tester) async {
    await monta(tester, const OcorrenciaResolucaoScreen(ocorrenciaId: 1));
  });

  /// As notificações são o caso diferente: o `initState` já atribuía direto
  /// (certo), e o corpo em seta só aparece no `_refresh`. A tela abre bem e
  /// só quebra quando o usuário puxa a lista para atualizar — por isso este
  /// teste precisa do gesto, e não só do primeiro frame.
  testWidgets('as notificações sobrevivem ao pull-to-refresh', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: NotificationsScreen(api: _ApiVazia())),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    await tester.fling(find.byType(RefreshIndicator), const Offset(0, 300), 1000);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
