import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/logistics/data/logistics_api.dart';
import 'package:edu_ia/features/logistics/domain/order.dart';
import 'package:edu_ia/features/logistics/presentation/tracking_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// `POST /occurrences/delivery-delay` é `requer_papel("entregador", "admin")`
/// no commerce-service, e `requer_papel` recusa `role="carregamento"` de
/// saída. Uma sessão aberta por código de carregamento — hoje a porta de
/// entrada normal do entregador — recebia o botão "Reportar atraso" mesmo
/// assim, e o servidor respondia 403. Esconder a ação é o conserto do lado
/// certo: alargar o token daria ao lote uma capacidade que ele não deve ter.
String _tokenComRole(String role) {
  String seg(Map<String, dynamic> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  return '${seg({'alg': 'HS256'})}.${seg({'role': role, 'sub': '1'})}.assinatura';
}

class _FakeTokenStore extends TokenStore {
  _FakeTokenStore(this._token);

  final String? _token;

  @override
  Future<String?> readAccessToken() async => _token;
}

class _ApiComUmaEntrega extends LogisticsApi {
  @override
  Future<List<Pedido>> fetchMinhasEntregas() async => [
    Pedido(
      id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
      userId: 'u1',
      status: StatusPedido.emTransito,
      enderecoEntrega: 'Rua das Flores, 42 - Centro',
      total: '100.00',
      createdAt: DateTime(2026, 9, 9),
    ),
  ];
}

Future<void> _montar(WidgetTester tester, String role) async {
  await tester.pumpWidget(
    MaterialApp(
      home: EntregadorEmRotaScreen(
        api: _ApiComUmaEntrega(),
        tokenStore: _FakeTokenStore(_tokenComRole(role)),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  testWidgets('a sessão de lote não recebe a ação de reportar atraso', (tester) async {
    await _montar(tester, 'carregamento');

    expect(find.text('Entregue'), findsOneWidget);
    expect(find.text('Reportar atraso'), findsNothing);
  });

  testWidgets('a conta de entregador continua recebendo a ação', (tester) async {
    await _montar(tester, 'entregador');

    expect(find.text('Entregue'), findsOneWidget);
    expect(find.text('Reportar atraso'), findsOneWidget);
  });
}
