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

/// Abre o date picker pelo campo (ainda vazio, mostrando a dica), escolhe o
/// dia de hoje — sempre selecionável, já que `firstDate` é hoje — e confirma
/// em OK. Usado pelos testes que precisam de uma data-alvo válida para
/// passar da validação local e chegar até `TrackerApi.saveGoal`.
Future<void> _escolherHoje(WidgetTester tester) async {
  await tester.tap(find.text('Escolha a data da prova'));
  await tester.pumpAndSettle();
  final hoje = DateTime.now();
  await tester.tap(find.text(hoje.day.toString()));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('sem objetivo, os campos vêm vazios e o botão diz Começar', (tester) async {
    await tester.pumpWidget(_harness(_FakeApi()));
    await tester.pumpAndSettle();

    expect(find.text('Começar'), findsOneWidget);
    expect(find.text('Pular por enquanto'), findsOneWidget);
  });

  testWidgets('a dica do objetivo sugere uma meta do ENEM', (tester) async {
    await tester.pumpWidget(_harness(_FakeApi()));
    await tester.pumpAndSettle();

    final campo = tester.widget<TextField>(find.byType(TextField).first);
    expect(campo.decoration?.hintText, 'Ex.: Medicina pelo ENEM');
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
    await _escolherHoje(tester);
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
    await _escolherHoje(tester);
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

  testWidgets('sem escolher a data, Começar não envia nada e mostra o erro', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina USP');
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, isNull);
    expect(find.text('Escolha uma data-alvo'), findsOneWidget);
  });

  testWidgets('a data escolhida no calendário é a que é enviada', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina USP');
    await _escolherHoje(tester);
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    final hoje = DateTime.now();
    expect(api.dataSalva, DateTime(hoje.year, hoje.month, hoje.day));
  });

  testWidgets('justRegistered viaja para a home quando o aluno salva', (tester) async {
    final api = _FakeApi();
    Object? argumentosRecebidos;
    var rotaRecebida = '';
    await tester.pumpWidget(
      MaterialApp(
        onGenerateInitialRoutes: (_) => [
          MaterialPageRoute(
            settings: const RouteSettings(
              name: '/onboarding',
              arguments: {'justRegistered': true},
            ),
            builder: (_) => OnboardingScreen(api: api),
          ),
        ],
        onGenerateRoute: (settings) {
          rotaRecebida = settings.name ?? '';
          argumentosRecebidos = settings.arguments;
          return MaterialPageRoute(builder: (_) => const Scaffold(body: Text('HOME')));
        },
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina USP');
    await _escolherHoje(tester);
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(rotaRecebida, '/home');
    expect(argumentosRecebidos, {'justRegistered': true});
  });

  testWidgets('justRegistered viaja para a home quando o aluno pula', (tester) async {
    final api = _FakeApi();
    Object? argumentosRecebidos;
    var rotaRecebida = '';
    await tester.pumpWidget(
      MaterialApp(
        onGenerateInitialRoutes: (_) => [
          MaterialPageRoute(
            settings: const RouteSettings(
              name: '/onboarding',
              arguments: {'justRegistered': true},
            ),
            builder: (_) => OnboardingScreen(api: api),
          ),
        ],
        onGenerateRoute: (settings) {
          rotaRecebida = settings.name ?? '';
          argumentosRecebidos = settings.arguments;
          return MaterialPageRoute(builder: (_) => const Scaffold(body: Text('HOME')));
        },
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Pular por enquanto'));
    await tester.pumpAndSettle();

    expect(rotaRecebida, '/home');
    expect(argumentosRecebidos, {'justRegistered': true});
  });

  testWidgets('salvar no modo edição manda update verdadeiro', (tester) async {
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

    await tester.tap(find.text('Salvar'));
    await tester.pumpAndSettle();

    expect(api.atualizou, isTrue);
    expect(find.text('HOME'), findsOneWidget);
  });
}
