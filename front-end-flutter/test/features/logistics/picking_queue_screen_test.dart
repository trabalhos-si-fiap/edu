import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/logistics/data/logistics_api.dart';
import 'package:edu_ia/features/logistics/presentation/picking_queue_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _emAndamentoId = 'aaaaaaaa-5717-4562-b3fc-2c963f66afa6';
const _aguardandoId = 'bbbbbbbb-5717-4562-b3fc-2c963f66afa6';

/// Payload literal de `PedidoFilaOut` — a fila nunca traz itens.
Map<String, dynamic> _pedidoFilaJson(String id, String status) => {
  'id': id,
  'user_id': 'b2c1a940-1234-4562-b3fc-2c963f66afa7',
  'status': status,
  'total': '242.00',
  'endereco_entrega': 'Rua das Flores, 123 - Centro',
  'carrier_name': null,
  'estimated_delivery_at': null,
  'created_at': '2026-08-09T09:30:00Z',
  'picker_id': status == 'EM_SEPARACAO' ? 'c3d2b850-2222-4562-b3fc-2c963f66afa8' : null,
  'deliverer_id': null,
  'score_risco': 0.4,
};

Finder _noCardDo(String titulo, Finder alvo) => find.descendant(
  of: find.ancestor(of: find.text(titulo), matching: find.byType(Card)),
  matching: alvo,
);

void main() {
  testWidgets('o pedido que o separador já começou aparece como "Em separação" '
      'e oferece continuar, não iniciar', (tester) async {
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode([
          _pedidoFilaJson(_emAndamentoId, 'EM_SEPARACAO'),
          _pedidoFilaJson(_aguardandoId, 'AGUARDANDO_SEPARACAO'),
        ]),
        200,
      ),
    );
    final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

    await tester.pumpWidget(MaterialApp(home: SeparadorFilaScreen(api: api)));
    await tester.pumpAndSettle();

    expect(_noCardDo('Pedido #AAAAAAAA', find.text('Em separação')), findsOneWidget);
    expect(_noCardDo('Pedido #AAAAAAAA', find.text('Continuar separação')), findsOneWidget);
    expect(_noCardDo('Pedido #AAAAAAAA', find.text('Iniciar separação')), findsNothing);

    expect(_noCardDo('Pedido #BBBBBBBB', find.text('Em separação')), findsNothing);
    expect(_noCardDo('Pedido #BBBBBBBB', find.text('Iniciar separação')), findsOneWidget);
  });
}
