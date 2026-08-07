/// Espelha back-end/learning-service/app/schemas/revisao.py.
class Review {
  const Review({
    required this.subtemaId,
    required this.nome,
    required this.nivelDominio,
    required this.proximaRevisao,
    required this.videoUrl,
  });

  factory Review.fromJson(Map<String, dynamic> json) {
    return Review(
      subtemaId: json['subtema_id'] as int,
      nome: json['nome'] as String,
      nivelDominio: (json['nivel_dominio'] as num).toDouble(),
      proximaRevisao: json['proxima_revisao'] == null
          ? null
          : DateTime.parse(json['proxima_revisao'] as String),
      videoUrl: json['video_url'] as String?,
    );
  }

  final int subtemaId;
  final String nome;

  /// 0.0–1.0 — nível de domínio no momento da última resposta (calculado
  /// pelo algoritmo SM-2 em app/services/sm2.py).
  final double nivelDominio;

  /// Data em que este subtema ficou (ou fica) devido para revisão. Null
  /// só ocorre se o registro de progresso nunca teve uma revisão agendada.
  final DateTime? proximaRevisao;
  final String? videoUrl;
}
