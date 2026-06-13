import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/data/product_service.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/marketplace_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/products_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _FakeService extends ProductService {
  @override
  Future<List<Product>> fetchProducts({int limit = 100}) async => [
    const Product(
      id: 'a', name: 'Guia de Redação', type: 'apostila', subtype: 'Digital',
      description: 'd', price: 49.90, ratingAvg: 4.5, ratingCount: 10,
    ),
  ];
}

Widget _harness(ProductsProvider provider) => MultiProvider(
      providers: [
        ChangeNotifierProvider<CartStore>(create: (_) => CartStore()),
        ChangeNotifierProvider<ProductsProvider>.value(value: provider),
      ],
      child: const MaterialApp(home: MarketplaceView()),
    );

void main() {
  testWidgets('renders products from the provider', (tester) async {
    final provider = ProductsProvider(service: _FakeService());
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('Guia de Redação'), findsOneWidget);
  });
}
