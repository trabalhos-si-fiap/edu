import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/logistics/data/logistics_api.dart';
import 'package:edu_ia/features/logistics/domain/order.dart';
import 'package:edu_ia/features/logistics/presentation/picking_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _pedidoId = '3fa85f64-5717-4562-b3fc-2c963f66afa6';

Map<String, dynamic> _pedidoJson(String status, {List<Map<String, dynamic>>? items}) => {
  'id': _pedidoId,
  'user_id': 'b2c1a940-1234-4562-b3fc-2c963f66afa7',
  'status': status,
  'total': '242.00',
  'endereco_entrega': 'Rua das Flores, 123 - Centro',
  'carrier_name': null,
  'estimated_delivery_at': null,
  'created_at': '2026-08-09T09:30:00Z',
  'picker_id': 'c3d2b850-2222-4562-b3fc-2c963f66afa8',
  'deliverer_id': null,
  'items': ?items,
};

Map<String, dynamic> _itemJson(String nome, int quantidade) => {
  'product_id': 'd4e3c960-3333-4562-b3fc-2c963f66af${quantidade}0',
  'product_name': nome,
  'unit_price': '24.90',
  'quantity': quantidade,
};

/// Backend falso: `GET /picking/{id}` devolve o pedido com [itensAtuais], as
/// ocorrências abertas vêm vazias e `finish` devolve AGUARDANDO_COLETA. Toda
/// requisição fica registrada em [chamadas] como `MÉTODO /caminho`.
LogisticsApi _api(
  List<String> chamadas, {
  required String statusAtual,
  required List<Map<String, dynamic>> itensAtuais,
}) {
  final client = MockClient((req) async {
    chamadas.add('${req.method} ${req.url.path}');
    final path = req.url.path;
    if (req.method == 'GET' && path.endsWith('/picking/$_pedidoId')) {
      return http.Response(jsonEncode(_pedidoJson(statusAtual, items: itensAtuais)), 200);
    }
    if (req.method == 'GET' && path.endsWith('/occurrences/order/$_pedidoId')) {
      return http.Response('[]', 200);
    }
    if (req.method == 'PATCH' && path.endsWith('/picking/$_pedidoId/finish')) {
      return http.Response(jsonEncode(_pedidoJson('AGUARDANDO_COLETA')), 200);
    }
    return http.Response('{"detail": "inesperado"}', 500);
  });
  return LogisticsApi(client: client, tokenStore: _FakeTokenStore());
}

/// Abre a tela por cima de uma rota inicial, como a fila faz — `finish`
/// devolve com `Navigator.pop`, e a rota inicial é o que sobra na pilha.
Future<void> _abrir(WidgetTester tester, Pedido daFila, LogisticsApi api) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => TextButton(
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => SeparadorPickingScreen(pedido: daFila, api: api),
            ),
          ),
          child: const Text('fila'),
        ),
      ),
    ),
  );
  await tester.tap(find.text('fila'));
  await tester.pumpAndSettle();
}

ElevatedButton _botaoPrincipal(WidgetTester tester) =>
    tester.widget<ElevatedButton>(find.byType(ElevatedButton));

void main() {
  testWidgets('retomar um pedido em separação confere os itens de agora e '
      'finaliza sem chamar /start de novo', (tester) async {
    final chamadas = <String>[];
    // O que a fila entregou: EM_SEPARACAO, sem itens (a fila nunca traz).
    final daFila = Pedido.fromJson(_pedidoJson('EM_SEPARACAO'));
    // O que o servidor tem hoje, depois da substituição.
    final api = _api(
      chamadas,
      statusAtual: 'EM_SEPARACAO',
      itensAtuais: [_itemJson('Caderno substituto', 1), _itemJson('Apostila', 2)],
    );

    await _abrir(tester, daFila, api);

    expect(
      chamadas.where((c) => c.startsWith('GET') && c.endsWith('/picking/$_pedidoId')),
      hasLength(1),
    );
    expect(find.text('Caderno substituto'), findsOneWidget);
    expect(find.text('Apostila'), findsOneWidget);
    expect(find.text('Iniciar Separação'), findsNothing);
    expect(find.text('Finalizar Separação'), findsOneWidget);
    expect(_botaoPrincipal(tester).onPressed, isNull);

    for (final checkbox in find.byType(Checkbox).evaluate().toList()) {
      await tester.tap(find.byWidget(checkbox.widget));
    }
    await tester.pump();
    expect(_botaoPrincipal(tester).onPressed, isNotNull);

    await tester.tap(find.text('Finalizar Separação'));
    await tester.pumpAndSettle();

    expect(chamadas.where((c) => c.startsWith('PATCH')), [
      endsWith('/picking/$_pedidoId/finish'),
    ]);
    expect(find.text('fila'), findsOneWidget);
  });

  testWidgets('sem item restante (o aluno removeu o único), a separação '
      'retomada ainda pode ser finalizada', (tester) async {
    final chamadas = <String>[];
    final api = _api(chamadas, statusAtual: 'EM_SEPARACAO', itensAtuais: []);

    await _abrir(tester, Pedido.fromJson(_pedidoJson('EM_SEPARACAO')), api);

    expect(find.text('Nenhum item restante neste pedido.'), findsOneWidget);
    expect(_botaoPrincipal(tester).onPressed, isNotNull);
  });

  testWidgets('se o pedido não carregar, a tela não deixa finalizar às cegas', (
    tester,
  ) async {
    final client = MockClient(
      (_) async => http.Response('{"detail": "Sem permissão para ver este pedido"}', 403),
    );
    final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

    await _abrir(tester, Pedido.fromJson(_pedidoJson('EM_SEPARACAO')), api);

    expect(find.text('Sem permissão para ver este pedido'), findsOneWidget);
    expect(_botaoPrincipal(tester).onPressed, isNull);
  });
}
