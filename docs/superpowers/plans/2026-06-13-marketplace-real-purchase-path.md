# Marketplace Real Purchase Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a purchase placed in the Flutter app persist on the backend so it shows up in "Seus pedidos".

**Architecture:** The backend (products, cart, orders) is already built and seeded; the Flutter marketplace is fully mocked. We wire the catalog to the real `GET /products` API (switching product IDs from `int` to UUID `String`), keep the cart local for instant +/− UX, and at checkout push the local cart to the backend (`POST /cart/items`) and create the order (`POST /orders`). The backend `POST /orders` reads the backend cart, snapshots it into an order, and empties the cart.

**Tech Stack:** Flutter/Dart, `provider` for state, `http` for networking, `flutter_test` + `http/testing`'s `MockClient`. Backend is FastAPI (no changes required).

**Key backend contracts (already implemented):**
- `GET /products?q=&limit=&offset=` → `{ items: ProductOut[], total, limit, offset }`. `ProductOut`: `{ id: uuid, name, type, subtype, description, price: "49.90" (string), image_url, rating_avg: float, rating_count: int }`.
- `GET /products/{id}/reviews?limit=&offset=` → `{ items: ReviewOut[], total, rating_avg, rating_count }`. `ReviewOut`: `{ id: uuid, author, rating: int, comment, created_at: iso }`.
- `GET /cart` → `{ items: CartItemOut[], total }`.
- `POST /cart/items` body `{ product_id: uuid, quantity: int(1..999) }` → `CartOut` (201). **Increments** quantity if the product is already in the cart.
- `DELETE /cart/items/{product_id}` → `CartOut`.
- `POST /orders` body `{ payment_method: str }` → `OrderOut` (201). Reads the backend cart, creates the order, empties the cart. Raises 400 "Cart is empty" if empty.
- All endpoints require `Authorization: Bearer <token>` (see existing `OrderListService` for the pattern).

**Existing patterns to follow:**
- HTTP client: `lib/features/marketplace/data/order_list_service.dart` (TokenStore + http.Client, exception type, `_headers()`).
- Provider: `lib/features/marketplace/presentation/orders_provider.dart` (loading/success/error enum).
- Service test: `test/features/marketplace/order_list_service_test.dart` (MockClient + fake TokenStore).
- Provider test: `test/features/marketplace/orders_provider_test.dart` (fake service subclass).

**Out of scope (confirmed with product owner):** per-operation cart sync, backend changes, "Comprar novamente"/"Avaliar itens" wiring on the orders screen, cart persistence across app restarts.

**Run commands** (from `front-end-flutter/`):
- Single test: `flutter test test/features/marketplace/<file>.dart`
- Analyze: `flutter analyze lib/features/marketplace lib/features/cart test/features`

---

## Phase 1 — Real product catalog

### Task 1: Switch Product/Review domain to UUID + JSON parsing

**Files:**
- Modify: `lib/features/marketplace/domain/product.dart`
- Test: `test/features/marketplace/product_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/marketplace/product_test.dart`:

```dart
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Product.fromJson parses fields and string price', () {
    final p = Product.fromJson({
      'id': 'a1b2',
      'name': 'Guia',
      'type': 'apostila',
      'subtype': 'Digital',
      'description': 'desc',
      'price': '49.90',
      'image_url': 'http://img/1.png',
      'rating_avg': 4.5,
      'rating_count': 128,
    });

    expect(p.id, 'a1b2');
    expect(p.name, 'Guia');
    expect(p.price, 49.90);
    expect(p.imageUrl, 'http://img/1.png');
    expect(p.ratingAvg, 4.5);
    expect(p.ratingCount, 128);
    expect(p.categoryLabel, 'DIGITAL');
  });

  test('Product.fromJson tolerates missing optional fields', () {
    final p = Product.fromJson({
      'id': 'x', 'name': 'N', 'type': 'curso', 'price': '0.00',
    });
    expect(p.subtype, '');
    expect(p.ratingCount, 0);
    expect(p.categoryLabel, 'CURSO');
  });

  test('Review.fromJson parses fields', () {
    final r = Review.fromJson({
      'id': 'r1',
      'author': 'Ana',
      'rating': 5,
      'comment': 'Ótimo',
      'created_at': '2026-03-12T00:00:00Z',
    });
    expect(r.id, 'r1');
    expect(r.author, 'Ana');
    expect(r.rating, 5);
    expect(r.comment, 'Ótimo');
    expect(r.createdAt, '2026-03-12T00:00:00Z');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/marketplace/product_test.dart`
Expected: FAIL — `Product.fromJson` / `Review.fromJson` not defined; `id` type mismatch.

- [ ] **Step 3: Rewrite `lib/features/marketplace/domain/product.dart`**

```dart
/// Produto do marketplace. Espelha `ProductOut` do backend: `id` é UUID
/// (string), `price` chega como string decimal ("49.90").
class Product {
  final String id;
  final String name;
  final String type;
  final String subtype;
  final String description;
  final double price;
  final String imageUrl;
  final double ratingAvg;
  final int ratingCount;

  const Product({
    required this.id,
    required this.name,
    required this.type,
    required this.subtype,
    required this.description,
    required this.price,
    this.imageUrl = '',
    this.ratingAvg = 0.0,
    this.ratingCount = 0,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      id: (json['id'] as String?) ?? '',
      name: (json['name'] as String?) ?? '',
      type: (json['type'] as String?) ?? '',
      subtype: (json['subtype'] as String?) ?? '',
      description: (json['description'] as String?) ?? '',
      price: double.tryParse('${json['price']}') ?? 0.0,
      imageUrl: (json['image_url'] as String?) ?? '',
      ratingAvg: (json['rating_avg'] as num?)?.toDouble() ?? 0.0,
      ratingCount: (json['rating_count'] as num?)?.toInt() ?? 0,
    );
  }

  /// Rótulo de categoria exibido nos cards (subtype, com fallback no type).
  String get categoryLabel =>
      subtype.trim().isNotEmpty ? subtype.toUpperCase() : type.toUpperCase();
}

/// Avaliação de um produto. Espelha `ReviewOut` do backend (`id` UUID,
/// `created_at` ISO-8601).
class Review {
  final String id;
  final String author;
  final int rating;
  final String comment;
  final String createdAt;

  const Review({
    required this.id,
    required this.author,
    required this.rating,
    required this.comment,
    required this.createdAt,
  });

  factory Review.fromJson(Map<String, dynamic> json) {
    return Review(
      id: (json['id'] as String?) ?? '',
      author: (json['author'] as String?) ?? '',
      rating: (json['rating'] as num?)?.toInt() ?? 0,
      comment: (json['comment'] as String?) ?? '',
      createdAt: (json['created_at'] as String?) ?? '',
    );
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/marketplace/product_test.dart`
Expected: PASS (3 tests). Other files won't compile yet — that's fixed in later tasks.

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/domain/product.dart test/features/marketplace/product_test.dart
git commit -m "refactor(marketplace): switch Product/Review to UUID ids with fromJson

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: ProductService (catalog + reviews)

**Files:**
- Create: `lib/features/marketplace/data/product_service.dart`
- Test: `test/features/marketplace/product_service_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/marketplace/product_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/product_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

class _NullTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => null;
}

void main() {
  test('fetchProducts parses items and sends the bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {'id': 'a', 'name': 'Guia', 'type': 'apostila', 'price': '49.90'},
            {'id': 'b', 'name': 'Curso', 'type': 'curso', 'price': '189.90'},
          ],
          'total': 2,
          'limit': 100,
          'offset': 0,
        }),
        200,
      );
    });

    final service =
        ProductService(client: client, tokenStore: _FakeTokenStore());
    final products = await service.fetchProducts();

    expect(products, hasLength(2));
    expect(products.first.id, 'a');
    expect(captured.method, 'GET');
    expect(captured.url.path, endsWith('/products'));
    expect(captured.headers['Authorization'], 'Bearer fake-token');
  });

  test('fetchReviews parses the items array', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 'r1',
              'author': 'Ana',
              'rating': 5,
              'comment': 'Ótimo',
              'created_at': '2026-03-12T00:00:00Z',
            },
          ],
          'total': 1,
          'rating_avg': 5.0,
          'rating_count': 1,
        }),
        200,
      );
    });

    final service =
        ProductService(client: client, tokenStore: _FakeTokenStore());
    final reviews = await service.fetchReviews('prod-1');

    expect(reviews, hasLength(1));
    expect(reviews.first.author, 'Ana');
    expect(captured.url.path, endsWith('/products/prod-1/reviews'));
  });

  test('throws ProductException on non-200', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service =
        ProductService(client: client, tokenStore: _FakeTokenStore());
    expect(() => service.fetchProducts(), throwsA(isA<ProductException>()));
  });

  test('throws ProductException when there is no token', () async {
    final client = MockClient((req) async => http.Response('{}', 200));
    final service =
        ProductService(client: client, tokenStore: _NullTokenStore());
    expect(() => service.fetchProducts(), throwsA(isA<ProductException>()));
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/marketplace/product_service_test.dart`
Expected: FAIL — `ProductService` / `ProductException` not defined.

- [ ] **Step 3: Create `lib/features/marketplace/data/product_service.dart`**

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/product.dart';

/// Lançada quando uma operação do catálogo falha; carrega mensagem amigável.
class ProductException implements Exception {
  ProductException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Cliente HTTP do catálogo (`GET /products`, `GET /products/{id}/reviews`).
class ProductService {
  ProductService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Lista produtos. `limit` alto: o marketplace filtra client-side.
  Future<List<Product>> fetchProducts({int limit = 100}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/products?limit=$limit');
    final body = await _get(uri, 'Falha ao carregar produtos');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items
        .map((e) => Product.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Review>> fetchReviews(String productId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/products/$productId/reviews');
    final body = await _get(uri, 'Falha ao carregar avaliações');
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items
        .map((e) => Review.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<String> _get(Uri uri, String errorLabel) async {
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on ProductException {
      rethrow;
    } on Exception {
      throw ProductException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw ProductException('$errorLabel (${res.statusCode})');
    }
    return res.body;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw ProductException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/marketplace/product_service_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/data/product_service.dart test/features/marketplace/product_service_test.dart
git commit -m "feat(marketplace): add ProductService for products and reviews

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: ProductsProvider (load + client-side filter)

**Files:**
- Create: `lib/features/marketplace/presentation/products_provider.dart`
- Test: `test/features/marketplace/products_provider_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/marketplace/products_provider_test.dart`:

```dart
import 'package:edu_ia/features/marketplace/data/product_service.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/products_provider.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id, String name, String type) => Product(
  id: id, name: name, type: type, subtype: '', description: '', price: 1.0,
);

class _FakeService extends ProductService {
  _FakeService(this.products);
  final List<Product> products;
  @override
  Future<List<Product>> fetchProducts({int limit = 100}) async => products;
}

class _FailingService extends ProductService {
  @override
  Future<List<Product>> fetchProducts({int limit = 100}) async =>
      throw ProductException('boom');
}

void main() {
  test('load success populates products and derives types', () async {
    final provider = ProductsProvider(
      service: _FakeService([
        _p('a', 'Guia', 'apostila'),
        _p('b', 'Curso', 'curso'),
      ]),
    );
    await provider.load();

    expect(provider.state, ProductsViewState.success);
    expect(provider.products, hasLength(2));
    expect(provider.types, containsAll(['apostila', 'curso']));
  });

  test('load failure sets error state', () async {
    final provider = ProductsProvider(service: _FailingService());
    await provider.load();
    expect(provider.state, ProductsViewState.error);
    expect(provider.errorMessage, 'boom');
  });

  test('visibleProducts filters by query and type', () async {
    final provider = ProductsProvider(
      service: _FakeService([
        _p('a', 'Guia de Redação', 'apostila'),
        _p('b', 'Curso de Matemática', 'curso'),
      ]),
    );
    await provider.load();

    provider.setQuery('redação');
    expect(provider.visibleProducts.map((p) => p.id), ['a']);

    provider.setQuery('');
    provider.setType('curso');
    expect(provider.visibleProducts.map((p) => p.id), ['b']);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/marketplace/products_provider_test.dart`
Expected: FAIL — `ProductsProvider` not defined.

- [ ] **Step 3: Create `lib/features/marketplace/presentation/products_provider.dart`**

```dart
import 'package:flutter/foundation.dart';

import '../data/product_service.dart';
import '../domain/product.dart';

enum ProductsViewState { loading, success, error }

/// Estado do catálogo do marketplace: carrega os produtos uma vez e filtra
/// client-side por busca e categoria (mesma UX do mock anterior).
class ProductsProvider extends ChangeNotifier {
  ProductsProvider({ProductService? service})
    : _service = service ?? ProductService();

  final ProductService _service;

  ProductsViewState _state = ProductsViewState.loading;
  List<Product> _products = const [];
  String? _errorMessage;
  String _query = '';
  String? _type;

  ProductsViewState get state => _state;
  List<Product> get products => _products;
  String? get errorMessage => _errorMessage;
  String get query => _query;
  String? get selectedType => _type;

  List<String> get types => _products
      .map((p) => p.type)
      .where((t) => t.isNotEmpty)
      .toSet()
      .toList();

  List<Product> get visibleProducts {
    final q = _query.trim().toLowerCase();
    return _products.where((p) {
      final matchesType = _type == null || p.type == _type;
      final matchesQuery = q.isEmpty ||
          p.name.toLowerCase().contains(q) ||
          p.description.toLowerCase().contains(q);
      return matchesType && matchesQuery;
    }).toList();
  }

  Future<void> load() async {
    _state = ProductsViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _products = await _service.fetchProducts();
      _state = ProductsViewState.success;
    } on ProductException catch (e) {
      _errorMessage = e.message;
      _state = ProductsViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = ProductsViewState.error;
    }
    notifyListeners();
  }

  void setQuery(String value) {
    _query = value;
    notifyListeners();
  }

  void setType(String? value) {
    _type = value;
    notifyListeners();
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/marketplace/products_provider_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/presentation/products_provider.dart test/features/marketplace/products_provider_test.dart
git commit -m "feat(marketplace): add ProductsProvider with client-side filtering

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Update CartStore to String product ids

**Files:**
- Modify: `lib/features/cart/data/cart_store.dart`
- Test: `test/features/cart/cart_store_test.dart`

CartStore stays local (instant +/− UX). Only the `int productId` parameters become `String`, matching `Product.id`.

- [ ] **Step 1: Write the failing test**

Create `test/features/cart/cart_store_test.dart`:

```dart
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id) => Product(
  id: id, name: 'P-$id', type: 'curso', subtype: '', description: '',
  price: 10.0,
);

void main() {
  test('add increments quantity for the same product id', () {
    final cart = CartStore();
    cart.add(_p('a'));
    cart.add(_p('a'), 2);
    expect(cart.totalQuantity, 3);
    expect(cart.items, hasLength(1));
    expect(cart.total, 30.0);
  });

  test('decrement removes the line when it reaches zero', () {
    final cart = CartStore();
    cart.add(_p('a'));
    cart.decrement('a');
    expect(cart.isEmpty, isTrue);
  });

  test('removeAll drops the whole line', () {
    final cart = CartStore();
    cart.add(_p('a'), 3);
    cart.removeAll('a');
    expect(cart.isEmpty, isTrue);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/cart/cart_store_test.dart`
Expected: FAIL — `decrement('a')` / `removeAll('a')` expect `int` (argument type mismatch).

- [ ] **Step 3: Edit `lib/features/cart/data/cart_store.dart`**

Change the three `int productId` occurrences to `String productId`:

```dart
  int _indexOf(String productId) =>
      _items.indexWhere((i) => i.product.id == productId);
```

```dart
  void decrement(String productId) {
```

```dart
  void removeAll(String productId) {
```

(Leave `add(Product product, ...)` unchanged — it reads `product.id`, now a String.)

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/cart/cart_store_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/cart/data/cart_store.dart test/features/cart/cart_store_test.dart
git commit -m "refactor(cart): key CartStore by string product id

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Wire marketplace screen + reviews to real data; remove mock

**Files:**
- Modify: `lib/features/marketplace/presentation/marketplace_screen.dart`
- Modify: `lib/features/marketplace/presentation/product_detail_screen.dart`
- Modify: `lib/features/marketplace/presentation/widgets/review_item.dart`
- Delete: `lib/features/marketplace/data/mock_marketplace.dart`
- Test: `test/features/marketplace/marketplace_screen_test.dart`

This task has no unit-testable logic of its own beyond what Tasks 1–3 cover; it is screen wiring plus one widget smoke test. Reviews are fetched on demand via `ProductService.fetchReviews`.

- [ ] **Step 1: Write the failing widget test**

Create `test/features/marketplace/marketplace_screen_test.dart`:

```dart
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/marketplace/marketplace_screen_test.dart`
Expected: FAIL — `MarketplaceView` not defined.

- [ ] **Step 3: Rewrite `marketplace_screen.dart` to be provider-driven**

Replace the top of the file (imports + the `MarketplaceScreen` class and its `_MarketplaceScreenState` filtering logic) so that:

1. Imports: remove `mock_marketplace.dart`; add
   `import 'products_provider.dart';`.
2. Split into `MarketplaceScreen` (creates the provider) and `MarketplaceView` (consumes it):

```dart
/// Entrada de rota do marketplace. Cria o [ProductsProvider] e carrega o
/// catálogo; a UI fica em [MarketplaceView] para facilitar testes.
class MarketplaceScreen extends StatelessWidget {
  const MarketplaceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => ProductsProvider()..load(),
      child: const MarketplaceView(),
    );
  }
}

class MarketplaceView extends StatefulWidget {
  const MarketplaceView({super.key});

  @override
  State<MarketplaceView> createState() => _MarketplaceViewState();
}

class _MarketplaceViewState extends State<MarketplaceView> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ProductsProvider>();
    final filtered = provider.visibleProducts;
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SafeArea(
          child: Column(
            children: [
              _TopBar(
                controller: _searchController,
                onSearchChange: provider.setQuery,
                onOpenProfile: () => Navigator.pushNamed(context, '/profile'),
                onOpenCart: () => Navigator.pushNamed(context, '/checkout'),
              ),
              _CategoryChips(
                types: provider.types,
                selected: provider.selectedType,
                onSelected: provider.setType,
              ),
              Expanded(child: _buildBody(provider, filtered)),
            ],
          ),
        ),
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 3,
        ),
      ),
    );
  }

  Widget _buildBody(ProductsProvider provider, List<Product> filtered) {
    switch (provider.state) {
      case ProductsViewState.loading:
        return const Center(
          child: CircularProgressIndicator(color: AppColors.purple),
        );
      case ProductsViewState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Não foi possível carregar o catálogo.',
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                provider.errorMessage ?? '',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: provider.load,
                child: const Text('Tentar novamente',
                    style: TextStyle(color: AppColors.purple)),
              ),
            ],
          ),
        );
      case ProductsViewState.success:
        return LayoutBuilder(
          builder: (context, constraints) {
            const padding = 24.0;
            const spacing = 12.0;
            final cellWidth =
                (constraints.maxWidth - padding * 2 - spacing) / 2;
            final extent = cellWidth + 252;
            return CustomScrollView(
              slivers: [
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(padding, padding, padding, 16),
                    child: Text(
                      'EduMarketplace',
                      style: TextStyle(
                        fontSize: 32,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                        letterSpacing: -0.5,
                      ),
                    ),
                  ),
                ),
                if (filtered.isEmpty)
                  SliverToBoxAdapter(child: _EmptyResult(query: provider.query))
                else
                  SliverPadding(
                    padding:
                        const EdgeInsets.fromLTRB(padding, 0, padding, 24),
                    sliver: SliverGrid(
                      gridDelegate:
                          SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        crossAxisSpacing: spacing,
                        mainAxisSpacing: 16,
                        mainAxisExtent: extent,
                      ),
                      delegate: SliverChildBuilderDelegate(
                        (context, i) => _ProductCard(product: filtered[i]),
                        childCount: filtered.length,
                      ),
                    ),
                  ),
              ],
            );
          },
        );
    }
  }
}
```

3. In `_ProductCard`, change the navigation argument from the id to the whole product (the detail screen will receive a `Product`):

```dart
      onTap: () =>
          Navigator.pushNamed(context, '/product', arguments: product),
```

4. Keep `_TopBar`, `_CartButton`, `_CategoryChips`, `_Chip`, `_ProductCard`, `_EmptyResult` as they are, except `_TopBar.onSearchChange` is now wired to `provider.setQuery` (already done above) — remove the old `setState(() => _query = v)` usages and the `_query`/`_selectedType`/`_types`/`_filtered` members from the old state class (they moved into the provider).

- [ ] **Step 4: Update `review_item.dart` — `showReviewsBottomSheet` fetches reviews**

Replace the imports and `showReviewsBottomSheet` so it no longer reads the mock; it fetches via `ProductService` with a `FutureBuilder`:

Imports (replace `import '../../data/mock_marketplace.dart';` with):

```dart
import '../../data/product_service.dart';
```

Replace the `showReviewsBottomSheet` body's reviews source. The function keeps its signature `void showReviewsBottomSheet(BuildContext context, Product product)`. Replace the `final reviews = reviewsForProduct(product.id);` line and the `if (reviews.isEmpty) ... else ...` block with a `FutureBuilder<List<Review>>`:

```dart
              FutureBuilder<List<Review>>(
                future: ProductService().fetchReviews(product.id),
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Center(
                        child: CircularProgressIndicator(
                            color: AppColors.purple),
                      ),
                    );
                  }
                  final reviews = snapshot.data ?? const <Review>[];
                  if (reviews.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Text(
                        'Este produto ainda não possui avaliações.',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    );
                  }
                  return Flexible(
                    child: ListView.separated(
                      shrinkWrap: true,
                      padding: EdgeInsets.zero,
                      itemCount: reviews.length,
                      separatorBuilder: (context, index) =>
                          const SizedBox(height: 10),
                      itemBuilder: (_, i) => ReviewItem(review: reviews[i]),
                    ),
                  );
                },
              ),
```

- [ ] **Step 5: Update `product_detail_screen.dart` to receive a Product and fetch reviews**

1. Remove `import '../data/mock_marketplace.dart';`; add `import '../data/product_service.dart';`.
2. Change the argument read:

```dart
    final product = ModalRoute.of(context)?.settings.arguments as Product?;
```

(delete the `productId`/`productById` lines.)

3. In `_ProductContent`, replace the synchronous `final reviews = reviewsForProduct(product.id);` and the inline reviews list with a `FutureBuilder<List<Review>>` over `ProductService().fetchReviews(product.id)`, mirroring Step 4. Replace the block starting at `if (reviews.isEmpty)` through the closing of the `for (final review in reviews)` loop with:

```dart
          FutureBuilder<List<Review>>(
            future: ProductService().fetchReviews(product.id),
            builder: (context, snapshot) {
              final reviews = snapshot.data ?? const <Review>[];
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    'Carregando avaliações...',
                    style:
                        TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                );
              }
              if (reviews.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    'Ainda não há avaliações.',
                    style:
                        TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                );
              }
              return Column(
                children: [
                  for (final review in reviews) ...[
                    ReviewItem(review: review),
                    const SizedBox(height: 10),
                  ],
                ],
              );
            },
          ),
```

- [ ] **Step 6: Delete the mock and verify no references remain**

```bash
rm lib/features/marketplace/data/mock_marketplace.dart
grep -rn "mock_marketplace\|productById\|reviewsForProduct\|mockProducts" lib test
```

Expected: no output (no remaining references). If `widget_test.dart` or others reference it, fix them.

- [ ] **Step 7: Run tests + analyzer**

Run: `flutter test test/features/marketplace/marketplace_screen_test.dart`
Expected: PASS (1 test).
Run: `flutter analyze lib/features/marketplace lib/features/cart`
Expected: No issues.

- [ ] **Step 8: Commit**

```bash
git add lib/features/marketplace test/features/marketplace/marketplace_screen_test.dart
git commit -m "feat(marketplace): load real products and reviews from the API

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — Checkout creates a real order

### Task 6: CheckoutService (push cart → create order)

**Files:**
- Create: `lib/features/marketplace/data/checkout_service.dart`
- Test: `test/features/marketplace/checkout_service_test.dart`

`placeOrder` makes the backend cart match the local cart, then creates the order. Because backend `POST /cart/items` *increments*, it first clears any existing backend cart items (idempotent on retry).

- [ ] **Step 1: Write the failing test**

Create `test/features/marketplace/checkout_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/data/checkout_service.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

Product _p(String id, double price) => Product(
  id: id, name: 'P', type: 'curso', subtype: '', description: '', price: price,
);

void main() {
  test('placeOrder clears the cart, posts each item, creates the order',
      () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      if (req.method == 'GET' && req.url.path.endsWith('/cart')) {
        return http.Response(
          jsonEncode({
            'items': [
              {'product_id': 'old', 'name': 'Old', 'type': 't', 'price': '5.00',
               'quantity': 1, 'subtotal': '5.00'},
            ],
            'total': '5.00',
          }),
          200,
        );
      }
      if (req.method == 'DELETE') return http.Response('{}', 200);
      if (req.method == 'POST' && req.url.path.endsWith('/cart/items')) {
        return http.Response('{}', 201);
      }
      if (req.method == 'POST' && req.url.path.endsWith('/orders')) {
        return http.Response(
          jsonEncode({
            'id': 'order-9', 'total': '20.00', 'status': 'pending',
            'created_at': '2026-06-13T00:00:00Z', 'items': [],
          }),
          201,
        );
      }
      return http.Response('nope', 500);
    });

    final cart = CartStore()
      ..add(_p('a', 10.0), 2);

    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());
    final orderId = await service.placeOrder(
      items: cart.items,
      paymentMethod: 'PIX',
    );

    expect(orderId, 'order-9');
    // Cleared the stale 'old' item, posted item 'a', then created the order.
    expect(calls, containsAllInOrder(<String>[
      'GET /api/cart',
      'DELETE /api/cart/items/old',
      'POST /api/cart/items',
      'POST /api/orders',
    ]));
  });

  test('throws CheckoutException when order creation fails', () async {
    final client = MockClient((req) async {
      if (req.url.path.endsWith('/cart') && req.method == 'GET') {
        return http.Response(jsonEncode({'items': [], 'total': '0.00'}), 200);
      }
      if (req.method == 'POST' && req.url.path.endsWith('/cart/items')) {
        return http.Response('{}', 201);
      }
      return http.Response('Cart is empty', 400); // POST /orders fails
    });

    final cart = CartStore()..add(_p('a', 10.0));
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.placeOrder(items: cart.items, paymentMethod: 'PIX'),
      throwsA(isA<CheckoutException>()),
    );
  });
}
```

> NOTE: `ApiConfig.baseUrl` ends in `/api`, so paths are `/api/cart`, `/api/orders`, etc.

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/marketplace/checkout_service_test.dart`
Expected: FAIL — `CheckoutService` / `CheckoutException` not defined.

- [ ] **Step 3: Create `lib/features/marketplace/data/checkout_service.dart`**

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../../cart/domain/cart_item.dart';

/// Lançada quando a finalização da compra falha; carrega mensagem amigável.
class CheckoutException implements Exception {
  CheckoutException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Finaliza a compra: espelha o carrinho local no carrinho do backend e cria o
/// pedido (`POST /orders`).
///
/// O backend `POST /cart/items` *soma* quantidades, então primeiro esvaziamos
/// o carrinho do backend (idempotente em caso de retry) antes de enviar os
/// itens locais.
class CheckoutService {
  CheckoutService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Retorna o id do pedido criado.
  Future<String> placeOrder({
    required List<CartItem> items,
    required String paymentMethod,
  }) async {
    final headers = await _headers();
    await _clearBackendCart(headers);

    for (final item in items) {
      await _send(
        () => _client.post(
          Uri.parse('${ApiConfig.baseUrl}/cart/items'),
          headers: {'Content-Type': 'application/json', ...headers},
          body: jsonEncode({
            'product_id': item.product.id,
            'quantity': item.quantity,
          }),
        ),
        accept: const {200, 201},
        error: 'Falha ao montar o pedido',
      );
    }

    final res = await _send(
      () => _client.post(
        Uri.parse('${ApiConfig.baseUrl}/orders'),
        headers: {'Content-Type': 'application/json', ...headers},
        body: jsonEncode({'payment_method': paymentMethod}),
      ),
      accept: const {200, 201},
      error: 'Falha ao finalizar o pedido',
    );
    return (jsonDecode(res.body) as Map<String, dynamic>)['id'] as String;
  }

  Future<void> _clearBackendCart(Map<String, String> headers) async {
    final res = await _send(
      () => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/cart'),
        headers: headers,
      ),
      accept: const {200},
      error: 'Falha ao ler o carrinho',
    );
    final items =
        (jsonDecode(res.body) as Map<String, dynamic>)['items'] as List;
    for (final item in items) {
      final id = (item as Map<String, dynamic>)['product_id'];
      await _send(
        () => _client.delete(
          Uri.parse('${ApiConfig.baseUrl}/cart/items/$id'),
          headers: headers,
        ),
        accept: const {200},
        error: 'Falha ao limpar o carrinho',
      );
    }
  }

  Future<http.Response> _send(
    Future<http.Response> Function() request, {
    required Set<int> accept,
    required String error,
  }) async {
    final http.Response res;
    try {
      res = await request();
    } on CheckoutException {
      rethrow;
    } on Exception {
      throw CheckoutException('Não foi possível conectar ao servidor');
    }
    if (!accept.contains(res.statusCode)) {
      throw CheckoutException('$error (${res.statusCode})');
    }
    return res;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw CheckoutException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/marketplace/checkout_service_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/data/checkout_service.dart test/features/marketplace/checkout_service_test.dart
git commit -m "feat(marketplace): add CheckoutService to persist orders via the API

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Wire checkout `_placeOrder` to CheckoutService

**Files:**
- Modify: `lib/features/marketplace/presentation/checkout_screen.dart`

`_placeOrder` currently clears the local cart and shows a fake success. Make it call `CheckoutService.placeOrder` first; only clear the local cart and show success on a real 201. On failure, show the error and keep the cart.

- [ ] **Step 1: Add the import**

At the top of `checkout_screen.dart` add:

```dart
import 'package:edu_ia/features/marketplace/data/checkout_service.dart';
```

- [ ] **Step 2: Replace `_placeOrder`**

Make it async and call the service before the existing success UX. Capture `CartStore` and `ScaffoldMessenger`/navigator before the await (avoid `use_build_context_synchronously`). The current method body (`context.read<CartStore>().clear(); switch (...) {...}`) becomes:

```dart
  Future<void> _placeOrder(PaymentMethod method) async {
    final cart = context.read<CartStore>();
    final items = cart.items;
    if (items.isEmpty) return;

    setState(() => _placingOrder = true);
    try {
      await CheckoutService().placeOrder(
        items: items,
        paymentMethod: _paymentTitle(method),
      );
    } on CheckoutException catch (e) {
      if (mounted) {
        setState(() => _placingOrder = false);
        _snack(e.message);
      }
      return;
    }

    if (!mounted) return;
    setState(() => _placingOrder = false);
    cart.clear();

    switch (method.type) {
      case PaymentMethodType.pix:
        _showCopyCodeDialog(
          title: 'Pague com PIX',
          description:
              'Copie o código abaixo e cole no app do seu banco para concluir o pagamento.',
          code: _generatePixCode(),
          copiedMessage: 'Código PIX copiado',
        );
        break;
      case PaymentMethodType.boleto:
        _showCopyCodeDialog(
          title: 'Pague com Boleto',
          description:
              'Copie a linha digitável abaixo e pague no app do seu banco. Compensação em até 2 dias úteis.',
          code: _generateBoletoCode(),
          copiedMessage: 'Linha digitável copiada',
        );
        break;
      case PaymentMethodType.creditCard:
        _snack('Pedido finalizado com sucesso!');
        Navigator.pop(context);
        break;
    }
  }
```

- [ ] **Step 3: Add the `_placingOrder` flag to the State class**

Near the other state fields in `_CheckoutScreenState`, add:

```dart
  bool _placingOrder = false;
```

(If the confirm button can be disabled, gate it on `!_placingOrder`. Optional; not required for correctness.)

- [ ] **Step 4: Update the dialog's confirm handler**

In `_showFinalizeDialog`, the confirm `onPressed` calls `_placeOrder(method)` (now returns a Future — fire-and-forget is fine here):

```dart
            onPressed: () {
              Navigator.pop(dialogContext);
              _placeOrder(method);
            },
```

(No change needed if already calling `_placeOrder(method);`.)

- [ ] **Step 5: Analyze + manual smoke**

Run: `flutter analyze lib/features/marketplace`
Expected: No issues (in particular, no `use_build_context_synchronously`).

Manual smoke (requires running backend + logged-in user):
1. `flutter run` (with backend up; see `docs/back-end/start-here.md`).
2. Loja → add a product → carrinho → Confirmar.
3. Go to "Seus pedidos" → the new order appears (status "Confirmado"/"Em separação").

- [ ] **Step 6: Commit**

```bash
git add lib/features/marketplace/presentation/checkout_screen.dart
git commit -m "feat(marketplace): create a real order on checkout

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Run the whole suite: `flutter test` — all green except the pre-existing `test/widget_test.dart` "Counter increments smoke test" (broken template stub, unrelated). If that stub now fails to *compile* due to the mock removal, delete or fix it in a `test:` commit.
- [ ] `flutter analyze lib test` — no new issues.
- [ ] Manual end-to-end: place an order, confirm it appears in "Seus pedidos" and that "Rastrear pedido" opens tracking for the real order id.

---

## Self-Review notes

- **Spec coverage:** products real (Tasks 1–3, 5), cart UUID (Task 4), checkout→order (Tasks 6–7). Reviews wired (Task 5). Orders listing already done in a prior change.
- **Type consistency:** `Product.id`/`Review.id` are `String` everywhere; `CartStore.decrement/removeAll` take `String`; nav argument for `/product` is a `Product`; `CheckoutService.placeOrder` consumes `List<CartItem>` and returns the order id `String`.
- **Known follow-ups (not in this plan):** cart persistence across restarts; "Comprar novamente"/"Avaliar itens" wiring; replacing the icon placeholders with real `image_url` thumbnails in the catalog/cart.
```
