import 'dart:async';

import 'package:edu_ia/features/marketplace/data/product_service.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/product_detail_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeReviews extends ProductService {
  _FakeReviews(this.handler);

  final Future<List<Review>> Function() handler;

  @override
  Future<List<Review>> fetchReviews(String productId) => handler();
}

Product _product() => const Product(
      id: 'p1',
      name: 'Guia de Redação',
      type: 'apostila',
      subtype: 'Digital',
      description: 'Conteúdo de apoio',
      price: 49.90,
      ratingAvg: 4.5,
      ratingCount: 3,
    );

Widget _harness(ProductService service) => MaterialApp(
      home: ProductDetailView(product: _product(), service: service),
    );

void main() {
  testWidgets('shows the loading state while reviews are pending',
      (tester) async {
    final pending = Completer<List<Review>>();
    await tester.pumpWidget(_harness(_FakeReviews(() => pending.future)));
    await tester.pump();

    expect(find.text('Carregando avaliações...'), findsOneWidget);
  });

  testWidgets('shows the error state when fetching reviews fails',
      (tester) async {
    await tester.pumpWidget(
      _harness(_FakeReviews(() => Future.error(ProductException('boom')))),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('Não foi possível carregar as avaliações.'),
      findsOneWidget,
    );
  });

  testWidgets('shows the empty state when there are no reviews',
      (tester) async {
    await tester.pumpWidget(
      _harness(_FakeReviews(() async => <Review>[])),
    );
    await tester.pumpAndSettle();

    expect(find.text('Ainda não há avaliações.'), findsOneWidget);
  });

  testWidgets('renders a ReviewItem per review in the list state',
      (tester) async {
    await tester.pumpWidget(
      _harness(_FakeReviews(() async => const [
            Review(
              id: 'r1',
              author: 'Ana',
              rating: 5,
              comment: 'Excelente material',
              createdAt: '2026-06-01',
            ),
          ])),
    );
    await tester.pumpAndSettle();

    expect(find.text('Ana'), findsOneWidget);
    expect(find.text('Excelente material'), findsOneWidget);
  });

  testWidgets(
      'a long name, no reviews and the price fit a 360dp-wide screen',
      (tester) async {
    // Largura de um Android comum (1080px a 3x). Antes, estrelas + "Sem
    // avaliações" + preço dividiam uma Row só e o preço estourava a borda.
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        home: ProductDetailView(
          product: const Product(
            id: 'p2',
            name: 'Mesa de estudo 120 cm com gaveteiro e suporte para monitor',
            type: 'mobiliario',
            subtype: '',
            description: '',
            price: 12399.90,
          ),
          service: _FakeReviews(() async => <Review>[]),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('Sem avaliações'), findsOneWidget);
    expect(find.text(r'R$ 12.399,90'), findsOneWidget);
  });
}
