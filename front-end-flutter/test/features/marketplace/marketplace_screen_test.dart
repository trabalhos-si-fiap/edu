import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/cart/domain/cart_item.dart';
import 'package:edu_ia/features/marketplace/data/partner_service.dart';
import 'package:edu_ia/features/marketplace/data/product_service.dart';
import 'package:edu_ia/features/marketplace/domain/partner.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/marketplace_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/partners_provider.dart';
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

// Sem parceiros ativos nesta suíte: MarketplaceView monta os dois providers
// (task 12), mas o que este teste verifica é o catálogo próprio.
class _EmptyPartnerService extends PartnerService {
  @override
  Future<List<Partner>> fetchActivePartners() async => const [];
}

class _EmptyCartService extends CartService {
  @override
  Future<List<CartItem>> fetch() async => <CartItem>[];
}

Widget _harness(ProductsProvider provider, PartnersProvider partnersProvider) =>
    MultiProvider(
      providers: [
        ChangeNotifierProvider<CartStore>(
          create: (_) => CartStore(service: _EmptyCartService()),
        ),
        ChangeNotifierProvider<ProductsProvider>.value(value: provider),
        ChangeNotifierProvider<PartnersProvider>.value(value: partnersProvider),
      ],
      child: const MaterialApp(home: MarketplaceView()),
    );

void main() {
  testWidgets('renders products from the provider', (tester) async {
    final provider = ProductsProvider(service: _FakeService());
    await provider.load();
    final partnersProvider = PartnersProvider(service: _EmptyPartnerService());
    await partnersProvider.load();

    await tester.pumpWidget(_harness(provider, partnersProvider));
    await tester.pump();

    expect(find.text('Guia de Redação'), findsOneWidget);
  });
}
