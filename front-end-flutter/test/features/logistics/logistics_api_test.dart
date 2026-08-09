import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/logistics/data/logistics_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _pedidoId = '3fa85f64-5717-4562-b3fc-2c963f66afa6';
const _produtoId = 'd4e3c960-3333-4562-b3fc-2c963f66afa9';

Map<String, dynamic> _pedidoJson({String status = 'AGUARDANDO_SEPARACAO'}) => {
  'id': _pedidoId,
  'user_id': 'b2c1a940-1234-4562-b3fc-2c963f66afa7',
  'status': status,
  'total': '242.00',
  'endereco_entrega': 'Rua das Flores, 123 - Centro',
  'carrier_name': null,
  'estimated_delivery_at': null,
  'created_at': '2026-08-09T09:30:00Z',
  'picker_id': null,
  'deliverer_id': null,
};

Map<String, dynamic> _ocorrenciaJson() => {
  'id': 42,
  'pedido_id': _pedidoId,
  'tipo': 'FALTA_ESTOQUE',
  'status': 'ABERTA',
  'produto_id': _produtoId,
  'nova_data_sugerida': null,
  'motivo': 'Sem estoque disponível',
  'resolucao': null,
  'criado_em': '2026-08-09T10:00:00Z',
  'resolvido_em': null,
};

void main() {
  group('LogisticsApi', () {
    test('fetchFilaSeparacao parses the queue and sends the bearer token', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(jsonEncode([_pedidoJson()]), 200);
      });
      final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

      final fila = await api.fetchFilaSeparacao();

      expect(fila, hasLength(1));
      expect(fila.first.id, _pedidoId);
      expect(captured.method, 'GET');
      expect(captured.url.path, endsWith('/picking/queue'));
      expect(captured.headers['Authorization'], 'Bearer fake-token');
    });

    test('iniciarSeparacao builds the path with the raw UUID pedidoId '
        '(no int.parse, no toString() over a number)', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(jsonEncode(_pedidoJson(status: 'EM_SEPARACAO')), 200);
      });
      final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

      await api.iniciarSeparacao(_pedidoId);

      expect(captured.method, 'PATCH');
      expect(captured.url.path, endsWith('/picking/$_pedidoId/start'));
    });

    test('reportarFaltaEstoque sends pedido_id and produto_id as strings in '
        'the request body', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(jsonEncode(_ocorrenciaJson()), 201);
      });
      final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

      await api.reportarFaltaEstoque(
        pedidoId: _pedidoId,
        produtoId: _produtoId,
        motivo: 'Sem estoque disponível',
      );

      expect(captured.url.path, endsWith('/occurrences/stock-shortage'));
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['pedido_id'], isA<String>());
      expect(body['pedido_id'], _pedidoId);
      expect(body['produto_id'], isA<String>());
      expect(body['produto_id'], _produtoId);
    });

    test('fetchOcorrenciasPedido builds the path with the raw UUID pedidoId, '
        'without converting it', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(jsonEncode([_ocorrenciaJson()]), 200);
      });
      final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

      final ocorrencias = await api.fetchOcorrenciasPedido(_pedidoId, apenasAbertas: true);

      expect(ocorrencias, hasLength(1));
      expect(
        captured.url.path + (captured.url.query.isEmpty ? '' : '?${captured.url.query}'),
        endsWith('/occurrences/order/$_pedidoId?apenas_abertas=true'),
      );
    });

    test('resolverOcorrencia sends produto_escolhido_id as a string and '
        'keeps ocorrenciaId as an int in the path', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response('', 200);
      });
      final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

      await api.resolverOcorrencia(
        ocorrenciaId: 42,
        resolucao: 'substituir',
        produtoEscolhidoId: _produtoId,
      );

      expect(captured.url.path, endsWith('/occurrences/42/resolve'));
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['produto_escolhido_id'], isA<String>());
      expect(body['produto_escolhido_id'], _produtoId);
    });
  });
}
