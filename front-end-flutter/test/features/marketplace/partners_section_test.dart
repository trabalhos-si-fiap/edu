import 'package:edu_ia/features/marketplace/domain/partner.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/partners_provider.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/partners_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _produto = Product(
  id: 'a',
  name: 'Luminária de mesa',
  type: 'iluminacao',
  subtype: 'Luminária',
  description: '',
  price: 129.90,
);

Future<void> _montar(WidgetTester tester, Widget child) =>
    tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child))));

void main() {
  testWidgets('with no active partner the section renders nothing', (tester) async {
    await _montar(
      tester,
      const PartnersSection(
        state: PartnersViewState.success,
        partners: [],
        productsByPartner: {},
      ),
    );
    expect(find.text('Parceiros'), findsNothing);
  });

  testWidgets('with one active partner it shows the header and the catalog',
      (tester) async {
    await _montar(
      tester,
      const PartnersSection(
        state: PartnersViewState.success,
        partners: [Partner(id: 2, name: 'Leroy Merlin', active: true, originLabel: 'Cajamar, SP')],
        productsByPartner: {2: [_produto]},
      ),
    );
    expect(find.text('Parceiros'), findsOneWidget);
    expect(find.text('Leroy Merlin'), findsOneWidget);
    expect(find.text('Luminária de mesa'), findsOneWidget);
  });

  testWidgets('on a network error it shows the message and a retry',
      (tester) async {
    var tentativas = 0;
    await _montar(
      tester,
      PartnersSection(
        state: PartnersViewState.error,
        partners: const [],
        productsByPartner: const {},
        errorMessage: 'Não foi possível conectar ao servidor',
        onRetry: () => tentativas++,
      ),
    );
    expect(find.text('Não foi possível conectar ao servidor'), findsOneWidget);
    await tester.tap(find.text('Tentar novamente'));
    expect(tentativas, 1);
  });
}
