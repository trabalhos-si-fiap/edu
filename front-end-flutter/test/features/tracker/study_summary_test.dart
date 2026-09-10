import 'package:edu_ia/features/tracker/domain/roadmap_step.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('aluno zerado vira zeros, não nulos', () {
    final resumo = StudySummary.fromJson(const {
      'objetivo': null,
      'roadmap': {'etapas_totais': 0, 'etapas_concluidas': 0, 'progresso': 0.0},
      'pontos': {'total': 0, 'nivel': 1, 'streak': 0},
      'estudo': {'questoes_respondidas': 0, 'subtemas_iniciados': 0},
    });

    expect(resumo.goal, isNull);
    expect(resumo.points.total, 0);
    expect(resumo.points.level, 1);
    expect(resumo.roadmap.progress, 0.0);
    expect(resumo.study.answeredQuestions, 0);
  });

  test('objetivo preenchido traz título, data e os dois contadores de dias', () {
    final resumo = StudySummary.fromJson(const {
      'objetivo': {
        'titulo': 'Medicina USP',
        'data_alvo': '2027-11-07',
        'dias_decorridos': 124,
        'dias_totais': 200,
      },
      'roadmap': {'etapas_totais': 50, 'etapas_concluidas': 34, 'progresso': 0.68},
      'pontos': {'total': 3120, 'nivel': 8, 'streak': 4},
      'estudo': {'questoes_respondidas': 15, 'subtemas_iniciados': 6},
    });

    expect(resumo.goal!.title, 'Medicina USP');
    expect(resumo.goal!.targetDate, DateTime(2027, 11, 7));
    expect(resumo.goal!.daysElapsed, 124);
    expect(resumo.goal!.daysTotal, 200);
    expect(resumo.roadmap.progress, 0.68);
  });

  test('número que chega como int ou como string não quebra a tela', () {
    final resumo = StudySummary.fromJson(const {
      'objetivo': null,
      'roadmap': {'etapas_totais': 3, 'etapas_concluidas': 1, 'progresso': 1},
      'pontos': {'total': 10, 'nivel': 1, 'streak': 0},
      'estudo': {'questoes_respondidas': 2, 'subtemas_iniciados': 1},
    });

    expect(resumo.roadmap.progress, 1.0);
  });

  test('campo ausente não derruba o parse — vira zero', () {
    final resumo = StudySummary.fromJson(const {'objetivo': null});
    expect(resumo.points.total, 0);
    expect(resumo.roadmap.totalSteps, 0);
    expect(resumo.study.startedSubtopics, 0);
  });

  test('etapa do roadmap sabe se dá para praticar', () {
    final etapa = RoadmapStep.fromJson(const {
      'subtema_id': 7,
      'subtema_nome': 'Membrana Plasmática',
      'tema_nome': 'Citologia',
      'materia_nome': 'Biologia',
      'ordem': 0,
      'prazo': '2026-10-01',
      'concluida': false,
      'concluida_em': null,
      'tem_questoes': false,
    });

    expect(etapa.subtopicName, 'Membrana Plasmática');
    expect(etapa.subjectName, 'Biologia');
    expect(etapa.deadline, DateTime(2026, 10, 1));
    expect(etapa.done, isFalse);
    expect(etapa.hasQuestions, isFalse);
  });

  test('roadmap sem objetivo carrega o motivo para a tela exibir', () {
    final roadmap = Roadmap.fromJson(const {
      'objetivo': null,
      'motivo': 'Defina um objetivo e uma data-alvo para montar seu percurso.',
      'prazo_apertado': false,
      'items': [],
      'total': 0,
      'limit': 50,
      'offset': 0,
    });

    expect(roadmap.steps, isEmpty);
    expect(roadmap.reason, contains('objetivo'));
    expect(roadmap.goal, isNull);
  });
}
