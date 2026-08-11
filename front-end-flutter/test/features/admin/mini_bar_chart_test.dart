import 'package:edu_ia/features/admin/presentation/widgets/admin_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// O `FractionallySizedBox` das barras vivia direto dentro de um `Column`,
/// que passa altura ILIMITADA aos filhos. Multiplicar infinito pelo
/// `heightFactor` continua infinito, então o layout estourava:
///
///   BoxConstraints forces an infinite height.
///   The offending constraints were: BoxConstraints(0.0<=w<=34.0, h=Infinity)
///
/// Quando o layout falha nada é pintado: no aparelho o Painel
/// Administrativo abria com o corpo inteiro em branco, sem erro visível e
/// sem responder ao pull-to-refresh.
///
/// O bug só aparece com `data` não vazio — com o banco zerado o gráfico cai
/// no ramo "Sem dados suficientes ainda", que não tem barra nenhuma. Foi por
/// isso que ele sobreviveu até existir o primeiro pedido.
void main() {
  const dados = {'Criado': 3, 'Separado': 2, 'Entregue': 1};

  testWidgets('as barras cabem dentro de um ListView', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(children: const [MiniBarChart(data: dados)]),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('as barras crescem com o valor', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(children: const [MiniBarChart(data: dados)]),
        ),
      ),
    );

    // A altura tem de acompanhar o valor, senão "não estourou" seria
    // satisfeito por barras de altura zero.
    double alturaDaBarra(String rotulo) {
      final coluna = find.ancestor(
        of: find.text(rotulo),
        matching: find.byType(Column),
      );
      // Mede o Container de dentro, não o FractionallySizedBox: este ocupa
      // toda a altura que o Expanded lhe dá e mede igual para todas as
      // barras — é o filho que recebe a fração.
      final barra = find.descendant(
        of: find.descendant(
          of: coluna.first,
          matching: find.byType(FractionallySizedBox),
        ),
        matching: find.byType(Container),
      );
      return tester.getSize(barra).height;
    }

    expect(alturaDaBarra('Criado'), greaterThan(alturaDaBarra('Separado')));
    expect(alturaDaBarra('Separado'), greaterThan(alturaDaBarra('Entregue')));
  });

  testWidgets('sem dados mostra o aviso e nenhuma barra', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(children: const [MiniBarChart(data: {})]),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
    expect(find.text('Sem dados suficientes ainda'), findsOneWidget);
    expect(find.byType(FractionallySizedBox), findsNothing);
  });
}
