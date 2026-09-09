import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _produto = Product(
  id: 'a',
  name: 'Luminária',
  type: 'iluminacao',
  subtype: '',
  description: '',
  price: 129.90,
);

Widget _harness(CartStore cartStore) => ChangeNotifierProvider<CartStore>.value(
      value: cartStore,
      child: MaterialApp(
        home: Scaffold(
          // Largura fixa: sem isso o card ocupa a tela inteira e a imagem
          // (aspect ratio 1) estoura a altura disponível — mesmo motivo pelo
          // qual partners_section.dart embrulha ProductCard num SizedBox.
          body: SizedBox(
            width: 200,
            height: 460,
            child: ProductCard(product: _produto),
          ),
        ),
      ),
    );

void main() {
  testWidgets(
    'a mixed-origin 409 on add-to-cart shows the exact backend sentence',
    (tester) async {
      // A frase é a do servidor, não uma cópia no Dart: o teste a extrai do
      // corpo mockado do 409, igual a cart_service_conflict_test.dart.
      const mensagem =
          'Seu carrinho já tem itens de outro parceiro. '
          'Finalize ou esvazie o carrinho antes de misturar.';
      final client = MockClient((req) async {
        if (req.method == 'POST') {
          return http.Response(
            jsonEncode({'detail': mensagem}),
            409,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }
        return http.Response(jsonEncode({'items': []}), 200);
      });
      final cartStore = CartStore(
        service: CartService(client: client, tokenStore: _FakeTokenStore()),
      );

      await tester.pumpWidget(_harness(cartStore));
      await tester.tap(find.text('+ Carrinho'));
      await tester.pumpAndSettle();

      expect(find.text(mensagem), findsOneWidget);

      // AddToCartButton schedules its own Future.delayed(1200ms) to flip
      // back to the idle label, uncancelled on dispose — advance the fake
      // clock past it so no timer is left pending when the test ends.
      await tester.pump(const Duration(milliseconds: 1300));
    },
  );
}
