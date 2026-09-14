import 'package:edu_ia/core/locale/app_locale.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Monta um app com a mesma configuração de idioma do `MaterialApp` raiz e um
/// botão que abre o seletor de data — o mesmo `showDatePicker` do cadastro e
/// do onboarding.
Future<void> _abrirSeletorDeData(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      locale: AppLocale.locale,
      supportedLocales: AppLocale.supportedLocales,
      localizationsDelegates: AppLocale.localizationsDelegates,
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () => showDatePicker(
              context: context,
              initialDate: DateTime(2000),
              firstDate: DateTime(1930),
              lastDate: DateTime(2026, 9, 13),
            ),
            child: const Text('abrir'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('abrir'));
  await tester.pumpAndSettle();
}

void main() {
  test('o app fala português do Brasil', () {
    expect(AppLocale.locale, const Locale('pt', 'BR'));
    expect(AppLocale.supportedLocales, [const Locale('pt', 'BR')]);
  });

  testWidgets('o seletor de data aparece em português, não em inglês', (
    tester,
  ) async {
    await _abrirSeletorDeData(tester);

    expect(find.text('Cancelar'), findsOneWidget);
    expect(find.text('OK'), findsOneWidget);
    expect(find.text('Selecione a data'), findsOneWidget);
    expect(find.text('Cancel'), findsNothing);
    expect(find.text('Select date'), findsNothing);
    expect(find.text('janeiro de 2000'), findsOneWidget);
  });
}
