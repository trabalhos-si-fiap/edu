import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _resumoJson = {
  'objetivo': null,
  'roadmap': {'etapas_totais': 0, 'etapas_concluidas': 0, 'progresso': 0.0},
  'pontos': {'total': 0, 'nivel': 1, 'streak': 0},
  'estudo': {'questoes_respondidas': 0, 'subtemas_iniciados': 0},
};

void main() {
  test('fetchSummary chama /profile/summary com o token', () async {
    late http.Request capturada;
    final client = MockClient((req) async {
      capturada = req;
      return http.Response(jsonEncode(_resumoJson), 200);
    });

    final resumo = await TrackerApi(client: client, tokenStore: _FakeTokenStore()).fetchSummary();

    expect(capturada.url.path, endsWith('/profile/summary'));
    expect(capturada.headers['Authorization'], 'Bearer fake-token');
    expect(resumo.points.total, 0);
  });

  test('fetchRoadmap pagina pela query', () async {
    late http.Request capturada;
    final client = MockClient((req) async {
      capturada = req;
      return http.Response(
        jsonEncode({
          'objetivo': null,
          'motivo': null,
          'prazo_apertado': false,
          'items': [],
          'total': 0,
          'limit': 20,
          'offset': 40,
        }),
        200,
      );
    });

    await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchRoadmap(limit: 20, offset: 40);

    expect(capturada.url.queryParameters['limit'], '20');
    expect(capturada.url.queryParameters['offset'], '40');
  });

  test('saveGoal manda POST na criação e PUT na edição', () async {
    final metodos = <String>[];
    final client = MockClient((req) async {
      metodos.add(req.method);
      return http.Response(
        jsonEncode({
          'objetivo': {
            'titulo': 'Medicina',
            'data_alvo': '2027-11-07',
            'criado_em': '2026-09-10T10:00:00Z',
            'atualizado_em': '2026-09-10T10:00:00Z',
          },
          'etapas_geradas': 99,
          'prazo_apertado': false,
        }),
        req.method == 'POST' ? 201 : 200,
      );
    });

    final api = TrackerApi(client: client, tokenStore: _FakeTokenStore());
    await api.saveGoal(title: 'Medicina', targetDate: DateTime(2027, 11, 7), update: false);
    await api.saveGoal(title: 'Medicina', targetDate: DateTime(2027, 11, 7), update: true);

    expect(metodos, ['POST', 'PUT']);
  });

  test('saveGoal devolve as etapas geradas e o aviso de prazo apertado', () async {
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({
          'objetivo': {
            'titulo': 'Medicina',
            'data_alvo': '2026-11-08',
            'criado_em': '2026-09-10T10:00:00Z',
            'atualizado_em': '2026-09-10T10:00:00Z',
          },
          'etapas_geradas': 107,
          'prazo_apertado': true,
        }),
        201,
      ),
    );

    final salvo = await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).saveGoal(title: 'Medicina', targetDate: DateTime(2026, 11, 8), update: false);

    expect(salvo.steps, 107);
    expect(salvo.tightDeadline, isTrue);
  });

  test('data vai como AAAA-MM-DD, não como ISO com hora', () async {
    late http.Request capturada;
    final client = MockClient((req) async {
      capturada = req;
      return http.Response(
        jsonEncode({
          'objetivo': {
            'titulo': 'Medicina',
            'data_alvo': '2027-11-07',
            'criado_em': '2026-09-10T10:00:00Z',
            'atualizado_em': '2026-09-10T10:00:00Z',
          },
          'etapas_geradas': 1,
          'prazo_apertado': false,
        }),
        201,
      );
    });

    await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).saveGoal(title: 'Medicina', targetDate: DateTime(2027, 11, 7), update: false);

    expect(jsonDecode(capturada.body)['data_alvo'], '2027-11-07');
  });

  test('a mensagem do servidor é a que chega na tela', () async {
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({
          'detail': [
            {'msg': 'Value error, A data-alvo não pode estar no passado'},
          ],
        }),
        422,
      ),
    );

    expect(
      () => TrackerApi(
        client: client,
        tokenStore: _FakeTokenStore(),
      ).saveGoal(title: 'Medicina', targetDate: DateTime(2020, 1, 1), update: false),
      throwsA(
        isA<TrackerException>().having(
          (e) => e.message,
          'message',
          contains('não pode estar no passado'),
        ),
      ),
    );
  });

  test('fetchGoal devolve null quando o aluno pulou o onboarding', () async {
    final client = MockClient((_) async => http.Response('null', 200));
    final objetivo = await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchGoal();
    expect(objetivo, isNull);
  });

  test('sem sessão, a chamada falha com mensagem de sessão expirada', () async {
    final client = MockClient((_) async => http.Response('{}', 200));
    expect(
      () => TrackerApi(client: client, tokenStore: _SemToken()).fetchSummary(),
      throwsA(isA<TrackerException>()),
    );
  });
}

class _SemToken extends TokenStore {
  @override
  Future<String?> readAccessToken() async => null;
}
