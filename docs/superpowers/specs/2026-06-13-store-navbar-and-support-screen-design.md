# Store Navbar + Support Screen — Design

**Date:** 2026-06-13
**Status:** Approved (pending implementation)
**Scope:** Flutter frontend (`front-end-flutter`) only. Backend `/api/support` already exists.

## Problem

When the user enters the store (Loja), the bottom navbar should switch from the
main study layout to a store-focused layout: **Home, Meus Pedidos, Suporte, Loja**.
There is no Suporte (support) screen yet — it should reproduce the chat-based support
screen ("Mentor Edu") already shipped in the Kotlin app (`/home/elias/programming/fiap/edu-kt`).

## Goals

1. Dual-layout bottom navbar that switches by current screen (no global flag).
2. A working chat-based Support screen backed by the existing `/api/support` endpoint.

## Non-goals

- No global "store mode" persistent state / Provider flag.
- No changes to Product detail / Checkout navbars (they currently render no navbar — left as-is).
- No backend changes — `/api/support` (GET list, POST → 201 + full list) already exists.

## Current state

- `lib/features/components/nav_bar.dart` — single stateless `NavBar(currentIndex)`,
  one static `_destinations` list of 5 items, navigates via `Navigator.pushReplacementNamed`.
  `route == null` → "Em breve" snackbar. `currentIndex: -1` → no tab highlighted.
- Call sites: home(0), quiz/report(1), marketplace(4), order-details(4), order-tracking(4),
  notifications(-1), profile(-1). OrdersScreen renders **no** navbar today.
- Networking pattern (mirror order_tracking): `http` package + `TokenStore` bearer auth +
  `ApiConfig.baseUrl`; manual `fromJson`; `ChangeNotifier` provider with loading/success/error.

## Design

### 1. Navbar — dual layout (Approach A: `mode` enum)

Add `enum NavBarMode { main, store }`. `NavBar` gains `final NavBarMode mode` (default `main`)
alongside the existing `currentIndex`. Two static destination lists; `_onTap` and `build`
index into the list selected by `mode`.

| `main` (index → route) | `store` (index → route) |
|---|---|
| 0 Home `/home` | 0 Home `/home` |
| 1 Quiz `/quiz` | 1 Meus Pedidos `/orders` |
| 2 Revisão `null` (em breve) | 2 Suporte `/support` |
| 3 Estudo `null` (em breve) | 3 Loja `/marketplace` |
| 4 Loja `/marketplace` | |

Behavior is purely screen-driven: the navbar a screen renders *is* the source of truth.
Tapping **Loja** → `/marketplace` (renders store navbar). Tapping **Home** from store layout
→ `/home` (renders main navbar). No persistent flag.

**Store-context screens** pass `mode: NavBarMode.store`:
- marketplace_screen → `(store, 3)`
- order_details_screen → `(store, 1)`
- order_tracking_screen → `(store, 1)`
- orders_screen → `(store, 1)` — **add a navbar here** (currently has none)
- support_screen (new) → `(store, 2)`

All other screens keep `mode: main` (the default) — no edits needed beyond the store set.

### 2. Support feature — chat screen (mirrors Kotlin "Mentor Edu")

New feature-first module `lib/features/support/`:

**domain/support_message.dart**
```dart
enum SupportSender { user, support }

class SupportMessage {
  final String id;          // UUID from backend
  final SupportSender sender;
  final String body;
  final DateTime createdAt;
  // factory SupportMessage.fromJson(...) — sender: 'support' => support else user;
  // created_at parsed via DateTime.parse, tolerant of missing/blank.
}
```

**data/support_service.dart**
- `Future<List<SupportMessage>> fetchMessages()` → `GET ${ApiConfig.baseUrl}/support`.
- `Future<List<SupportMessage>> sendMessage(String body)` → `POST ${ApiConfig.baseUrl}/support`
  with JSON `{"body": ...}`; accepts 200 **and 201** as success; returns parsed list.
- Bearer auth via `TokenStore.readAccessToken()`; throws `SupportException('Sessão expirada')`
  when missing. Non-success status → `SupportException` with a friendly message.
- Constructor injects `http.Client` and `TokenStore` for testability (matches OrderService).

**presentation/support_provider.dart**
- `ChangeNotifier`. `enum SupportViewState { loading, success, error }`.
- Fields: `state`, `messages`, `errorMessage`, `sending`.
- `load()` → loading → fetch → success/error.
- `send(String body)` → guards empty/sending; sets `sending=true`, posts, replaces `messages`
  with returned list, `sending=false`; on error keeps existing messages, clears `sending`.

**presentation/support_screen.dart** (route `/support`)
- `ChangeNotifierProvider(create: (_) => SupportProvider()..load())` scoped to the screen
  (matches order_tracking — not a global provider in main.dart).
- Layout (top→bottom): gradient background; header title **"Suporte de Pedidos"** with back button;
  chat panel card; `NavBar(mode: NavBarMode.store, currentIndex: 2)`.
- Chat panel states:
  - loading → centered spinner
  - error → "Não foi possível carregar o chat." + message + "Tentar novamente" (retry)
  - empty → agent-avatar circle + "Olá! Como posso ajudar com seus pedidos hoje?"
  - list → message bubbles, auto-scroll to last
- Bubbles: support = agent avatar + "SUPORTE EDU" purple bold label + body + `HH:mm` time,
  left-aligned; user = body + time, right-aligned. Max width ~280.
- Input bar: multiline (max 4 lines) "Escreva sua mensagem aqui...", circular send button
  (disabled when empty or `sending`, dimmed to 40%). Submit clears field then calls `send`.
- Disclaimer footer: "Mentor Edu pode cometer erros, verifique informações importantes."

**main.dart**
- Register route `'/support': (_) => const SupportScreen()`.
- Provider is screen-scoped; no `MultiProvider` change required.

**Design system**
- Reuse `AppColors` (purple, white, textSecondary) and existing gradient/card widgets.
- Add any missing token (e.g. an input-fill light-gray) to `AppColors` rather than hardcoding.

### Time formatting
Match Kotlin: `HH:mm` in the device local zone. A small helper formats `createdAt`;
blank/invalid → empty string.

## Data contracts (backend, existing)

- `GET /api/support` → `200` `[{ id: uuid, sender: "user"|"support", body: str, created_at: iso }]`
- `POST /api/support` body `{ body: str (1..2000) }` → `201` with full updated list.
- Both require `Authorization: Bearer <access>` (`get_current_user`).

## Testing (TDD)

- `SupportMessage.fromJson`: support/user mapping, UUID id, date parsing, missing fields.
- `SupportService`: GET maps list; POST sends `{body}`, accepts 201, maps list; 401/missing
  token → `SupportException`; non-success → `SupportException` (mocked `http.Client`).
- `SupportProvider`: load success/error transitions; send guards (empty, while sending),
  success replaces list, error keeps list and clears `sending`.
- `NavBar`: renders main items in `main` mode and store items (Home/Meus Pedidos/Suporte/Loja)
  in `store` mode; tapping a store item with `index != currentIndex` navigates to its route;
  `null` route shows "Em breve".

## Risks / open items

- `ApiConfig.baseUrl` (`:8001/api`) must route `/support` to the support module the same way
  it serves `/orders` and `/auth`. Other features hit it directly, so assumed fine — confirm
  during manual verification.
