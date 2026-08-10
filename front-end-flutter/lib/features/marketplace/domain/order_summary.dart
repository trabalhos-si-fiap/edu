/// Status de entrega de um pedido. Espelha `StatusContrato` do backend
/// (pending -> confirmed -> separating -> out_for_delivery -> delivered),
/// mais `cancelled`, que é a saída do fluxo e não um passo dele.
enum OrderSummaryStatus {
  pending,
  confirmed,
  separating,
  outForDelivery,
  delivered,
  cancelled,
}

OrderSummaryStatus _statusFromJson(String? raw) {
  switch (raw) {
    case 'confirmed':
      return OrderSummaryStatus.confirmed;
    case 'separating':
      return OrderSummaryStatus.separating;
    case 'out_for_delivery':
      return OrderSummaryStatus.outForDelivery;
    case 'delivered':
      return OrderSummaryStatus.delivered;
    // Sem este caso, o `default` abaixo faria um pedido cancelado aparecer
    // como "Pendente", no passo 0 do stepper, para sempre — e ele nunca
    // sairia da lista de pedidos ativos.
    case 'cancelled':
      return OrderSummaryStatus.cancelled;
    case 'pending':
    default:
      return OrderSummaryStatus.pending;
  }
}

/// Item de um pedido, na visão da listagem. Espelha `OrderItemOut`.
class OrderItemSummary {
  final String productName;
  final String imageUrl;
  final int quantity;

  const OrderItemSummary({
    required this.productName,
    required this.imageUrl,
    required this.quantity,
  });

  factory OrderItemSummary.fromJson(Map<String, dynamic> json) {
    return OrderItemSummary(
      productName: (json['product_name'] as String?) ?? '',
      imageUrl: (json['image_url'] as String?) ?? '',
      quantity: (json['quantity'] as num?)?.toInt() ?? 0,
    );
  }
}

/// Pedido na visão da tela "Seus pedidos". Espelha `OrderOut` do backend:
/// `id` é UUID (string), `total` chega como string decimal ("242.00"),
/// `status` é um dos valores de [OrderSummaryStatus] e `created_at` é ISO-8601.
class OrderSummary {
  final String id;
  final String total;
  final OrderSummaryStatus status;
  final DateTime? createdAt;
  final List<OrderItemSummary> items;

  const OrderSummary({
    required this.id,
    required this.total,
    required this.status,
    required this.createdAt,
    required this.items,
  });

  factory OrderSummary.fromJson(Map<String, dynamic> json) {
    final created = json['created_at'] as String?;
    final rawItems = (json['items'] as List<dynamic>?) ?? const [];
    return OrderSummary(
      id: (json['id'] as String?) ?? '',
      total: (json['total'] as String?) ?? '',
      status: _statusFromJson(json['status'] as String?),
      createdAt: (created == null || created.isEmpty)
          ? null
          : DateTime.tryParse(created),
      items: rawItems
          .map((e) => OrderItemSummary.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  bool get isDelivered => status == OrderSummaryStatus.delivered;

  /// Pedido que saiu do fluxo: entregue OU cancelado.
  ///
  /// `isDelivered` sozinho não serve para dividir "ativos" de "concluídos":
  /// um pedido cancelado não está entregue, mas também não está em curso.
  bool get isFinished =>
      status == OrderSummaryStatus.delivered ||
      status == OrderSummaryStatus.cancelled;

  /// Soma das quantidades de todos os itens do pedido.
  int get totalQuantity => items.fold(0, (sum, item) => sum + item.quantity);

  /// Índice no stepper de 3 etapas da UI (Separação / Trânsito / Entregue).
  int get stepIndex {
    switch (status) {
      case OrderSummaryStatus.pending:
      case OrderSummaryStatus.confirmed:
      case OrderSummaryStatus.separating:
        return 0;
      case OrderSummaryStatus.outForDelivery:
        return 1;
      case OrderSummaryStatus.delivered:
      // Um pedido cancelado não está no stepper. Devolve o último índice
      // para o widget não renderizar barra de progresso pela metade; quem
      // tira um pedido cancelado do caminho do stepper é
      // `OrdersProvider.activeOrders` (orders_provider.dart), que filtra por
      // `isFinished` antes de a tela receber a lista — a tela em si nunca lê
      // `isFinished` (medido: `grep -rn "isDelivered\|isFinished\|isCancelled"
      // front-end-flutter/lib/`, rodada de correção 1, Minor 3).
      case OrderSummaryStatus.cancelled:
        return 2;
    }
  }

  /// Rótulo legível do status atual, exibido no card de pedido ativo.
  String get statusLabel {
    switch (status) {
      case OrderSummaryStatus.pending:
        return 'Pendente';
      case OrderSummaryStatus.confirmed:
        return 'Confirmado';
      case OrderSummaryStatus.separating:
        return 'Em separação';
      case OrderSummaryStatus.outForDelivery:
        return 'Saiu para entrega';
      case OrderSummaryStatus.delivered:
        return 'Entregue';
      case OrderSummaryStatus.cancelled:
        return 'Cancelado';
    }
  }
}

const _months = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

/// Formata o total (string decimal do backend, ex.: "1234.50") como moeda
/// brasileira: `R$ 1.234,50`. Mantém o valor cru caso não seja numérico.
String formatOrderTotal(String total) {
  final value = double.tryParse(total);
  if (value == null) return 'R\$ $total';

  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  final intPart = parts[0];
  final decPart = parts[1];

  final buffer = StringBuffer();
  for (var i = 0; i < intPart.length; i++) {
    if (i > 0 && (intPart.length - i) % 3 == 0) buffer.write('.');
    buffer.write(intPart[i]);
  }
  return 'R\$ $buffer,$decPart';
}

/// Formata a data como `dd de <mês>, yyyy` (ex.: "22 de abril, 2026") no fuso
/// local. Retorna string vazia quando não há data.
String formatOrderDate(DateTime? date) {
  if (date == null) return '';
  final local = date.toLocal();
  return '${local.day} de ${_months[local.month - 1]}, ${local.year}';
}
