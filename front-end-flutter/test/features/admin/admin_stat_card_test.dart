import 'package:edu_ia/features/admin/presentation/widgets/admin_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// O card de KPI estourava a célula do grid do Painel Administrativo:
///
///   BOTTOM OVERFLOWED BY 27 PIXELS   (rótulo de uma linha)
///   BOTTOM OVERFLOWED BY 44 PIXELS   (rótulo de duas linhas)
///
/// O valor grande ficava cortado ao meio. Ficou escondido enquanto o
/// gráfico de barras derrubava o layout inteiro do painel — ver
/// mini_bar_chart_test.dart. Com aquele corrigido, a tela passou a pintar e
/// o estouro apareceu.
///
/// A geometria abaixo reproduz a célula real: `GridView.count` com 2
/// colunas dentro de um ListView de padding horizontal 16 e espaçamento 12.
/// A largura sai de (360 - 32 - 12) / 2, e a altura da divisão pelo
/// `childAspectRatio` de `_GradeMetricas` (1.15).
void main() {
  const larguraCelula = (360.0 - 32 - 12) / 2;

  Future<void> pumpNaCelula(
    WidgetTester tester, {
    required String label,
    required double aspectRatio,
    String? badge,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: larguraCelula,
              height: larguraCelula / aspectRatio,
              child: AdminStatCard(
                icon: Icons.shopping_bag_outlined,
                label: label,
                value: '3',
                badge: badge,
              ),
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('cabe na célula com rótulo de uma linha', (tester) async {
    await pumpNaCelula(tester, label: 'Pedidos criados', aspectRatio: 1.15);
    expect(tester.takeException(), isNull);
  });

  testWidgets('cabe na célula com rótulo de duas linhas', (tester) async {
    await pumpNaCelula(
      tester,
      label: 'Ocorrências resolvidas',
      aspectRatio: 1.15,
      badge: 'OK',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('o valor continua inteiro na tela', (tester) async {
    await pumpNaCelula(tester, label: 'Pedidos criados', aspectRatio: 1.15);
    // Não basta não estourar: o número é a informação do card, e um
    // `overflow: clip` silencioso passaria no teste acima.
    expect(find.text('3'), findsOneWidget);
    expect(tester.getSize(find.text('3')).height, greaterThan(0));
  });
}
