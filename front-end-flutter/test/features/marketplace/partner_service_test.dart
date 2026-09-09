import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/partner_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

void main() {
  test('fetchActivePartners asks the backend which partners are active',
      () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 2,
              'nome': 'Leroy Merlin',
              'ativo': true,
              'origem_rotulo': 'Cajamar, SP',
            },
          ],
          'total': 1,
          'limit': 20,
          'offset': 0,
        }),
        200,
      );
    });

    final partners = await PartnerService(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchActivePartners();

    expect(partners, hasLength(1));
    expect(partners.first.id, 2);
    expect(partners.first.name, 'Leroy Merlin');
    expect(partners.first.originLabel, 'Cajamar, SP');
    // O app NÃO sabe que a resposta é a Leroy. Ele pergunta quem está ativo.
    expect(captured.url.queryParameters['active'], 'true');
    expect(captured.url.path, endsWith('/partners'));
  });

  test('fetchPartnerProducts filters the catalog by partner id', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {'id': 'a', 'name': 'Luminária', 'type': 'iluminacao', 'price': '129.90'},
          ],
          'total': 1,
          'limit': 50,
          'offset': 0,
        }),
        200,
      );
    });

    final produtos = await PartnerService(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchPartnerProducts(2);

    expect(produtos, hasLength(1));
    expect(produtos.first.name, 'Luminária');
    expect(captured.url.queryParameters['partner_id'], '2');
  });

  test('a non-200 becomes a PartnerException with a readable message',
      () async {
    final client = MockClient((_) async => http.Response('{}', 500));
    expect(
      () => PartnerService(client: client, tokenStore: _FakeTokenStore())
          .fetchActivePartners(),
      throwsA(isA<PartnerException>()),
    );
  });
}
