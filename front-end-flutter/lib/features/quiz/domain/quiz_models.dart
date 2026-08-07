/// Modelos espelhando back-end/learning-service/app/schemas/{materias,
/// diagnostico,recomendacao}.py. Campos continuam em português — mesma
/// convenção do restante do learning-service (só commerce/auth traduziram
/// pro Flutter, ver docs/back-end/microservices.md).
library;

/// GET /subjects
class Materia {
  const Materia({required this.id, required this.nome});

  factory Materia.fromJson(Map<String, dynamic> json) {
    return Materia(id: json['id'] as int, nome: json['nome'] as String);
  }

  final int id;
  final String nome;
}

/// GET /subjects/{materia_id}/topics
class Tema {
  const Tema({
    required this.id,
    required this.materiaId,
    required this.nome,
    required this.ordem,
  });

  factory Tema.fromJson(Map<String, dynamic> json) {
    return Tema(
      id: json['id'] as int,
      materiaId: json['materia_id'] as int,
      nome: json['nome'] as String,
      ordem: json['ordem'] as int,
    );
  }

  final int id;
  final int materiaId;
  final String nome;
  final int ordem;
}

/// Uma questão do questionário de diagnóstico — devolvida por GET
/// /topics/{tema_id}/quiz, SEM o gabarito (o backend nunca manda a
/// resposta certa antes de `POST /diagnostic/answer`).
class QuestaoQuiz {
  const QuestaoQuiz({
    required this.id,
    required this.subtemaId,
    required this.enunciado,
    required this.alternativas,
    required this.nivelDificuldade,
  });

  factory QuestaoQuiz.fromJson(Map<String, dynamic> json) {
    return QuestaoQuiz(
      id: json['id'] as int,
      subtemaId: json['subtema_id'] as int,
      enunciado: json['enunciado'] as String,
      // {"A": "...", "B": "...", ...} — a ordem das chaves no JSON decodado
      // preserva a ordem de inserção original (LinkedHashMap), então as
      // alternativas aparecem na tela na mesma ordem que o backend gerou.
      alternativas: (json['alternativas'] as Map<String, dynamic>).map(
        (k, v) => MapEntry(k, v as String),
      ),
      nivelDificuldade: json['nivel_dificuldade'] as int,
    );
  }

  final int id;
  final int subtemaId;
  final String enunciado;
  final Map<String, String> alternativas;
  final int nivelDificuldade;
}

/// Corpo de POST /diagnostic/answer.
class RespostaItem {
  const RespostaItem({
    required this.questaoId,
    required this.alternativaEscolhida,
  });

  final int questaoId;

  /// Letra da alternativa marcada ("A", "B", "C"...) — não um índice.
  final String alternativaEscolhida;

  Map<String, dynamic> toJson() => {
    'questao_id': questaoId,
    'alternativa_escolhida': alternativaEscolhida,
  };
}

/// Resposta de POST /diagnostic/answer — resultado completo do
/// diagnóstico, já com a nota calculada, ação recomendada e mensagem do
/// tutor gerada por IA. Nunca é um simples "X acertos de Y": o backend
/// avalia CADA subtema do tema separadamente antes de agregar.
class DiagnosticoResultado {
  const DiagnosticoResultado({
    required this.temaId,
    required this.dominioTema,
    required this.acao,
    required this.subtemasAvaliados,
    required this.recomendacoesConteudo,
    required this.temaRecomendado,
    required this.mensagemTutor,
  });

  factory DiagnosticoResultado.fromJson(Map<String, dynamic> json) {
    return DiagnosticoResultado(
      temaId: json['tema_id'] as int,
      dominioTema: (json['dominio_tema'] as num).toDouble(),
      acao: json['acao'] as String,
      subtemasAvaliados: (json['subtemas_avaliados'] as List<dynamic>)
          .map((e) => SubtemaAvaliado.fromJson(e as Map<String, dynamic>))
          .toList(),
      recomendacoesConteudo: (json['recomendacoes_conteudo'] as List<dynamic>)
          .map((e) => RecomendacaoConteudo.fromJson(e as Map<String, dynamic>))
          .toList(),
      temaRecomendado: json['tema_recomendado'] == null
          ? null
          : TemaResumo.fromJson(
              json['tema_recomendado'] as Map<String, dynamic>,
            ),
      mensagemTutor: json['mensagem_tutor'] as String,
    );
  }

  final int temaId;

  /// 0.0–1.0. Média ponderada do domínio de todos os subtemas do tema.
  final double dominioTema;

  /// 'estudar' | 'avancar' | 'retroceder'.
  final String acao;
  final List<SubtemaAvaliado> subtemasAvaliados;
  final List<RecomendacaoConteudo> recomendacoesConteudo;

  /// Tema pré-requisito (se [acao] == 'retroceder') ou próximo da trilha
  /// (se [acao] == 'avancar'). Null se [acao] == 'estudar', ou se não há
  /// tema anterior/próximo cadastrado.
  final TemaResumo? temaRecomendado;

  /// Nunca vazio — se o LLM falhar, o backend usa um fallback determinístico.
  final String mensagemTutor;
}

class SubtemaAvaliado {
  const SubtemaAvaliado({
    required this.subtemaId,
    required this.nome,
    required this.dominio,
    required this.classificacao,
    required this.proximaRevisao,
  });

  factory SubtemaAvaliado.fromJson(Map<String, dynamic> json) {
    return SubtemaAvaliado(
      subtemaId: json['subtema_id'] as int,
      nome: json['nome'] as String,
      dominio: (json['dominio'] as num).toDouble(),
      classificacao: json['classificacao'] as String,
      proximaRevisao: DateTime.parse(json['proxima_revisao'] as String),
    );
  }

  final int subtemaId;
  final String nome;

  /// 0.0–1.0.
  final double dominio;

  /// 'estudar_do_zero' | 'revisar' | 'dominado'.
  final String classificacao;
  final DateTime proximaRevisao;
}

class SubtemaRelacionado {
  const SubtemaRelacionado({
    required this.subtemaId,
    required this.nome,
    required this.similaridade,
  });

  factory SubtemaRelacionado.fromJson(Map<String, dynamic> json) {
    return SubtemaRelacionado(
      subtemaId: json['subtema_id'] as int,
      nome: json['nome'] as String,
      similaridade: (json['similaridade'] as num).toDouble(),
    );
  }

  final int subtemaId;
  final String nome;
  final double similaridade;
}

class RecomendacaoConteudo {
  const RecomendacaoConteudo({
    required this.subtemaId,
    required this.nome,
    required this.motivo,
    required this.videoUrl,
    required this.subtemasRelacionados,
  });

  factory RecomendacaoConteudo.fromJson(Map<String, dynamic> json) {
    return RecomendacaoConteudo(
      subtemaId: json['subtema_id'] as int,
      nome: json['nome'] as String,
      motivo: json['motivo'] as String,
      videoUrl: json['video_url'] as String?,
      subtemasRelacionados:
          (json['subtemas_relacionados'] as List<dynamic>? ?? const [])
              .map((e) => SubtemaRelacionado.fromJson(e as Map<String, dynamic>))
              .toList(),
    );
  }

  final int subtemaId;
  final String nome;

  /// 'estudar_do_zero' | 'revisar'.
  final String motivo;
  final String? videoUrl;
  final List<SubtemaRelacionado> subtemasRelacionados;
}

class TemaResumo {
  const TemaResumo({required this.id, required this.nome});

  factory TemaResumo.fromJson(Map<String, dynamic> json) {
    return TemaResumo(id: json['id'] as int, nome: json['nome'] as String);
  }

  final int id;
  final String nome;
}
