import 'package:edu_ia/features/onboarding/presentation/onboarding_screen.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends TrackerApi {
  _FakeApi({this.objetivo, this.erro});

  final Goal? objetivo;
  final String? erro;
  String? tituloSalvo;
  DateTime? dataSalva;
  bool? atualizou;

  @override
  Future<Goal?> fetchGoal() async => objetivo;

  @override
  Future<int> saveGoal({
    required String title,
    required DateTime targetDate,
    required bool update,
  }) async {
    if (erro != null) throw TrackerException(erro!);
    tituloSalvo = title;
    dataSalva = targetDate;
    atualizou = update;
    return 99;
  }
}

Widget _harness(TrackerApi api) => MaterialApp(
  home: OnboardingScreen(api: api),
  routes: {'/home': (_) => const Scaffold(body: Text('HOME'))},
);

void main() {
  testWidgets('sem objetivo, os campos vêm vazios e o botão diz Começar', (tester) async {
    await tester.pumpWidget(_harness(_FakeApi()));
    await tester.pumpAndSettle();

    expect(find.text('Começar'), findsOneWidget);
    expect(find.text('Pular por enquanto'), findsOneWidget);
  });

  testWidgets('com objetivo, os campos vêm preenchidos e o botão diz Salvar', (tester) async {
    final api = _FakeApi(
      objetivo: Goal(
        title: 'Medicina USP',
        targetDate: DateTime(2027, 11, 7),
        daysElapsed: 0,
        daysTotal: 0,
      ),
    );
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    expect(find.text('Medicina USP'), findsOneWidget);
    expect(find.text('Salvar'), findsOneWidget);
  });

  testWidgets('objetivo em branco não envia nada', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, isNull);
    expect(find.textContaining('Diga o que você quer'), findsOneWidget);
  });

  testWidgets('salvar manda título e data e volta para a home', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina USP');
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, 'Medicina USP');
    expect(api.atualizou, isFalse);
    expect(find.text('HOME'), findsOneWidget);
  });

  testWidgets('a mensagem do servidor aparece na tela', (tester) async {
    final api = _FakeApi(erro: 'A data-alvo não pode estar no passado');
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina');
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(find.text('A data-alvo não pode estar no passado'), findsOneWidget);
  });

  testWidgets('pular vai para a home sem salvar nada', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Pular por enquanto'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, isNull);
    expect(find.text('HOME'), findsOneWidget);
  });
}
