import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/order_tracking/data/route_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _body = {
  'origin': {'label': 'Centro de Distribuição', 'latitude': -23.3, 'longitude': -46.8},
  'destination': {'label': 'Endereço de entrega', 'latitude': -23.5, 'longitude': -46.6},
  'polyline': 'enc',
  'distance_text': '32 km',
  'distance_km': 32.0,
  'duration_text': '48 min',
  'duration_minutes': 48,
};

void main() {
  test('fetchRoute parses a 200 response and sends the bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_body), 200);
    });

    final service = RouteService(client: client, tokenStore: _FakeTokenStore());
    final route = await service.fetchRoute('ED-99420');

    expect(route.polyline, 'enc');
    expect(route.origin.label, 'Centro de Distribuição');
    expect(captured.headers['Authorization'], 'Bearer fake-token');
    expect(captured.url.path, endsWith('/orders/ED-99420/route'));
  });

  test('fetchRoute throws RouteException on non-200', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service = RouteService(client: client, tokenStore: _FakeTokenStore());

    expect(() => service.fetchRoute('ED-99420'), throwsA(isA<RouteException>()));
  });
}
