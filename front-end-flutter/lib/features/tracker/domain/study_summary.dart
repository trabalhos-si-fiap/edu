/// Modelos do resumo de estudo — o que `GET /profile/summary` devolve.
///
/// Todo número desta tela vem daqui, e daqui vem só o que o backend mandou:
/// a spec D existe porque a tela inicial anunciava um par de dias
/// inventado para qualquer aluno.
///
/// O parsing é tolerante a tipo (`_asInt`/`_asDouble`) porque JSON de
/// número em Dart chega como `int` ou `double` conforme o valor, e um
/// `as double` estoura em `1` (int) enquanto `1.0` passa. Ausência de
/// campo vira zero, nunca exceção: uma tela que não desenha é pior que uma
/// tela que desenha zero.
library;

int _asInt(dynamic valor) {
  if (valor is int) return valor;
  if (valor is num) return valor.toInt();
  if (valor is String) return int.tryParse(valor) ?? 0;
  return 0;
}

double _asDouble(dynamic valor) {
  if (valor is num) return valor.toDouble();
  if (valor is String) return double.tryParse(valor) ?? 0.0;
  return 0.0;
}

DateTime? _asDate(dynamic valor) {
  if (valor is String && valor.isNotEmpty) return DateTime.tryParse(valor);
  return null;
}

class Goal {
  const Goal({
    required this.title,
    required this.targetDate,
    required this.daysElapsed,
    required this.daysTotal,
  });

  final String title;
  final DateTime targetDate;
  final int daysElapsed;
  final int daysTotal;

  /// Fração do prazo já percorrida, 0.0 a 1.0. Zero quando o objetivo foi
  /// criado para hoje — o denominador é zero e a barra fica vazia em vez de
  /// estourar.
  double get elapsedFraction => daysTotal <= 0 ? 0.0 : (daysElapsed / daysTotal).clamp(0.0, 1.0);

  static Goal? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    return Goal(
      title: (json['titulo'] ?? '') as String,
      targetDate: _asDate(json['data_alvo']) ?? DateTime.now(),
      daysElapsed: _asInt(json['dias_decorridos']),
      daysTotal: _asInt(json['dias_totais']),
    );
  }
}

class RoadmapProgress {
  const RoadmapProgress({
    required this.totalSteps,
    required this.completedSteps,
    required this.progress,
  });

  final int totalSteps;
  final int completedSteps;
  final double progress;

  factory RoadmapProgress.fromJson(Map<String, dynamic>? json) => RoadmapProgress(
    totalSteps: _asInt(json?['etapas_totais']),
    completedSteps: _asInt(json?['etapas_concluidas']),
    progress: _asDouble(json?['progresso']),
  );
}

class Points {
  const Points({required this.total, required this.level, required this.streak});

  final int total;
  final int level;
  final int streak;

  factory Points.fromJson(Map<String, dynamic>? json) => Points(
    total: _asInt(json?['total']),
    // Nível mínimo é 1, nunca 0: um aluno sem pontos está no nível 1.
    level: json?['nivel'] == null ? 1 : _asInt(json?['nivel']),
    streak: _asInt(json?['streak']),
  );
}

class Study {
  const Study({required this.answeredQuestions, required this.startedSubtopics});

  final int answeredQuestions;
  final int startedSubtopics;

  factory Study.fromJson(Map<String, dynamic>? json) => Study(
    answeredQuestions: _asInt(json?['questoes_respondidas']),
    startedSubtopics: _asInt(json?['subtemas_iniciados']),
  );
}

class StudySummary {
  const StudySummary({
    required this.goal,
    required this.roadmap,
    required this.points,
    required this.study,
  });

  final Goal? goal;
  final RoadmapProgress roadmap;
  final Points points;
  final Study study;

  factory StudySummary.fromJson(Map<String, dynamic> json) => StudySummary(
    goal: Goal.fromJson(json['objetivo'] as Map<String, dynamic>?),
    roadmap: RoadmapProgress.fromJson(json['roadmap'] as Map<String, dynamic>?),
    points: Points.fromJson(json['pontos'] as Map<String, dynamic>?),
    study: Study.fromJson(json['estudo'] as Map<String, dynamic>?),
  );
}
