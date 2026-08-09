/// Modelos de domínio do pedido, do ponto de vista de separador/entregador
/// (Commerce Service — `back-end/commerce-service`).
class PedidoItem {
  // `products.id` é UUID desde a task B4 (bloco anterior); `fornecedores.id`
  // continua inteiro — nenhuma task deste bloco tocou a tabela de
  // fornecedores. Nenhum schema de staff devolve a chave `itens` hoje:
  // medido, `grep -n "itens" back-end/commerce-service/app/schemas/pedido.py`
  // devolve só a linha `itens: list[PedidoItemIn]` dentro de
  // `PedidoCreateIn` (corpo de `POST /orders`, contrato do aluno) — nenhuma
  // ocorrência em `PedidoStaffOut` nem `PedidoFilaOut`. Estes tipos existem
  // para o dia em que a lacuna de produto citada em `picking_screen.dart`
  // for fechada.
  final String produtoId;
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
      produtoId: json['produto_id'] as String,
      fornecedorId: json['fornecedor_id'] as int,
      quantidade: json['quantidade'] as int,
      precoUnitario: (json['preco_unitario'] as num).toDouble(),
      nomeProduto: json['nome_produto'] as String?,
    );
  }
}

enum StatusPedido {
  criado,
  confirmado,
  aguardandoSeparacao,
  emSeparacao,
  separado,
  aguardandoColeta,
  emTransito,
  entregue,
  cancelado,
  // Nenhum case caiu aqui por acidente. Antes desta task, um valor não
  // reconhecido caía no `default: return StatusPedido.cancelado` — e a task
  // C1 acrescentou o status `CONFIRMADO` ao backend sem que este enum
  // soubesse, então um pedido recém-pago (`"CONFIRMADO"`) aparecia como
  // "Cancelado" para o separador (medido: brief C4b, "O que quebrou,
  // medido"). `desconhecido` é a saída honesta para qualquer valor que o
  // app ainda não conhece — nunca mais um estado novo vira "Cancelado" por
  // acidente.
  desconhecido;

  static StatusPedido fromApi(String value) {
    switch (value) {
      case 'CRIADO':
        return StatusPedido.criado;
      case 'CONFIRMADO':
        return StatusPedido.confirmado;
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
      case 'CANCELADO':
        return StatusPedido.cancelado;
      default:
        return StatusPedido.desconhecido;
    }
  }

  String get label {
    switch (this) {
      case StatusPedido.criado:
        return 'Criado';
      case StatusPedido.confirmado:
        return 'Confirmado';
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
      case StatusPedido.desconhecido:
        return 'Status desconhecido';
    }
  }
}

class Pedido {
  final String id;
  final String userId;
  final StatusPedido status;
  final String enderecoEntrega;
  // Decimal serializado como string pelo Pydantic v2 — mesma convenção já
  // usada pelo contrato do aluno (`OrderSummary.total`, medido em
  // `front-end-flutter/lib/features/marketplace/domain/order_summary.dart:47`).
  // Não convertido para `double` aqui para não perder precisão decimal nem
  // divergir do padrão já estabelecido.
  final String total;
  final String? pickerId;
  final String? delivererId;
  final String? carrierName;
  final DateTime? estimatedDeliveryAt;
  final DateTime createdAt;
  final List<PedidoItem> itens;

  const Pedido({
    required this.id,
    required this.userId,
    required this.status,
    required this.enderecoEntrega,
    required this.total,
    this.pickerId,
    this.delivererId,
    this.carrierName,
    this.estimatedDeliveryAt,
    required this.createdAt,
    this.itens = const [],
  });

  /// Prefixo curto do UUID (8 primeiros caracteres, maiúsculo) para exibir
  /// ao operador nas telas de fila/detalhe. Decisão registrada no relatório
  /// da task C4b: o UUID inteiro é ruído para quem só precisa diferenciar
  /// pedidos numa lista — o prefixo já basta, e a busca/URL sempre usa
  /// [id] completo, nunca este valor.
  String get idCurto => id.length > 8 ? id.substring(0, 8).toUpperCase() : id.toUpperCase();

  factory Pedido.fromJson(Map<String, dynamic> json) {
    return Pedido(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      status: StatusPedido.fromApi(json['status'] as String),
      enderecoEntrega: json['endereco_entrega'] as String,
      total: json['total'] as String,
      pickerId: json['picker_id'] as String?,
      delivererId: json['deliverer_id'] as String?,
      carrierName: json['carrier_name'] as String?,
      estimatedDeliveryAt: json['estimated_delivery_at'] != null
          ? DateTime.parse(json['estimated_delivery_at'] as String)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
      itens: (json['itens'] as List<dynamic>? ?? [])
          .map((i) => PedidoItem.fromJson(i as Map<String, dynamic>))
          .toList(),
    );
  }
}
