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
}) => RoadmapStep(
  subtopicId: id,
  subtopicName: nome,
  topicName: 'Citologia',
  subjectName: 'Biologia',
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

Widget _harness(TrackerProvider provider) => MaterialApp(
  home: ChangeNotifierProvider.value(value: provider, child: const TrackerView()),
  routes: {'/onboarding': (_) => const Scaffold(body: Text('ONBOARDING'))},
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

  testWidgets('etapa com questão tem botão de praticar habilitado', (tester) async {
    final provider = TrackerProvider(api: _FakeApi(_roadmap(etapas: [_etapa()])));
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    final botao = tester.widget<ElevatedButton>(find.byType(ElevatedButton).first);
    expect(botao.onPressed, isNotNull);
    expect(find.text('Praticar'), findsOneWidget);
  });

  testWidgets('etapa concluída aparece marcada', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(concluida: true)])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('falha mostra a mensagem, não uma tela em branco', (tester) async {
    final provider = TrackerProvider(api: _FakeApi(_roadmap(), erro: 'servidor fora'));
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('servidor fora'), findsOneWidget);
  });
}
