import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/summary_provider.dart';
import 'package:flutter_test/flutter_test.dart';

StudySummary _resumo({Goal? goal}) => StudySummary(
  goal: goal,
  roadmap: const RoadmapProgress(totalSteps: 0, completedSteps: 0, progress: 0),
  points: const Points(total: 0, level: 1, streak: 0),
  study: const Study(answeredQuestions: 0, startedSubtopics: 0),
);

class _FakeApi extends TrackerApi {
  _FakeApi({this.resumo, this.erro});
  final StudySummary? resumo;
  final String? erro;

  @override
  Future<StudySummary> fetchSummary() async {
    if (erro != null) throw TrackerException(erro!);
    return resumo!;
  }
}

void main() {
  test('sucesso guarda o resumo', () async {
    final provider = SummaryProvider(api: _FakeApi(resumo: _resumo()));
    await provider.load();

    expect(provider.state, SummaryViewState.success);
    expect(provider.summary!.points.total, 0);
    expect(provider.errorMessage, isNull);
  });

  test('falha vira estado de erro com a mensagem do servidor', () async {
    final provider = SummaryProvider(api: _FakeApi(erro: 'servidor fora'));
    await provider.load();

    expect(provider.state, SummaryViewState.error);
    expect(provider.errorMessage, 'servidor fora');
    expect(provider.summary, isNull);
  });
}
