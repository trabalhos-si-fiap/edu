import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/logistics/data/logistics_api.dart';
import 'package:edu_ia/features/marketplace/presentation/incident_resolution_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

/// Backend falso: `GET /occurrences/7` devolve uma falta de estoque aberta
/// com dois similares, os preços como o commerce-service manda (número).
LogisticsApi _api() {
  final client = MockClient((req) async {
    if (req.method == 'GET' && req.url.path.endsWith('/occurrences/7')) {
      return http.Response(
        jsonEncode({
          'id': 7,
          'pedido_id': '01a09d8b-cab4-7553-8616-25b78a60e63a',
          'tipo': 'FALTA_ESTOQUE',
          'status': 'ABERTA',
          'produto_id': 'p-original',
          'nova_data_sugerida': null,
          'motivo': 'Sem unidades na prateleira.',
          'resolucao': null,
          'criado_em': '2026-09-13T22:30:00Z',
          'produto_original': {'id': 'p-original', 'nome': 'Cadeira', 'preco': 1299.5},
          'produtos_sugeridos': [
            {'id': 'p-1', 'nome': 'Luminária de mesa', 'preco': 279.9},
            {'id': 'p-2', 'nome': 'Cadeira ergonômica', 'preco': 749},
          ],
        }),
        200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    }
    return http.Response('{"detail": "inesperado"}', 500);
  });
  return LogisticsApi(client: client, tokenStore: _FakeTokenStore());
}

void main() {
  testWidgets('os preços dos similares saem no formato brasileiro', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: OcorrenciaResolucaoScreen(ocorrenciaId: 7, api: _api())),
    );
    await tester.pumpAndSettle();

    expect(find.text(r'R$ 279,90'), findsOneWidget);
    expect(find.text(r'R$ 749,00'), findsOneWidget);
    expect(find.text(r'R$ 279.90'), findsNothing);
  });
}
