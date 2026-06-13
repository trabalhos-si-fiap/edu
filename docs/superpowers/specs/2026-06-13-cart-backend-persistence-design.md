# Cart Backend Persistence — Design

**Date:** 2026-06-13
**Track:** 1 of 3 (marketplace follow-ups)
**Status:** Approved design — pending spec review

## Problem

The Flutter `CartStore` (`features/cart/data/cart_store.dart`) is an in-memory
`ChangeNotifier`. The working cart is lost on every app restart. The backend
already has a complete, per-user cart CRUD; the frontend only uses it as a
transient staging area during checkout. We want the backend cart to be the
**source of truth** for the working cart, so it persists across restarts (and,
as a free consequence, across devices).

## Current State (verified)

- **Backend cart is complete and committed** (`app/modules/cart/`):
  - Models `Cart` (one per `user_id`) and `CartItem` (`cart_id` + `product_id`
    unique, `quantity > 0`).
  - Endpoints: `GET /cart`, `POST /cart/items` (sums quantity, `quantity` in
    `[1, 999]`), `DELETE /cart/items/{product_id}?quantity=N` (decrement by N, or
    remove the line when `quantity` is omitted or `>=` current).
  - Auth/ownership via `Depends(get_current_user)`; cart-row `with_for_update`
    makes the read→write atomic; product existence validated server-side.
  - Router wired in `app/main.py`; migration `57b1073cc5f3`; tests under
    `tests/modules/cart`.
- **`POST /orders`** (`create_order_from_cart`) reads the backend cart, builds
  the order, and **empties the cart in the same locked transaction**. The
  backend cart is already designed to be the checkout source of truth.
- **Frontend** keeps an in-memory `CartStore`; at checkout `CheckoutService`
  mirrors local → backend (clears item-by-item, then re-posts each item) before
  `POST /orders`. This staging is what we will remove.

`CartOut` item shape (from `cart/schemas.py`): `product_id, name, type, subtype,
price, quantity, subtotal, image_url, rating_avg, rating_count`. This is enough
to reconstruct a frontend `Product` (only `description` is missing → defaults to
`''`, which the cart UI does not use).

## Scope

Frontend-only. **No backend changes.** Two decisions locked with the user:

1. **Optimistic + write-through** sync strategy.
2. **Include the `CheckoutService` simplification** (drop the staging dance).

## Architecture

### 1. `CartService` — new (`features/cart/data/cart_service.dart`)

Follows the existing service pattern (`ProductService`, `CheckoutService`):
injectable `http.Client? client` + `TokenStore? tokenStore`, a `CartException`
with a friendly message, and a private `_send` helper for status handling and
auth headers (mirror `CheckoutService._send` / `_headers`).

API (every method returns the full cart as the server sees it):

```dart
Future<List<CartItem>> fetch();                                  // GET /cart
Future<List<CartItem>> addItem(String productId, int quantity);  // POST /cart/items
Future<List<CartItem>> removeItem(String productId, {int? quantity}); // DELETE /cart/items/{id}[?quantity=N]
```

- Parses `CartOut` → maps each item to `CartItem(Product(...), quantity)`.
  `Product` is built from the response fields; `description` defaults to `''`.
- Accepts `{200, 201}` where the backend may return either (POST returns 201).
- Auth: `Authorization: Bearer <access>`; missing token → `CartException`
  ('Sessão expirada. Entre novamente.'), consistent with sibling services.

### 2. `CartStore` — backend-backed (`features/cart/data/cart_store.dart`)

Constructor takes an injectable `CartService` (`CartStore({CartService? service})`)
for testability, defaulting to `CartService()`.

State additions:
- `bool isLoading` / `String? errorMessage` exposed for the UI (soft error).
- `bool _loaded` guard so `load()` runs at most once per session unless forced.

Methods (optimistic + write-through):

- `Future<void> load({bool force = false})` — guarded; `GET /cart`, replace
  `_items`, `notifyListeners()`. No-ops when already loaded (unless `force`). On
  error: set `errorMessage`, leave items as-is.
- `void add(Product product, [int quantity = 1])` — **optimistic**: update
  `_items` locally and `notifyListeners()` immediately (instant +/- UX), then
  fire `service.addItem(...)` in the background.
- `void decrement(String productId)` — optimistic local decrement, then fire
  `service.removeItem(id, quantity: 1)`.
- `void removeAll(String productId)` — optimistic local removal, then fire
  `service.removeItem(id)` (no quantity).
- `void clear()` — local clear + notify only. `POST /orders` already emptied the
  server cart at checkout; no API call needed.
- `void reset()` — clear local state and `_loaded` (for logout); wiring into the
  logout flow is optional and noted, not required for this track.

**Concurrency rule (locked):** on a successful mutation we do **not** overwrite
local state with the response — the optimistic state already reflects the intent
and avoids an older response clobbering a newer tap. On **failure**, call
`load(force: true)` to resync from the server and set `errorMessage`. This makes
the store self-healing without race-prone response merging.

Mutations stay **synchronous (void)** from the UI's perspective (fire-and-forget
background `Future`), so existing call sites
(`context.read<CartStore>().add(...)`) are unchanged.

### 3. Load trigger

`MarketplaceScreen` calls `context.read<CartStore>().load()` in `initState`
(guard makes it idempotent). This is the entry point to shopping and runs after
login, so the token is available. The cart badge/count then reflects the server
cart on a fresh launch.

### 4. `CheckoutService` simplification

`placeOrder` drops `_clearBackendCart` and the per-item re-post loop. Since the
backend cart is now always in sync with `CartStore`, checkout is just:

```dart
POST /orders {payment_method}  →  returns order id
```

`items` parameter is removed from `placeOrder` (the server reads its own cart).
`checkout_screen` still calls `cart.clear()` after a successful order to zero the
local view (server already emptied it).

## Data Flow

```
App launch → MarketplaceScreen.initState → CartStore.load() → GET /cart → items
Tap "+"    → CartStore.add() → local update + notify → (bg) POST /cart/items
Tap "-"    → CartStore.decrement() → local update + notify → (bg) DELETE .../{id}?quantity=1
Remove     → CartStore.removeAll() → local update + notify → (bg) DELETE .../{id}
On bg error→ CartStore.load(force:true) → resync + errorMessage
Checkout   → CheckoutService.placeOrder() → POST /orders (server reads+empties cart)
           → CartStore.clear() (local only)
```

## Error Handling

- Network/parse errors in `CartService` → `CartException` with a friendly
  message.
- `CartStore` mutation failures are non-fatal: the optimistic UI stays, then a
  background `load(force: true)` resyncs and sets `errorMessage`. The marketplace
  may surface `errorMessage` as a soft, non-blocking hint (e.g., SnackBar); a
  blocking error UI is not required.
- `load()` failure on launch leaves an empty cart and sets `errorMessage`;
  shopping still works (next mutation re-attempts a sync).

## Testing (TDD)

Unit tests only — no widget tests in this track.

- **`test/features/cart/cart_service_test.dart`** — `MockClient` (`http` package
  `MockClient`) feeding canned `CartOut` JSON:
  - `fetch` maps items → `CartItem`s with correct product fields and quantities.
  - `addItem`/`removeItem` send the right method/URL/body and parse the response.
  - Non-2xx → `CartException`; missing token → `CartException`.
- **`test/features/cart/cart_store_test.dart`** — fake `CartService`:
  - `load` populates items and is guarded (second call no-ops without `force`).
  - `add`/`decrement`/`removeAll` update local state immediately (optimistic) and
    invoke the matching service call.
  - On service error, store calls `load(force: true)` and sets `errorMessage`.
  - `clear` zeroes local state without calling the service.
- **`test/features/marketplace/checkout_service_test.dart`** (existing) — update
  for the simplified flow: `placeOrder` issues only `POST /orders` and no longer
  GETs/clears the cart.

## Out of Scope

- Backend changes (the cart CRUD is complete).
- Multi-device live sync / real-time cart updates.
- Logout-triggered `reset()` wiring (method provided; wiring is a later concern).
- A dedicated cart screen redesign.

## Commit Sequence (Conventional Commits)

1. `test(cart): add CartService tests`
2. `feat(cart): add CartService for the backend cart API`
3. `test(cart): add backend-backed CartStore tests`
4. `refactor(cart): back CartStore with CartService (optimistic write-through)`
5. `feat(marketplace): load the cart on marketplace launch`
6. `refactor(marketplace): simplify CheckoutService to POST /orders only`
7. `test(marketplace): update CheckoutService tests for the simplified flow`
