import 'study_summary.dart';

/// Uma etapa do percurso e o envelope que `GET /roadmap` devolve.
class RoadmapStep {
  const RoadmapStep({
    required this.subtopicId,
    required this.subtopicName,
    required this.topicName,
    required this.subjectName,
    required this.order,
    required this.deadline,
    required this.done,
    required this.hasQuestions,
  });

  final int subtopicId;
  final String subtopicName;
  final String topicName;
  final String subjectName;
  final int order;
  final DateTime deadline;
  final bool done;

  /// `false` quando a matéria ainda não tem questão semeada. A tela mostra a
  /// etapa assim mesmo, com o botão desabilitado e o motivo — é a
  /// alternativa honesta a esconder a matéria.
  final bool hasQuestions;

  factory RoadmapStep.fromJson(Map<String, dynamic> json) => RoadmapStep(
    subtopicId: (json['subtema_id'] as num?)?.toInt() ?? 0,
    subtopicName: (json['subtema_nome'] ?? '') as String,
    topicName: (json['tema_nome'] ?? '') as String,
    subjectName: (json['materia_nome'] ?? '') as String,
    order: (json['ordem'] as num?)?.toInt() ?? 0,
    deadline: DateTime.tryParse((json['prazo'] ?? '') as String) ?? DateTime.now(),
    done: json['concluida'] == true,
    hasQuestions: json['tem_questoes'] == true,
  );
}

class Roadmap {
  const Roadmap({
    required this.goal,
    required this.reason,
    required this.tightDeadline,
    required this.steps,
    required this.total,
  });

  final Goal? goal;

  /// Só vem preenchido quando a lista está vazia por falta de objetivo — é o
  /// convite ao onboarding que a tela exibe.
  final String? reason;
  final bool tightDeadline;
  final List<RoadmapStep> steps;
  final int total;

  factory Roadmap.fromJson(Map<String, dynamic> json) => Roadmap(
    goal: Goal.fromJson(json['objetivo'] as Map<String, dynamic>?),
    reason: json['motivo'] as String?,
    tightDeadline: json['prazo_apertado'] == true,
    steps: ((json['items'] ?? const []) as List<dynamic>)
        .map((e) => RoadmapStep.fromJson(e as Map<String, dynamic>))
        .toList(),
    total: (json['total'] as num?)?.toInt() ?? 0,
  );
}
