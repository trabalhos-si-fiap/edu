class ProdutoSugerido {
  final String id;
  final String nome;
  final double preco;
  final String? imagemUrl;

  const ProdutoSugerido({
    required this.id,
    required this.nome,
    required this.preco,
    this.imagemUrl,
  });

  factory ProdutoSugerido.fromJson(Map<String, dynamic> json) {
    return ProdutoSugerido(
      id: json['id'] as String,
      nome: json['nome'] as String,
      preco: (json['preco'] as num).toDouble(),
      imagemUrl: json['imagem_url'] as String?,
    );
  }
}

/// Ocorrência excepcional durante separação (falta de estoque) ou entrega
/// (atraso), reportada por separador/entregador e resolvida pelo aluno.
class Ocorrencia {
  // `id` da ocorrência continua inteiro — o schema do backend
  // (`OcorrenciaOut.id`) mantém; só `pedido_id` acompanhou `orders.id`
  // virando UUID (task C3), e `produto_id` acompanhou `products.id` (B4).
  final int id;
  final String pedidoId;
  final String tipo; // FALTA_ESTOQUE | ATRASO_ENTREGA
  final String status; // ABERTA | RESOLVIDA
  final String? produtoId;
  final DateTime? novaDataSugerida;
  final String motivo;
  final String? resolucao;
  final DateTime criadoEm;
  final ProdutoSugerido? produtoOriginal;
  final List<ProdutoSugerido> produtosSugeridos;

  const Ocorrencia({
    required this.id,
    required this.pedidoId,
    required this.tipo,
    required this.status,
    this.produtoId,
    this.novaDataSugerida,
    required this.motivo,
    this.resolucao,
    required this.criadoEm,
    this.produtoOriginal,
    this.produtosSugeridos = const [],
  });

  bool get aberta => status == 'ABERTA';

  factory Ocorrencia.fromJson(Map<String, dynamic> json) {
    return Ocorrencia(
      id: json['id'] as int,
      pedidoId: json['pedido_id'] as String,
      tipo: json['tipo'] as String,
      status: json['status'] as String,
      produtoId: json['produto_id'] as String?,
      novaDataSugerida: json['nova_data_sugerida'] != null
          ? DateTime.parse(json['nova_data_sugerida'] as String)
          : null,
      motivo: json['motivo'] as String,
      resolucao: json['resolucao'] as String?,
      criadoEm: DateTime.parse(json['criado_em'] as String),
      produtoOriginal: json['produto_original'] != null
          ? ProdutoSugerido.fromJson(json['produto_original'] as Map<String, dynamic>)
          : null,
      produtosSugeridos: (json['produtos_sugeridos'] as List<dynamic>? ?? [])
          .map((p) => ProdutoSugerido.fromJson(p as Map<String, dynamic>))
          .toList(),
    );
  }
}
