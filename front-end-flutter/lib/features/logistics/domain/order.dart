/// Modelos de domínio do pedido, do ponto de vista de separador/entregador
/// (Commerce Service — `back-end/commerce-service`).
class PedidoItem {
  final int produtoId;
  final int fornecedorId;
  final int quantidade;
  final double precoUnitario;
  final String? nomeProduto;

  const PedidoItem({
    required this.produtoId,
    required this.fornecedorId,
    required this.quantidade,
    required this.precoUnitario,
    this.nomeProduto,
  });

  factory PedidoItem.fromJson(Map<String, dynamic> json) {
    return PedidoItem(
      produtoId: json['produto_id'] as int,
      fornecedorId: json['fornecedor_id'] as int,
      quantidade: json['quantidade'] as int,
      precoUnitario: (json['preco_unitario'] as num).toDouble(),
      nomeProduto: json['nome_produto'] as String?,
    );
  }
}

enum StatusPedido {
  criado,
  aguardandoSeparacao,
  emSeparacao,
  separado,
  aguardandoColeta,
  emTransito,
  entregue,
  cancelado;

  static StatusPedido fromApi(String value) {
    switch (value) {
      case 'CRIADO':
        return StatusPedido.criado;
      case 'AGUARDANDO_SEPARACAO':
        return StatusPedido.aguardandoSeparacao;
      case 'EM_SEPARACAO':
        return StatusPedido.emSeparacao;
      case 'SEPARADO':
        return StatusPedido.separado;
      case 'AGUARDANDO_COLETA':
        return StatusPedido.aguardandoColeta;
      case 'EM_TRANSITO':
        return StatusPedido.emTransito;
      case 'ENTREGUE':
        return StatusPedido.entregue;
      default:
        return StatusPedido.cancelado;
    }
  }

  String get label {
    switch (this) {
      case StatusPedido.criado:
        return 'Criado';
      case StatusPedido.aguardandoSeparacao:
        return 'Aguardando Separação';
      case StatusPedido.emSeparacao:
        return 'Em Separação';
      case StatusPedido.separado:
        return 'Separado';
      case StatusPedido.aguardandoColeta:
        return 'Aguardando Coleta';
      case StatusPedido.emTransito:
        return 'Em Trânsito';
      case StatusPedido.entregue:
        return 'Entregue';
      case StatusPedido.cancelado:
        return 'Cancelado';
    }
  }
}

class Pedido {
  final int id;
  final String alunoId;
  final StatusPedido status;
  final String enderecoEntrega;
  final double valorTotal;
  final String? separadorId;
  final String? entregadorId;
  final String? transportadoraNome;
  final DateTime criadoEm;
  final List<PedidoItem> itens;

  const Pedido({
    required this.id,
    required this.alunoId,
    required this.status,
    required this.enderecoEntrega,
    required this.valorTotal,
    this.separadorId,
    this.entregadorId,
    this.transportadoraNome,
    required this.criadoEm,
    this.itens = const [],
  });

  factory Pedido.fromJson(Map<String, dynamic> json) {
    return Pedido(
      id: json['id'] as int,
      alunoId: json['aluno_id'] as String,
      status: StatusPedido.fromApi(json['status'] as String),
      enderecoEntrega: json['endereco_entrega'] as String,
      valorTotal: (json['valor_total'] as num).toDouble(),
      separadorId: json['separador_id'] as String?,
      entregadorId: json['entregador_id'] as String?,
      transportadoraNome: json['transportadora_nome'] as String?,
      criadoEm: DateTime.parse(json['criado_em'] as String),
      itens: (json['itens'] as List<dynamic>? ?? [])
          .map((i) => PedidoItem.fromJson(i as Map<String, dynamic>))
          .toList(),
    );
  }
}
