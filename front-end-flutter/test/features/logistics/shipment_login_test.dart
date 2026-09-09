import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/auth/presentation/login_screen.dart';
import 'package:edu_ia/features/logistics/data/logistics_api.dart';
import 'package:edu_ia/features/logistics/presentation/shipment_login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Fake sem persistência real — só captura o que `entrarNoCarregamento`
/// gravaria no `FlutterSecureStorage`, para o teste inspecionar sem tocar
/// em plugin de plataforma nenhum.
class _FakeTokenStore extends TokenStore {
  String? access;
  String? refresh;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    access = accessToken;
    refresh = refreshToken;
  }
}

void main() {
  test('entra com código e guarda o token', () async {
    final client = MockClient((req) async {
      expect(req.url.path, endsWith('/shipments/login'));
      expect(req.headers['Authorization'], isNull);
      expect(jsonDecode(req.body)['codigo'], 'ABCD2345');
      return http.Response(
        jsonEncode({
          'access_token': 'tok',
          'token_type': 'bearer',
          'carregamento_id': 12,
          'codigo': 'ABCD2345',
          'origem_rotulo': 'Cajamar, SP',
        }),
        200,
      );
    });
    final store = _FakeTokenStore();
    final api = LogisticsApi(client: client, tokenStore: store);

    final sessao = await api.entrarNoCarregamento(
      codigo: 'ABCD2345',
      senha: 'SEGREDO12345',
      nome: 'Maria',
      contato: '11999990000',
    );

    expect(sessao.carregamentoId, 12);
    expect(store.access, 'tok');
  });

  test('credencial errada vira mensagem legível, não código HTTP', () async {
    final client = MockClient(
      (_) async =>
          http.Response(jsonEncode({'detail': 'Código ou senha inválidos'}), 401),
    );
    final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => api.entrarNoCarregamento(
        codigo: 'X',
        senha: 'Y',
        nome: 'Maria',
        contato: '11999990000',
      ),
      throwsA(
        isA<LogisticsException>()
            .having((e) => e.message, 'message', contains('inválidos')),
      ),
    );
  });

  testWidgets('a tela de login por código monta e valida os quatro campos',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ShipmentLoginScreen()));

    await tester.tap(find.text('Entrar'));
    await tester.pump();

    expect(find.text('Informe o código'), findsOneWidget);
    expect(find.text('Informe a senha'), findsOneWidget);
    expect(find.text('Informe seu nome'), findsOneWidget);
    expect(find.text('Informe um contato'), findsOneWidget);
  });

  testWidgets('a tela de login normal oferece o caminho do carregamento',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: const LoginScreen(),
      routes: {'/shipment-login': (_) => const ShipmentLoginScreen()},
    ));

    expect(find.text('Entrar com código de carregamento'), findsOneWidget);
  });
}
