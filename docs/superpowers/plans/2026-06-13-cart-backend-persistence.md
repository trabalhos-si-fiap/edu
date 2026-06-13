# Cart Backend Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backend cart the source of truth for the Flutter working cart so it survives app restarts, by adding a `CartService`, backing `CartStore` with it (optimistic write-through), loading on launch, and simplifying checkout.

**Architecture:** Frontend-only. A new `CartService` wraps the existing backend cart CRUD (`GET /cart`, `POST /cart/items`, `DELETE /cart/items/{id}`). `CartStore` mutates local state optimistically and writes through in the background; on failure it resyncs from the server. The marketplace loads the cart on launch. `CheckoutService` drops its staging logic and just `POST /orders` (the server reads and empties its own cart).

**Tech Stack:** Flutter/Dart, `provider`, `http` (+ `package:http/testing.dart` `MockClient`), `flutter_test`.

---

## Background (read before starting)

- **No backend changes.** The cart CRUD is complete and committed in
  `back-end/app/modules/cart/` (router wired, migration `57b1073cc5f3`, tests).
- Endpoints (all under `${ApiConfig.baseUrl}` = `http://10.0.2.2:8001/api`):
  - `GET /cart` → `{items: [...], total: "..."}`
  - `POST /cart/items` body `{product_id, quantity}` → returns full cart (201)
  - `DELETE /cart/items/{product_id}?quantity=N` → returns full cart (200);
    omit `quantity` to remove the whole line.
- `CartOut` item fields: `product_id, name, type, subtype, price, quantity,
  subtotal, image_url, rating_avg, rating_count`. Enough to build a frontend
  `Product` (`description` defaults to `''`).
- Existing patterns to mirror: `ProductService` / `CheckoutService`
  (`front-end-flutter/lib/features/marketplace/data/`) — injectable
  `http.Client? client` + `TokenStore? tokenStore`, a friendly-message
  `Exception`, a private `_send` + `_headers` helper.
- Tests already use `package:http/testing.dart`'s `MockClient` and a
  `_FakeTokenStore extends TokenStore { readAccessToken() async => 'fake-token'; }`.

## File Structure

- **Create** `front-end-flutter/lib/features/cart/data/cart_service.dart` —
  HTTP client for the backend cart; parses `CartOut` → `List<CartItem>`.
- **Modify** `front-end-flutter/lib/features/cart/data/cart_store.dart` —
  backend-backed, optimistic write-through, `load`/`clear`/`reset`.
- **Modify** `front-end-flutter/lib/features/marketplace/presentation/marketplace_screen.dart` —
  `MarketplaceView` loads the cart in `initState`.
- **Modify** `front-end-flutter/lib/features/marketplace/data/checkout_service.dart` —
  `placeOrder({required String paymentMethod})`, drop staging.
- **Modify** `front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart` —
  update the `placeOrder` call site.
- **Create** `front-end-flutter/test/features/cart/cart_service_test.dart`.
- **Modify** `front-end-flutter/test/features/cart/cart_store_test.dart` —
  inject a fake `CartService`; add load/error/clear tests.
- **Modify** `front-end-flutter/test/features/marketplace/marketplace_screen_test.dart` —
  inject a no-network `CartStore` so `initState` `load()` doesn't hit the network.
- **Modify** `front-end-flutter/test/features/marketplace/checkout_service_test.dart` —
  rewrite for the simplified flow.

All `flutter` commands run from `front-end-flutter/`.

---

### Task 1: `CartService`

**Files:**
- Create: `front-end-flutter/lib/features/cart/data/cart_service.dart`
- Test: `front-end-flutter/test/features/cart/cart_service_test.dart`

- [ ] **Step 1: Write the failing tests**

Create `front-end-flutter/test/features/cart/cart_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/cart/data/cart_service.dart';
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

String _cartJson() => jsonEncode({
      'items': [
        {
          'product_id': 'a', 'name': 'Apostila', 'type': 'apostila',
          'subtype': 'Digital', 'price': '49.90', 'quantity': 2,
          'subtotal': '99.80', 'image_url': 'http://img', 'rating_avg': 4.5,
          'rating_count': 10,
        },
      ],
      'total': '99.80',
    });

void main() {
  test('fetch maps CartOut items to CartItems', () async {
    final client = MockClient((req) async {
      expect(req.method, 'GET');
      expect(req.url.path, '/api/cart');
      return http.Response(_cartJson(), 200);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    final items = await service.fetch();

    expect(items, hasLength(1));
    expect(items.first.product.id, 'a');
    expect(items.first.product.name, 'Apostila');
    expect(items.first.product.price, 49.90);
    expect(items.first.quantity, 2);
  });

  test('addItem posts product_id and quantity and parses the cart', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      expect(jsonDecode(req.body), {'product_id': 'a', 'quantity': 2});
      return http.Response(_cartJson(), 201);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    final items = await service.addItem('a', 2);

    expect(calls, ['POST /api/cart/items']);
    expect(items.first.quantity, 2);
  });

  test('removeItem with quantity sends a decrement query', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}?${req.url.query}');
      return http.Response(_cartJson(), 200);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    await service.removeItem('a', quantity: 1);

    expect(calls, ['DELETE /api/cart/items/a?quantity=1']);
  });

  test('removeItem without quantity omits the query', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}?${req.url.query}');
      return http.Response(_cartJson(), 200);
    });
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    await service.removeItem('a');

    expect(calls, ['DELETE /api/cart/items/a?']);
  });

  test('non-2xx throws CartException', () async {
    final client = MockClient((req) async => http.Response('boom', 500));
    final service = CartService(client: client, tokenStore: _FakeTokenStore());

    expect(() => service.fetch(), throwsA(isA<CartException>()));
  });

  test('missing token throws CartException', () async {
    final client = MockClient((req) async => http.Response(_cartJson(), 200));
    final service = CartService(client: client, tokenStore: _NullTokenStore());

    expect(() => service.fetch(), throwsA(isA<CartException>()));
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `flutter test test/features/cart/cart_service_test.dart`
Expected: FAIL — `Target of URI doesn't exist: '.../cart_service.dart'` / `CartService` undefined.

- [ ] **Step 3: Write the implementation**

Create `front-end-flutter/lib/features/cart/data/cart_service.dart`:

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../../marketplace/domain/product.dart';
import '../domain/cart_item.dart';

/// Lançada quando uma operação do carrinho falha; carrega mensagem amigável.
class CartException implements Exception {
  CartException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Cliente HTTP do carrinho do backend (`/cart`). Cada método retorna o
/// carrinho completo como o servidor o vê, mapeado para [CartItem].
class CartService {
  CartService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<List<CartItem>> fetch() async {
    final res = await _send(
      () async => _client.get(_uri(''), headers: await _headers()),
      'Falha ao carregar o carrinho',
    );
    return _parse(res.body);
  }

  Future<List<CartItem>> addItem(String productId, int quantity) async {
    final res = await _send(
      () async => _client.post(
        _uri('/items'),
        headers: {'Content-Type': 'application/json', ...await _headers()},
        body: jsonEncode({'product_id': productId, 'quantity': quantity}),
      ),
      'Falha ao adicionar ao carrinho',
    );
    return _parse(res.body);
  }

  Future<List<CartItem>> removeItem(String productId, {int? quantity}) async {
    final query = quantity == null ? '' : '?quantity=$quantity';
    final res = await _send(
      () async =>
          _client.delete(_uri('/items/$productId$query'), headers: await _headers()),
      'Falha ao remover do carrinho',
    );
    return _parse(res.body);
  }

  Uri _uri(String suffix) => Uri.parse('${ApiConfig.baseUrl}/cart$suffix');

  List<CartItem> _parse(String body) {
    final items = (jsonDecode(body) as Map<String, dynamic>)['items'] as List;
    return items.map((e) {
      final m = e as Map<String, dynamic>;
      return CartItem(
        product: Product(
          id: m['product_id'] as String,
          name: (m['name'] as String?) ?? '',
          type: (m['type'] as String?) ?? '',
          subtype: (m['subtype'] as String?) ?? '',
          description: '',
          price: double.tryParse('${m['price']}') ?? 0.0,
          imageUrl: (m['image_url'] as String?) ?? '',
          ratingAvg: (m['rating_avg'] as num?)?.toDouble() ?? 0.0,
          ratingCount: (m['rating_count'] as num?)?.toInt() ?? 0,
        ),
        quantity: (m['quantity'] as num?)?.toInt() ?? 0,
      );
    }).toList();
  }

  Future<http.Response> _send(
    Future<http.Response> Function() request,
    String error,
  ) async {
    final http.Response res;
    try {
      res = await request();
    } on CartException {
      rethrow;
    } on Exception {
      throw CartException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw CartException('$error (${res.statusCode})');
    }
    return res;
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw CartException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `flutter test test/features/cart/cart_service_test.dart`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd front-end-flutter
git add lib/features/cart/data/cart_service.dart test/features/cart/cart_service_test.dart
git commit -m "$(printf 'feat(cart): add CartService for the backend cart API\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Back `CartStore` with `CartService` (optimistic write-through)

**Files:**
- Modify: `front-end-flutter/lib/features/cart/data/cart_store.dart`
- Test: `front-end-flutter/test/features/cart/cart_store_test.dart` (rewrite)

- [ ] **Step 1: Rewrite the tests (failing)**

Replace the entire contents of
`front-end-flutter/test/features/cart/cart_store_test.dart`:

```dart
import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/cart/domain/cart_item.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id) => Product(
      id: id, name: 'P-$id', type: 'curso', subtype: '', description: '',
      price: 10.0,
    );

class _FakeCartService extends CartService {
  final List<String> calls = [];
  List<CartItem> serverItems = [];
  bool failMutations = false;

  @override
  Future<List<CartItem>> fetch() async {
    calls.add('fetch');
    return List.of(serverItems);
  }

  @override
  Future<List<CartItem>> addItem(String productId, int quantity) async {
    calls.add('addItem:$productId:$quantity');
    if (failMutations) throw CartException('boom');
    return List.of(serverItems);
  }

  @override
  Future<List<CartItem>> removeItem(String productId, {int? quantity}) async {
    calls.add('removeItem:$productId:${quantity ?? 'all'}');
    if (failMutations) throw CartException('boom');
    return List.of(serverItems);
  }
}

void main() {
  test('add updates local state immediately and writes through', () async {
    final service = _FakeCartService();
    final cart = CartStore(service: service);

    cart.add(_p('a'), 2);

    expect(cart.totalQuantity, 2); // optimistic, synchronous
    expect(cart.items, hasLength(1));
    await pumpEventQueue();
    expect(service.calls, contains('addItem:a:2'));
  });

  test('add increments quantity for the same product id', () {
    final cart = CartStore(service: _FakeCartService());
    cart.add(_p('a'));
    cart.add(_p('a'), 2);
    expect(cart.totalQuantity, 3);
    expect(cart.items, hasLength(1));
    expect(cart.total, 30.0);
  });

  test('decrement removes the line when it reaches zero', () {
    final cart = CartStore(service: _FakeCartService());
    cart.add(_p('a'));
    cart.decrement('a');
    expect(cart.isEmpty, isTrue);
  });

  test('removeAll drops the whole line', () {
    final cart = CartStore(service: _FakeCartService());
    cart.add(_p('a'), 3);
    cart.removeAll('a');
    expect(cart.isEmpty, isTrue);
  });

  test('load populates items and is guarded unless forced', () async {
    final service = _FakeCartService()
      ..serverItems = [CartItem(product: _p('a'), quantity: 4)];
    final cart = CartStore(service: service);

    await cart.load();
    expect(cart.totalQuantity, 4);
    expect(service.calls, ['fetch']);

    await cart.load(); // guarded
    expect(service.calls, ['fetch']);

    await cart.load(force: true);
    expect(service.calls, ['fetch', 'fetch']);
  });

  test('mutation failure resyncs from the server and sets errorMessage',
      () async {
    final service = _FakeCartService()
      ..serverItems = [] // server cart is empty
      ..failMutations = true;
    final cart = CartStore(service: service);

    cart.add(_p('a'));
    expect(cart.totalQuantity, 1); // optimistic

    await pumpEventQueue();
    expect(cart.errorMessage, isNotNull);
    expect(service.calls, contains('fetch')); // resync via load(force: true)
    expect(cart.isEmpty, isTrue); // resynced to the empty server cart
  });

  test('clear zeroes local state without calling the service', () {
    final service = _FakeCartService();
    final cart = CartStore(service: service)..add(_p('a'));
    service.calls.clear();

    cart.clear();

    expect(cart.isEmpty, isTrue);
    expect(service.calls, isEmpty);
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `flutter test test/features/cart/cart_store_test.dart`
Expected: FAIL — `CartStore` has no `service` named parameter / no `load`/`errorMessage`.

- [ ] **Step 3: Rewrite the implementation**

Replace the entire contents of
`front-end-flutter/lib/features/cart/data/cart_store.dart`:

```dart
import 'package:flutter/foundation.dart';

import '../../marketplace/domain/product.dart';
import '../domain/cart_item.dart';
import 'cart_service.dart';

/// Estado do carrinho, com o backend como fonte da verdade.
///
/// Exposto na árvore via `ChangeNotifierProvider`. As mutações são otimistas:
/// o estado local muda na hora (UI instantânea) e a escrita no backend acontece
/// em segundo plano (write-through). Em caso de falha, o estado é ressincronizado
/// a partir do servidor (`load(force: true)`) e [errorMessage] é preenchido.
class CartStore extends ChangeNotifier {
  CartStore({CartService? service}) : _service = service ?? CartService();

  final CartService _service;
  final List<CartItem> _items = [];
  bool _loaded = false;

  bool isLoading = false;
  String? errorMessage;

  List<CartItem> get items => List.unmodifiable(_items);
  bool get isEmpty => _items.isEmpty;
  int get totalQuantity => _items.fold(0, (sum, i) => sum + i.quantity);
  double get total => _items.fold(0.0, (sum, i) => sum + i.subtotal);

  int _indexOf(String productId) =>
      _items.indexWhere((i) => i.product.id == productId);

  /// Carrega o carrinho do backend. Roda uma vez por sessão; use [force] para
  /// recarregar (ex.: ressincronização após falha de escrita).
  Future<void> load({bool force = false}) async {
    if (_loaded && !force) return;
    isLoading = true;
    notifyListeners();
    try {
      final items = await _service.fetch();
      _items
        ..clear()
        ..addAll(items);
      _loaded = true;
      errorMessage = null;
    } on CartException catch (e) {
      errorMessage = e.message;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  void add(Product product, [int quantity = 1]) {
    final idx = _indexOf(product.id);
    if (idx >= 0) {
      _items[idx] = _items[idx].copyWith(
        quantity: _items[idx].quantity + quantity,
      );
    } else {
      _items.add(CartItem(product: product, quantity: quantity));
    }
    notifyListeners();
    _sync(() => _service.addItem(product.id, quantity));
  }

  void decrement(String productId) {
    final idx = _indexOf(productId);
    if (idx < 0) return;
    final next = _items[idx].quantity - 1;
    if (next <= 0) {
      _items.removeAt(idx);
    } else {
      _items[idx] = _items[idx].copyWith(quantity: next);
    }
    notifyListeners();
    _sync(() => _service.removeItem(productId, quantity: 1));
  }

  void removeAll(String productId) {
    final idx = _indexOf(productId);
    if (idx < 0) return;
    _items.removeAt(idx);
    notifyListeners();
    _sync(() => _service.removeItem(productId));
  }

  /// Zera o estado local. Usado após o checkout — o `POST /orders` já esvaziou
  /// o carrinho no servidor, então não há chamada de API aqui.
  void clear() {
    if (_items.isEmpty) return;
    _items.clear();
    notifyListeners();
  }

  /// Limpa o estado local e a marca de carregamento (ex.: no logout).
  void reset() {
    _items.clear();
    _loaded = false;
    errorMessage = null;
    notifyListeners();
  }

  /// Dispara a escrita no backend; em sucesso, mantém o estado otimista. Em
  /// falha, ressincroniza do servidor e preenche [errorMessage]. A mensagem é
  /// definida *depois* do resync porque `load` zera [errorMessage] no sucesso.
  Future<void> _sync(Future<List<CartItem>> Function() op) async {
    try {
      await op();
      errorMessage = null;
    } on CartException catch (e) {
      await load(force: true);
      errorMessage = e.message;
      notifyListeners();
    }
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `flutter test test/features/cart/cart_store_test.dart`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd front-end-flutter
git add lib/features/cart/data/cart_store.dart test/features/cart/cart_store_test.dart
git commit -m "$(printf 'refactor(cart): back CartStore with CartService (optimistic write-through)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Load the cart on marketplace launch

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/marketplace_screen.dart` (the `_MarketplaceViewState` class, ~lines 35-42)
- Modify: `front-end-flutter/test/features/marketplace/marketplace_screen_test.dart` (the `_harness` and imports)

> Why the test change: with the new `initState`, `MarketplaceView` reads
> `CartStore` and calls `load()`, which would hit the real network. The widget
> test must inject a `CartStore` whose `CartService` returns an empty cart.

- [ ] **Step 1: Update the widget test (failing for the right reason)**

In `front-end-flutter/test/features/marketplace/marketplace_screen_test.dart`,
add these imports near the existing ones:

```dart
import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:edu_ia/features/cart/domain/cart_item.dart';
```

Add a no-network fake service after the existing `_FakeService` class:

```dart
class _EmptyCartService extends CartService {
  @override
  Future<List<CartItem>> fetch() async => <CartItem>[];
}
```

Replace the `CartStore` provider line inside `_harness` (currently
`ChangeNotifierProvider<CartStore>(create: (_) => CartStore())`) with:

```dart
        ChangeNotifierProvider<CartStore>(
          create: (_) => CartStore(service: _EmptyCartService()),
        ),
```

- [ ] **Step 2: Run the test to confirm current state still passes**

Run: `flutter test test/features/marketplace/marketplace_screen_test.dart`
Expected: PASS (the production code hasn't changed yet; this verifies the test
harness compiles with the injected service before we add `initState`).

- [ ] **Step 3: Add the load trigger**

In `front-end-flutter/lib/features/marketplace/presentation/marketplace_screen.dart`,
add an `initState` to `_MarketplaceViewState` (it currently has only `dispose`).
Insert directly above the existing `@override void dispose()`:

```dart
  @override
  void initState() {
    super.initState();
    context.read<CartStore>().load();
  }
```

`provider` (`context.read`) and `CartStore` are already imported in this file.

- [ ] **Step 4: Run the test and analyzer**

Run: `flutter test test/features/marketplace/marketplace_screen_test.dart`
Expected: PASS.

Run: `flutter analyze lib/features/marketplace/presentation/marketplace_screen.dart`
Expected: No issues.

- [ ] **Step 5: Commit**

```bash
cd front-end-flutter
git add lib/features/marketplace/presentation/marketplace_screen.dart test/features/marketplace/marketplace_screen_test.dart
git commit -m "$(printf 'feat(marketplace): load the cart on marketplace launch\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Simplify `CheckoutService` to `POST /orders` only

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/data/checkout_service.dart`
- Test: `front-end-flutter/test/features/marketplace/checkout_service_test.dart` (rewrite)

- [ ] **Step 1: Rewrite the tests (failing)**

Replace the entire contents of
`front-end-flutter/test/features/marketplace/checkout_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/marketplace/data/checkout_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

void main() {
  test('placeOrder posts only to /orders and returns the order id', () async {
    final calls = <String>[];
    final client = MockClient((req) async {
      calls.add('${req.method} ${req.url.path}');
      if (req.method == 'POST' && req.url.path.endsWith('/orders')) {
        return http.Response(jsonEncode({'id': 'order-9'}), 201);
      }
      return http.Response('nope', 500);
    });
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    final orderId = await service.placeOrder(paymentMethod: 'PIX');

    expect(orderId, 'order-9');
    expect(calls, ['POST /api/orders']);
  });

  test('throws CheckoutException when order creation fails', () async {
    final client =
        MockClient((req) async => http.Response('Cart is empty', 400));
    final service =
        CheckoutService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.placeOrder(paymentMethod: 'PIX'),
      throwsA(isA<CheckoutException>()),
    );
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `flutter test test/features/marketplace/checkout_service_test.dart`
Expected: FAIL — `placeOrder` still requires the `items:` argument.

- [ ] **Step 3: Simplify the implementation**

Replace the entire contents of
`front-end-flutter/lib/features/marketplace/data/checkout_service.dart`:

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';

/// Lançada quando a finalização da compra falha; carrega mensagem amigável.
class CheckoutException implements Exception {
  CheckoutException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Finaliza a compra criando o pedido (`POST /orders`). O backend lê o próprio
/// carrinho do usuário e o esvazia na mesma transação, então não há staging
/// aqui — o carrinho do backend já está sincronizado com o [CartStore].
class CheckoutService {
  CheckoutService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  /// Retorna o id do pedido criado.
  Future<String> placeOrder({required String paymentMethod}) async {
    final headers = await _headers();
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `flutter test test/features/marketplace/checkout_service_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd front-end-flutter
git add lib/features/marketplace/data/checkout_service.dart test/features/marketplace/checkout_service_test.dart
git commit -m "$(printf 'refactor(marketplace): simplify CheckoutService to POST /orders only\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Update the checkout screen call site

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart` (the `_placeOrder` method, ~lines 224-237)

- [ ] **Step 1: Update the call site**

In `_placeOrder`, replace this block:

```dart
    final cart = context.read<CartStore>();
    final items = cart.items;
    if (items.isEmpty) return;

    try {
      await CheckoutService().placeOrder(
        items: items,
        paymentMethod: _paymentTitle(method),
      );
    } on CheckoutException catch (e) {
```

with:

```dart
    final cart = context.read<CartStore>();
    if (cart.isEmpty) return;

    try {
      await CheckoutService().placeOrder(
        paymentMethod: _paymentTitle(method),
      );
    } on CheckoutException catch (e) {
```

(The later `cart.clear();` on success stays as-is.)

- [ ] **Step 2: Analyze for unused imports / errors**

Run: `flutter analyze lib/features/marketplace/presentation/checkout_screen.dart`
Expected: No issues. If `cart_item.dart` is now unused in this file, remove its
import; if `CartStore` is still used (it is, via `context.read<CartStore>()`),
keep that import.

- [ ] **Step 3: Run the full suite + analyzer**

Run: `flutter test`
Expected: PASS (all tests, including cart, marketplace, checkout).

Run: `flutter analyze`
Expected: No issues.

- [ ] **Step 4: Commit**

```bash
cd front-end-flutter
git add lib/features/marketplace/presentation/checkout_screen.dart
git commit -m "$(printf 'refactor(checkout): place order from the synced backend cart\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Final Verification

- [ ] `cd front-end-flutter && flutter test` → all green.
- [ ] `cd front-end-flutter && flutter analyze` → no issues.
- [ ] Manual sanity (optional, needs the backend running): add items, kill and
      relaunch the app, open the marketplace → the cart is restored from the
      server. Checkout empties it.

## Notes / Out of Scope

- Backend is unchanged.
- `CartStore.reset()` exists for logout but wiring it into the logout flow is a
  later concern.
- Surfacing `CartStore.errorMessage` as a SnackBar in the marketplace UI is
  optional and not required here; the store self-heals via resync.
- No widget tests for cart UI in this track (covered by unit tests).
