import 'package:edu_ia/features/order_tracking/domain/order_model.dart';
import 'package:edu_ia/features/order_tracking/presentation/order_tracking_screen.dart';
import 'package:edu_ia/features/order_tracking/presentation/widgets/order_format.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

final _confirmadoEm = DateTime.utc(2026, 9, 14, 1, 20);
final _saiuEm = DateTime.utc(2026, 9, 14, 1, 32);

/// O que o commerce-service manda (rastreio_builder.py) para um pedido que
/// saiu para entrega: o passo "Entregue" ainda pendente, mas COM horário —
/// o builder carimba `status_updated_at` em `delivered` qualquer que seja o
/// estado do passo.
final _saiuDaEntregaUtc = OrderModel(
  id: '01a09d8b-cab4-7553-8616-25b78a60e63a',
  headline: 'Saiu para entrega',
  description: 'Seu pedido está a caminho do seu endereço.',
  estimatedArrival: DateTime.utc(2026, 9, 17, 22, 30),
  steps: [
    TrackingStep(
      code: 'confirmed',
      title: 'Confirmado',
      status: OrderStepStatus.done,
      timestamp: _confirmadoEm,
    ),
    const TrackingStep(
      code: 'separating',
      title: 'Em separação',
      status: OrderStepStatus.done,
    ),
    TrackingStep(
      code: 'out_for_delivery',
      title: 'Saiu para entrega',
      status: OrderStepStatus.current,
      timestamp: _saiuEm,
    ),
    TrackingStep(
      code: 'delivered',
      title: 'Entregue',
      status: OrderStepStatus.pending,
      timestamp: DateTime.utc(2026, 9, 14, 1, 39),
    ),
  ],
  location: const TrackingLocation(
    name: 'Em rota de entrega',
    city: 'São Paulo',
    state: 'SP',
  ),
  kit: const [KitItem(name: 'Mesa de estudo 120 cm')],
  carrier: 'Frota própria',
  status: 'out_for_delivery',
);

Future<void> _pump(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: OrderTrackingContent(order: _saiuDaEntregaUtc)),
    ),
  );
}

void main() {
  testWidgets('o cabeçalho mostra o id curto, como o resto do app', (tester) async {
    await _pump(tester);

    expect(find.text('PEDIDO #01A09D8B'), findsOneWidget);
    expect(find.textContaining('cab4-7553'), findsNothing);
  });
}
