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

/// Tipos chegam do backend como código sem acento; os subtypes já vêm em
/// português e ocupam o card, então o chip é o único lugar do código cru.
class _CatalogoComTiposService extends ProductService {
  @override
  Future<List<Product>> fetchProducts({int limit = 100}) async => [
    const Product(
      id: 'm', name: 'Mesa Dobrável', type: 'mobiliario', subtype: 'Mesa',
      description: 'd', price: 199.90,
    ),
    const Product(
      id: 'l', name: 'Luminária LED', type: 'iluminacao',
      subtype: 'Luminária', description: 'd', price: 89.90,
    ),
  ];
}

// Sem parceiros ativos nesta suíte: MarketplaceView monta os dois providers
// (task 12), mas o que este teste verifica é o catálogo próprio.
class _EmptyPartnerService extends PartnerService {
  @override
  Future<List<Partner>> fetchActivePartners() async => const [];
}

/// Um parceiro ativo com catálogo próprio — o que a narração da demonstração
/// destaca ("produtos da própria Leroy Merlin em parceria").
class _LeroyPartnerService extends PartnerService {
  @override
  Future<List<Partner>> fetchActivePartners() async => const [
    Partner(
      id: 2, name: 'Leroy Merlin', active: true, originLabel: 'Cajamar, SP',
    ),
  ];

  @override
  Future<List<Product>> fetchPartnerProducts(int partnerId) async => const [
    Product(
      id: 'p1', name: 'Luminária de mesa', type: 'iluminacao',
      subtype: 'Luminária', description: '', price: 129.90,
    ),
  ];
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

  testWidgets(
    'os chips de categoria mostram o rótulo pt-BR, não o código do tipo',
    (tester) async {
      final provider = ProductsProvider(service: _CatalogoComTiposService());
      await provider.load();
      final partnersProvider = PartnersProvider(
        service: _EmptyPartnerService(),
      );
      await partnersProvider.load();

      await tester.pumpWidget(_harness(provider, partnersProvider));
      await tester.pump();

      expect(find.text('MOBILIÁRIO'), findsOneWidget);
      expect(find.text('ILUMINAÇÃO'), findsOneWidget);
      expect(find.text('MOBILIARIO'), findsNothing);
      expect(find.text('ILUMINACAO'), findsNothing);
    },
  );

  group('seção Parceiros', () {
    Future<void> montar(WidgetTester tester) async {
      // Tela alta o bastante para a grade inteira ser construída: o que se
      // compara é a ordem, não o que cabe na primeira dobra.
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final provider = ProductsProvider(service: _FakeService());
      await provider.load();
      final partnersProvider = PartnersProvider(
        service: _LeroyPartnerService(),
      );
      await partnersProvider.load();

      await tester.pumpWidget(_harness(provider, partnersProvider));
      await tester.pump();
    }

    double topo(WidgetTester tester, String texto) =>
        tester.getTopLeft(find.text(texto)).dy;

    testWidgets('vem logo abaixo do título, antes da grade de produtos', (
      tester,
    ) async {
      await montar(tester);

      expect(find.text('Leroy Merlin'), findsOneWidget);
      expect(topo(tester, 'EduMarketplace'), lessThan(topo(tester, 'Parceiros')));
      expect(topo(tester, 'Parceiros'), lessThan(topo(tester, 'Guia de Redação')));
      expect(
        topo(tester, 'Luminária de mesa'),
        lessThan(topo(tester, 'Guia de Redação')),
      );
    });

    testWidgets('some com uma categoria selecionada e volta em "Tudo"', (
      tester,
    ) async {
      await montar(tester);

      await tester.tap(find.text('APOSTILAS'));
      await tester.pump();
      expect(find.text('Parceiros'), findsNothing);
      expect(find.text('Guia de Redação'), findsOneWidget);

      await tester.tap(find.text('Tudo'));
      await tester.pump();
      expect(find.text('Parceiros'), findsOneWidget);
    });

    testWidgets('some com uma busca ativa', (tester) async {
      await montar(tester);

      await tester.enterText(find.byType(TextField), 'redação');
      await tester.pump();
      expect(find.text('Parceiros'), findsNothing);
      expect(find.text('Guia de Redação'), findsOneWidget);

      await tester.enterText(find.byType(TextField), '');
      await tester.pump();
      expect(find.text('Parceiros'), findsOneWidget);
    });
  });
}
