# Reviews-States Widget Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the product-detail reviews source injectable and cover its four UI states (loading, error, empty, list) with widget tests.

**Architecture:** Apply the codebase's Screen/View split. Extract the private `_ProductContent` in `product_detail_screen.dart` into a public `ProductDetailView` that accepts an optional `ProductService`, defaulting to `ProductService()` so production behavior is unchanged. `ProductDetailScreen` stays the route wrapper (reads `Product` from `ModalRoute`, keeps the cart widgets and the null-product error path). Then drive the four states from widget tests with a fake service.

**Tech Stack:** Flutter / Dart, `flutter_test`, `package:provider` (not needed by the View tests — the cart widgets stay in the Screen). Fakes via `extends ProductService` + method override, matching the existing `_FakeService` pattern.

---

## File Structure

- **Modify:** `front-end-flutter/lib/features/marketplace/presentation/product_detail_screen.dart`
  - Promote private `_ProductContent` → public `ProductDetailView({required Product product, ProductService? service})`.
  - `ProductDetailScreen.build` delegates its body to `ProductDetailView(product: product)`.
- **Create:** `front-end-flutter/test/features/marketplace/product_detail_screen_test.dart`
  - `_FakeReviews extends ProductService`, a `_product(...)` fixture helper, four `testWidgets` cases.

All commands run from `front-end-flutter/`.

---

### Task 1: Extract `ProductDetailView` (injectable reviews service)

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/presentation/product_detail_screen.dart`

This is a pure refactor (no behavior change), so the test is the existing suite staying green plus `flutter analyze` staying clean. The new behavior (injection) is exercised by Task 2's tests.

- [ ] **Step 1: Rename the private content widget to a public, injectable View**

In `product_detail_screen.dart`, replace the `_ProductContent` widget and its state (lines ~49–202) with `ProductDetailView`. The only behavioral change is the optional `service` field and using it in `initState`:

```dart
class ProductDetailView extends StatefulWidget {
  final Product product;
  final ProductService? service;

  const ProductDetailView({super.key, required this.product, this.service});

  @override
  State<ProductDetailView> createState() => _ProductDetailViewState();
}

class _ProductDetailViewState extends State<ProductDetailView> {
  late final Future<List<Review>> _reviewsFuture;

  @override
  void initState() {
    super.initState();
    _reviewsFuture =
        (widget.service ?? ProductService()).fetchReviews(widget.product.id);
  }

  // build() body is unchanged from the old _ProductContentState.build,
  // including the FutureBuilder<List<Review>> and its four states.
```

Keep the entire `build` method body exactly as it was in `_ProductContentState` (the `SafeArea` → `ListView` → hero/cards/`FutureBuilder` tree).

- [ ] **Step 2: Point the route wrapper at the new View**

In `ProductDetailScreen.build`, update the body delegation (was `_ProductContent(product: product)`):

```dart
body: product == null
    ? const _ProductError()
    : ProductDetailView(product: product),
```

Leave the `appBar` (`_CartButton`), `bottomNavigationBar` (`_AddToCartBar`), and the `_ProductError` null-product path unchanged — the cart widgets stay in the Screen.

- [ ] **Step 3: Run analyze to confirm no dangling references**

Run: `flutter analyze`
Expected: no new findings (one pre-existing `withOpacity` info in `quiz_screen.dart:160` may remain — unrelated). Confirm there is no remaining reference to `_ProductContent`.

- [ ] **Step 4: Run the existing suite to confirm the refactor is behavior-preserving**

Run: `flutter test`
Expected: PASS (same count as before — 85 — no test referenced `_ProductContent`).

- [ ] **Step 5: Commit**

```bash
git add lib/features/marketplace/presentation/product_detail_screen.dart
git commit -m "refactor(marketplace): extract ProductDetailView for review injection"
```

---

### Task 2: Widget tests for the four reviews states

**Files:**
- Create: `front-end-flutter/test/features/marketplace/product_detail_screen_test.dart`

- [ ] **Step 1: Write the failing tests**

Create `test/features/marketplace/product_detail_screen_test.dart` with the full content below. `_FakeReviews` extends the real service and overrides only `fetchReviews` (mirrors the existing `_FakeService` in `marketplace_screen_test.dart`). The loading case returns a never-completed `Completer.future` — a `Completer` schedules no timer, so the test does not trip the pending-timer check.

```dart
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
}
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `flutter test test/features/marketplace/product_detail_screen_test.dart`
Expected: PASS — 4 tests. (If `ProductDetailView` is not exported/public, this fails to compile — that means Task 1 was not completed.)

- [ ] **Step 3: Run the marketplace suite and analyze**

Run: `flutter test test/features/marketplace` then `flutter analyze`
Expected: all green; analyze clean (only the pre-existing unrelated info, if any).

- [ ] **Step 4: Commit**

```bash
git add test/features/marketplace/product_detail_screen_test.dart
git commit -m "test(marketplace): cover the four reviews states"
```

---

## Self-Review

**Spec coverage:**
- Injectable service via Screen/View split → Task 1. ✓
- Loading / Error / Empty / List asserts → Task 2 (four cases matching the spec table). ✓
- Cart widgets stay in the Screen so the View needs no provider → Task 1 Step 2 (appBar/bottomNavigationBar untouched); harness in Task 2 uses no provider. ✓
- Out-of-scope (null-product path, `ProductService`/endpoint/model untouched) → respected; no task changes them. ✓
- Verification (`flutter test`, `flutter analyze`) → Task 1 Steps 3–4, Task 2 Steps 2–3. ✓

**Placeholder scan:** none — all code and commands are concrete.

**Type consistency:** `ProductDetailView({required Product product, ProductService? service})` used identically in Task 1 (definition) and Task 2 (`_harness`). `fetchReviews(String productId)` matches the real signature in `product_service.dart`. `Review(id, author, rating, comment, createdAt)` matches `domain/product.dart`. `Product(...)` fixture uses only real required/optional fields. ✓
