import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/roadmap_step.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/tracker_provider.dart';
import 'package:edu_ia/features/tracker/presentation/tracker_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

RoadmapStep _etapa({
  int id = 1,
  String nome = 'Membrana Plasmática',
  bool concluida = false,
  bool temQuestoes = true,
  int temaId = 5,
  String materia = 'Biologia',
}) => RoadmapStep(
  subtopicId: id,
  subtopicName: nome,
  topicId: temaId,
  topicName: 'Citologia',
  subjectName: materia,
  order: id - 1,
  deadline: DateTime(2026, 10, 1),
  done: concluida,
  hasQuestions: temQuestoes,
);

class _FakeApi extends TrackerApi {
  _FakeApi(this.roadmap, {this.erro});
  final Roadmap roadmap;
  final String? erro;

  @override
  Future<Roadmap> fetchRoadmap({int limit = 50, int offset = 0}) async {
    if (erro != null) throw TrackerException(erro!);
    return roadmap;
  }
}

Roadmap _roadmap({List<RoadmapStep> etapas = const [], String? motivo}) => Roadmap(
  goal: motivo == null
      ? Goal(
          title: 'Medicina USP',
          targetDate: DateTime(2027, 11, 7),
          daysElapsed: 10,
          daysTotal: 100,
        )
      : null,
  reason: motivo,
  tightDeadline: false,
  steps: etapas,
  total: etapas.length,
);

Widget _harness(TrackerProvider provider, {void Function(RouteSettings)? aoNavegar}) => MaterialApp(
  home: ChangeNotifierProvider.value(value: provider, child: const TrackerView()),
  routes: {'/onboarding': (_) => const Scaffold(body: Text('ONBOARDING'))},
  // Só usado pelos testes que precisam saber para onde o Navigator.pushNamed
  // foi — os demais não passam `aoNavegar` e o comportamento não muda.
  onGenerateRoute: aoNavegar == null
      ? null
      : (settings) {
          aoNavegar(settings);
          return MaterialPageRoute(builder: (_) => const Scaffold(body: Text('DESTINO')));
        },
);

void main() {
  testWidgets('sem objetivo, a tela convida ao onboarding', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(motivo: 'Defina um objetivo e uma data-alvo para montar seu percurso.')),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.textContaining('Defina um objetivo'), findsOneWidget);
    expect(find.text('Definir objetivo'), findsOneWidget);
  });

  testWidgets('com percurso, lista as etapas agrupadas por matéria', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(), _etapa(id: 2, nome: 'Organelas')])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('Biologia'), findsOneWidget); // cabeçalho da matéria
    expect(find.text('Membrana Plasmática'), findsOneWidget);
    expect(find.text('Organelas'), findsOneWidget);
  });

  testWidgets('etapa sem questão fica desabilitada e diz por quê', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(temQuestoes: false)])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('Conteúdo em preparação'), findsOneWidget);
    final botao = tester.widget<ElevatedButton>(find.byType(ElevatedButton).first);
    expect(botao.onPressed, isNull);
  });

  testWidgets(
    'etapa com questão tem botão de praticar habilitado e leva ao quiz do próprio tema',
    (tester) async {
      final provider = TrackerProvider(
        api: _FakeApi(_roadmap(etapas: [_etapa(temaId: 42)])),
      );
      RouteSettings? rotaEmpurrada;
      await tester.pumpWidget(
        _harness(provider, aoNavegar: (settings) => rotaEmpurrada = settings),
      );
      await provider.load();
      await tester.pumpAndSettle();

      final botao = tester.widget<ElevatedButton>(find.byType(ElevatedButton).first);
      expect(botao.onPressed, isNotNull);
      expect(find.text('Praticar'), findsOneWidget);

      await tester.tap(find.text('Praticar'));
      await tester.pumpAndSettle();

      // '/questions' é o QuizScreen de verdade — '/quiz' é só o seletor de
      // matérias, e empurrar pra lá descartaria o tema que o aluno escolheu.
      expect(rotaEmpurrada?.name, '/questions');
      expect(rotaEmpurrada?.arguments, {
        'materiaNome': 'Biologia',
        'temaId': 42,
        'temaNome': 'Citologia',
      });
    },
  );

  testWidgets('etapa concluída aparece marcada', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(concluida: true)])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('a barra de navegação aparece com a aba Estudo marcada', (tester) async {
    final provider = TrackerProvider(api: _FakeApi(_roadmap(etapas: [_etapa()])));
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    // A aba Estudo troca a rota em vez de empilhar: sem a barra aqui, quem
    // chega pela aba não teria como sair do percurso.
    final barra = tester.widget<NavBar>(find.byType(NavBar));
    expect(barra.currentIndex, 3);
  });

  testWidgets('etapa pendente aparece como item de checklist desmarcado', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(), _etapa(id: 2, nome: 'Organelas', concluida: true)])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.radio_button_unchecked), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('cada matéria mostra quantas das suas etapas estão concluídas', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(
        _roadmap(
          etapas: [
            _etapa(concluida: true),
            _etapa(id: 2, nome: 'Organelas'),
            _etapa(id: 3, nome: 'Funções', materia: 'Matemática'),
          ],
        ),
      ),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('1/2 concluídas'), findsOneWidget); // Biologia
    expect(find.text('0/1 concluídas'), findsOneWidget); // Matemática
  });

  testWidgets('falha mostra a mensagem, não uma tela em branco', (tester) async {
    final provider = TrackerProvider(api: _FakeApi(_roadmap(), erro: 'servidor fora'));
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('servidor fora'), findsOneWidget);
  });
}
