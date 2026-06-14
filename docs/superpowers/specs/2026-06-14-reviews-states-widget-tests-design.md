# Design — Track 3: widget-tests for the reviews states

**Date:** 2026-06-14
**Track:** Marketplace follow-up #3 (reviews state coverage)
**Scope:** Frontend only. No backend, no routing, no API change.

## Problem

`front-end-flutter/lib/features/marketplace/presentation/product_detail_screen.dart`
renders product reviews through a `FutureBuilder<List<Review>>` with four UI
states:

- **Loading** — `'Carregando avaliações...'`
- **Error** — `'Não foi possível carregar as avaliações.'`
- **Empty** — `'Ainda não há avaliações.'`
- **List** — one `ReviewItem` per `Review`

None of these states are covered by tests. The future is built inline in the
private `_ProductContent.initState`:

```dart
_reviewsFuture = ProductService().fetchReviews(widget.product.id);
```

Because `ProductService()` is instantiated inline and `_ProductContent` is
private, the reviews source cannot be faked, so the four states cannot be
driven from a widget test.

## Approach

Make the reviews service injectable by following the codebase's established
**Screen/View split** convention (`MarketplaceScreen`/`MarketplaceView`,
`OrdersScreen`/`OrdersView`): a route-wrapper `Screen` that wires dependencies,
and a public `View` widget that holds the testable UI.

### Production change — `product_detail_screen.dart`

1. Promote the private `_ProductContent` to a public `ProductDetailView`:

   ```dart
   class ProductDetailView extends StatefulWidget {
     const ProductDetailView({super.key, required this.product, this.service});

     final Product product;
     final ProductService? service;
   }
   ```

   In `initState`, default the service so production behavior is unchanged:

   ```dart
   _reviewsFuture =
       (widget.service ?? ProductService()).fetchReviews(widget.product.id);
   ```

2. `ProductDetailScreen` stays the route entry. It still reads `Product` from
   `ModalRoute.of(context)?.settings.arguments`, still renders `_ProductError`
   for the `null`-product case, and now delegates the body to
   `ProductDetailView(product: product)`.

3. The cart button (`_CartButton`) and add-to-cart bar (`_AddToCartBar`) — the
   only widgets that touch `CartStore` — stay in `ProductDetailScreen`'s
   `Scaffold`, **not** in `ProductDetailView`. Consequence: `ProductDetailView`
   has no `CartStore` dependency, so its tests need no provider wiring.

No change to routing (`pushNamed('/product', arguments: product)` keeps
working), to `ProductService`, or to the backend.

### Test — `test/features/marketplace/product_detail_screen_test.dart`

A fake that mirrors the existing `_FakeService` pattern (extend the real
service, override the one method):

```dart
class _FakeReviews extends ProductService {
  _FakeReviews(this.handler);
  final Future<List<Review>> Function() handler;

  @override
  Future<List<Review>> fetchReviews(String productId) => handler();
}
```

A `_product(...)` helper builds a `Product` fixture. Each test pumps:

```dart
await tester.pumpWidget(
  MaterialApp(home: ProductDetailView(product: _product(), service: fake)),
);
```

Four `testWidgets` cases:

| State | Fake `fetchReviews` returns | Drive | Assert |
|---|---|---|---|
| Loading | a pending `Completer<List<Review>>().future` | `pump()` once | finds `'Carregando avaliações...'` |
| Error | `Future.error(ProductException('x'))` | `pumpAndSettle()` | finds `'Não foi possível carregar as avaliações.'` |
| Empty | `<Review>[]` | `pumpAndSettle()` | finds `'Ainda não há avaliações.'` |
| List | `[Review(...)]` | `pumpAndSettle()` | finds the review's author and comment text |

The loading case leaves the `Completer` uncompleted. A `Completer` creates no
timer, so the test does not fail with a pending-timer error.

## Out of scope

- Testing the `null`-product `_ProductError` path of `ProductDetailScreen`
  (separate from the reviews states; can be added later if wanted).
- Any change to `ProductService`, the reviews endpoint, or the `Review` model.

## Verification

- `flutter test test/features/marketplace` — green.
- `flutter analyze` — clean (no new findings).

## Commits (expected)

1. `refactor(marketplace): extract ProductDetailView for review injection`
2. `test(marketplace): cover the four reviews states`

Executed via subagent-driven-development in an isolated git worktree off `main`.
