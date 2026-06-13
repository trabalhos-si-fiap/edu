# Store Navbar + Support Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a store-context bottom navbar layout (Home · Meus Pedidos · Suporte · Loja) that appears on store screens, plus a new chat-based Support screen backed by the existing `/api/support` endpoint.

**Architecture:** The `NavBar` widget gains a `NavBarMode` enum (`main`/`store`) selecting one of two static destination lists — layout is driven entirely by which screen renders the navbar (no global state). The Support feature is a new feature-first module (`domain`/`data`/`presentation`) mirroring the existing `order_tracking` patterns: `http` + `TokenStore` bearer auth, manual `fromJson`, a `ChangeNotifier` provider scoped to the screen.

**Tech Stack:** Flutter/Dart, `http` package, `flutter_secure_storage` (via `TokenStore`), `provider`, `flutter_test` + `package:http/testing.dart` (`MockClient`).

---

## File Structure

- **Create** `lib/features/support/domain/support_message.dart` — `SupportSender` enum, `SupportMessage` model + `fromJson`, `formatMessageTime` helper.
- **Create** `lib/features/support/data/support_service.dart` — `SupportException`, `SupportService` (GET/POST `/support`).
- **Create** `lib/features/support/presentation/support_provider.dart` — `SupportViewState` enum, `SupportProvider` (`ChangeNotifier`).
- **Create** `lib/features/support/presentation/support_screen.dart` — chat UI at route `/support`.
- **Modify** `lib/features/components/nav_bar.dart` — add `NavBarMode`, two destination lists.
- **Modify** `lib/main.dart` — register `/support` route.
- **Modify** store screens to pass `mode: NavBarMode.store` (marketplace, order_details, order_tracking) and add a navbar to `orders_screen`.
- **Create** tests under `test/features/support/` and `test/features/components/`.

Package name is `edu_ia` (imports use `package:edu_ia/...`). All test commands run from `front-end-flutter/`.

---

### Task 1: NavBar dual-layout

**Files:**
- Modify: `lib/features/components/nav_bar.dart`
- Test: `test/features/components/nav_bar_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/components/nav_bar_test.dart`:

```dart
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _wrap(Widget child) => MaterialApp(
      home: Scaffold(bottomNavigationBar: child),
    );

void main() {
  testWidgets('main mode shows the study layout', (tester) async {
    await tester.pumpWidget(_wrap(const NavBar(currentIndex: 0)));

    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Quiz'), findsOneWidget);
    expect(find.text('Revisão'), findsOneWidget);
    expect(find.text('Estudo'), findsOneWidget);
    expect(find.text('Loja'), findsOneWidget);
    expect(find.text('Meus Pedidos'), findsNothing);
    expect(find.text('Suporte'), findsNothing);
  });

  testWidgets('store mode shows the store layout', (tester) async {
    await tester.pumpWidget(
      _wrap(const NavBar(mode: NavBarMode.store, currentIndex: 2)),
    );

    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Meus Pedidos'), findsOneWidget);
    expect(find.text('Suporte'), findsOneWidget);
    expect(find.text('Loja'), findsOneWidget);
    expect(find.text('Quiz'), findsNothing);
    expect(find.text('Revisão'), findsNothing);
  });

  testWidgets('mode defaults to main', (tester) async {
    await tester.pumpWidget(_wrap(const NavBar(currentIndex: 1)));
    expect(find.text('Quiz'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/components/nav_bar_test.dart`
Expected: FAIL — `NavBarMode` undefined / `mode` named param does not exist.

- [ ] **Step 3: Write the implementation**

Replace the entire contents of `lib/features/components/nav_bar.dart`:

```dart
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';

/// Layout de abas exibido pela [NavBar].
///
/// [main] é o app de estudos; [store] é o contexto de loja/pedidos.
enum NavBarMode { main, store }

/// Barra de navegação principal do app.
///
/// Centraliza itens, rotas e a navegação em si — cada tela informa qual layout
/// usar via [mode] e qual item está ativo via [currentIndex]. Telas que não são
/// uma aba (ex.: perfil) podem passar `currentIndex: -1`.
class NavBar extends StatelessWidget {
  final int currentIndex;
  final NavBarMode mode;

  const NavBar({
    super.key,
    required this.currentIndex,
    this.mode = NavBarMode.main,
  });

  /// Destinos por layout. `route == null` marca tela ainda não implementada.
  static const Map<NavBarMode, List<({IconData icon, String label, String? route})>>
  _layouts = {
    NavBarMode.main: [
      (icon: Icons.home_rounded, label: 'Home', route: '/home'),
      (icon: Icons.quiz_outlined, label: 'Quiz', route: '/quiz'),
      (icon: Icons.assignment_turned_in_outlined, label: 'Revisão', route: null),
      (icon: Icons.menu_book_outlined, label: 'Estudo', route: null),
      (
        icon: Icons.store_mall_directory_outlined,
        label: 'Loja',
        route: '/marketplace',
      ),
    ],
    NavBarMode.store: [
      (icon: Icons.home_rounded, label: 'Home', route: '/home'),
      (
        icon: Icons.receipt_long_outlined,
        label: 'Meus Pedidos',
        route: '/orders',
      ),
      (icon: Icons.support_agent_outlined, label: 'Suporte', route: '/support'),
      (
        icon: Icons.store_mall_directory_outlined,
        label: 'Loja',
        route: '/marketplace',
      ),
    ],
  };

  List<({IconData icon, String label, String? route})> get _destinations =>
      _layouts[mode]!;

  void _onTap(BuildContext context, int index) {
    if (index == currentIndex) return;
    final route = _destinations[index].route;
    if (route == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Em breve')),
      );
      return;
    }
    Navigator.pushReplacementNamed(context, route);
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      child: BottomNavigationBar(
        // BottomNavigationBar exige um índice válido; telas fora das abas
        // (currentIndex < 0) não destacam nenhum item de forma efetiva.
        currentIndex: currentIndex < 0 ? 0 : currentIndex,
        onTap: (index) => _onTap(context, index),
        backgroundColor: AppColors.white,
        selectedItemColor: AppColors.purple,
        unselectedItemColor: AppColors.textSecondary,
        type: BottomNavigationBarType.fixed,
        items: [
          for (final d in _destinations)
            BottomNavigationBarItem(icon: Icon(d.icon), label: d.label),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/components/nav_bar_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/components/nav_bar.dart test/features/components/nav_bar_test.dart
git commit -m "feat(navbar): add store layout mode to NavBar"
```

---

### Task 2: SupportMessage model + time formatting

**Files:**
- Create: `lib/features/support/domain/support_message.dart`
- Test: `test/features/support/support_message_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/support/support_message_test.dart`:

```dart
import 'package:edu_ia/features/support/domain/support_message.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fromJson maps a support message', () {
    final msg = SupportMessage.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'sender': 'support',
      'body': 'Olá!',
      'created_at': '2026-06-13T12:30:00Z',
    });

    expect(msg.id, '11111111-1111-1111-1111-111111111111');
    expect(msg.sender, SupportSender.support);
    expect(msg.body, 'Olá!');
    expect(msg.createdAt, DateTime.parse('2026-06-13T12:30:00Z'));
  });

  test('fromJson treats any non-support sender as user', () {
    final msg = SupportMessage.fromJson({
      'id': 'x',
      'sender': 'user',
      'body': 'oi',
      'created_at': '2026-06-13T12:30:00Z',
    });
    expect(msg.sender, SupportSender.user);
  });

  test('fromJson tolerates missing/blank fields', () {
    final msg = SupportMessage.fromJson({});
    expect(msg.id, '');
    expect(msg.sender, SupportSender.user);
    expect(msg.body, '');
    expect(msg.createdAt, isNull);
  });

  test('formatMessageTime renders HH:mm and empty for null', () {
    final t = DateTime(2026, 6, 13, 9, 5);
    expect(formatMessageTime(t), '09:05');
    expect(formatMessageTime(null), '');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/support/support_message_test.dart`
Expected: FAIL — target of URI doesn't exist (`support_message.dart`).

- [ ] **Step 3: Write the implementation**

Create `lib/features/support/domain/support_message.dart`:

```dart
/// Quem enviou a mensagem de suporte.
enum SupportSender { user, support }

/// Mensagem do chat de suporte ("Mentor Edu").
///
/// Espelha `SupportMessageOut` do backend: `id` é UUID (string), `sender` é
/// `"user"` ou `"support"`, `created_at` é ISO-8601.
class SupportMessage {
  final String id;
  final SupportSender sender;
  final String body;
  final DateTime? createdAt;

  const SupportMessage({
    required this.id,
    required this.sender,
    required this.body,
    required this.createdAt,
  });

  factory SupportMessage.fromJson(Map<String, dynamic> json) {
    final created = json['created_at'] as String?;
    return SupportMessage(
      id: (json['id'] as String?) ?? '',
      sender: (json['sender'] as String?) == 'support'
          ? SupportSender.support
          : SupportSender.user,
      body: (json['body'] as String?) ?? '',
      createdAt: (created == null || created.isEmpty)
          ? null
          : DateTime.tryParse(created),
    );
  }
}

/// Formata o horário da mensagem como `HH:mm` no fuso local.
/// Retorna string vazia quando não há data.
String formatMessageTime(DateTime? time) {
  if (time == null) return '';
  final local = time.toLocal();
  final hh = local.hour.toString().padLeft(2, '0');
  final mm = local.minute.toString().padLeft(2, '0');
  return '$hh:$mm';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/support/support_message_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/support/domain/support_message.dart test/features/support/support_message_test.dart
git commit -m "feat(support): add SupportMessage model and time formatting"
```

---

### Task 3: SupportService (HTTP)

**Files:**
- Create: `lib/features/support/data/support_service.dart`
- Test: `test/features/support/support_service_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/support/support_service_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/support/data/support_service.dart';
import 'package:edu_ia/features/support/domain/support_message.dart';
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

final _list = [
  {
    'id': 'a',
    'sender': 'user',
    'body': 'oi',
    'created_at': '2026-06-13T12:00:00Z',
  },
  {
    'id': 'b',
    'sender': 'support',
    'body': 'olá',
    'created_at': '2026-06-13T12:01:00Z',
  },
];

void main() {
  test('fetchMessages parses the list and sends bearer token', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_list), 200);
    });

    final service =
        SupportService(client: client, tokenStore: _FakeTokenStore());
    final messages = await service.fetchMessages();

    expect(messages, hasLength(2));
    expect(messages[1].sender, SupportSender.support);
    expect(captured.method, 'GET');
    expect(captured.url.path, endsWith('/support'));
    expect(captured.headers['Authorization'], 'Bearer fake-token');
  });

  test('sendMessage posts the body and accepts 201', () async {
    late http.Request captured;
    final client = MockClient((req) async {
      captured = req;
      return http.Response(jsonEncode(_list), 201);
    });

    final service =
        SupportService(client: client, tokenStore: _FakeTokenStore());
    final messages = await service.sendMessage('preciso de ajuda');

    expect(messages, hasLength(2));
    expect(captured.method, 'POST');
    expect(jsonDecode(captured.body), {'body': 'preciso de ajuda'});
    expect(captured.headers['Content-Type'], contains('application/json'));
  });

  test('throws SupportException on non-success status', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final service =
        SupportService(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => service.fetchMessages(),
      throwsA(isA<SupportException>()),
    );
  });

  test('throws SupportException when there is no token', () async {
    final client = MockClient((req) async => http.Response('[]', 200));
    final service =
        SupportService(client: client, tokenStore: _NullTokenStore());

    expect(
      () => service.fetchMessages(),
      throwsA(isA<SupportException>()),
    );
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/support/support_service_test.dart`
Expected: FAIL — `support_service.dart` does not exist.

- [ ] **Step 3: Write the implementation**

Create `lib/features/support/data/support_service.dart`:

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/support_message.dart';

/// Lançada quando uma operação de suporte falha; carrega mensagem amigável
/// pronta para exibir ao usuário.
class SupportException implements Exception {
  SupportException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP do chat de suporte (`GET /support`, `POST /support`).
///
/// Ambos os endpoints retornam a lista completa de mensagens do usuário
/// autenticado. O envio aceita `200` e `201` como sucesso.
class SupportService {
  SupportService({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<List<SupportMessage>> fetchMessages() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/support');
    final http.Response res;
    try {
      res = await _client.get(uri, headers: await _headers());
    } on SupportException {
      rethrow;
    } on Exception {
      throw SupportException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw SupportException('Falha ao carregar o chat (${res.statusCode})');
    }
    return _parseList(res.body);
  }

  Future<List<SupportMessage>> sendMessage(String body) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/support');
    final http.Response res;
    try {
      res = await _client.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          ...await _headers(),
        },
        body: jsonEncode({'body': body}),
      );
    } on SupportException {
      rethrow;
    } on Exception {
      throw SupportException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw SupportException('Falha ao enviar a mensagem (${res.statusCode})');
    }
    return _parseList(res.body);
  }

  List<SupportMessage> _parseList(String body) {
    final list = jsonDecode(body) as List<dynamic>;
    return list
        .map((e) => SupportMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, String>> _headers() async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw SupportException('Sessão expirada. Entre novamente.');
    }
    return {'Authorization': 'Bearer $access'};
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/support/support_service_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/support/data/support_service.dart test/features/support/support_service_test.dart
git commit -m "feat(support): add SupportService HTTP client"
```

---

### Task 4: SupportProvider (state)

**Files:**
- Create: `lib/features/support/presentation/support_provider.dart`
- Test: `test/features/support/support_provider_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/support/support_provider_test.dart`:

```dart
import 'package:edu_ia/features/support/data/support_service.dart';
import 'package:edu_ia/features/support/domain/support_message.dart';
import 'package:edu_ia/features/support/presentation/support_provider.dart';
import 'package:flutter_test/flutter_test.dart';

SupportMessage _msg(String id, SupportSender sender, String body) =>
    SupportMessage(id: id, sender: sender, body: body, createdAt: null);

/// Service de teste com comportamento configurável (sem rede).
class _FakeService extends SupportService {
  _FakeService({
    this.onList,
    this.onSend,
  });

  Future<List<SupportMessage>> Function()? onList;
  Future<List<SupportMessage>> Function(String body)? onSend;

  @override
  Future<List<SupportMessage>> fetchMessages() =>
      onList?.call() ?? Future.value(const []);

  @override
  Future<List<SupportMessage>> sendMessage(String body) =>
      onSend?.call(body) ?? Future.value(const []);
}

void main() {
  test('load success populates messages', () async {
    final service = _FakeService(
      onList: () async => [_msg('a', SupportSender.support, 'olá')],
    );
    final provider = SupportProvider(service: service);

    await provider.load();

    expect(provider.state, SupportViewState.success);
    expect(provider.messages, hasLength(1));
  });

  test('load failure sets error state', () async {
    final service = _FakeService(
      onList: () async => throw SupportException('boom'),
    );
    final provider = SupportProvider(service: service);

    await provider.load();

    expect(provider.state, SupportViewState.error);
    expect(provider.errorMessage, 'boom');
  });

  test('send replaces messages with the returned list', () async {
    final service = _FakeService(
      onList: () async => [_msg('a', SupportSender.user, 'oi')],
      onSend: (body) async => [
        _msg('a', SupportSender.user, 'oi'),
        _msg('b', SupportSender.support, 'resposta'),
      ],
    );
    final provider = SupportProvider(service: service);
    await provider.load();

    await provider.send('oi de novo');

    expect(provider.messages, hasLength(2));
    expect(provider.sending, isFalse);
  });

  test('send ignores empty/blank input', () async {
    var called = false;
    final service = _FakeService(
      onList: () async => const [],
      onSend: (body) async {
        called = true;
        return const [];
      },
    );
    final provider = SupportProvider(service: service);
    await provider.load();

    await provider.send('   ');

    expect(called, isFalse);
  });

  test('send failure keeps existing messages and clears sending', () async {
    final service = _FakeService(
      onList: () async => [_msg('a', SupportSender.user, 'oi')],
      onSend: (body) async => throw SupportException('falhou'),
    );
    final provider = SupportProvider(service: service);
    await provider.load();

    await provider.send('tentativa');

    expect(provider.messages, hasLength(1));
    expect(provider.sending, isFalse);
    expect(provider.errorMessage, 'falhou');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/support/support_provider_test.dart`
Expected: FAIL — `support_provider.dart` does not exist.

- [ ] **Step 3: Write the implementation**

Create `lib/features/support/presentation/support_provider.dart`:

```dart
import 'package:flutter/foundation.dart';

import '../data/support_service.dart';
import '../domain/support_message.dart';

enum SupportViewState { loading, success, error }

/// Estado do chat de suporte: carrega o histórico e envia novas mensagens.
class SupportProvider extends ChangeNotifier {
  SupportProvider({SupportService? service})
    : _service = service ?? SupportService();

  final SupportService _service;

  SupportViewState _state = SupportViewState.loading;
  List<SupportMessage> _messages = const [];
  String? _errorMessage;
  bool _sending = false;

  SupportViewState get state => _state;
  List<SupportMessage> get messages => _messages;
  String? get errorMessage => _errorMessage;
  bool get sending => _sending;

  Future<void> load() async {
    _state = SupportViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _messages = await _service.fetchMessages();
      _state = SupportViewState.success;
    } on SupportException catch (e) {
      _errorMessage = e.message;
      _state = SupportViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = SupportViewState.error;
    }
    notifyListeners();
  }

  Future<void> send(String body) async {
    final text = body.trim();
    if (text.isEmpty || _sending) return;

    _sending = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _messages = await _service.sendMessage(text);
    } on SupportException catch (e) {
      _errorMessage = e.message;
    } catch (_) {
      _errorMessage = 'Não foi possível enviar a mensagem.';
    } finally {
      _sending = false;
      notifyListeners();
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/support/support_provider_test.dart`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/features/support/presentation/support_provider.dart test/features/support/support_provider_test.dart
git commit -m "feat(support): add SupportProvider state management"
```

---

### Task 5: SupportScreen UI + route registration

**Files:**
- Create: `lib/features/support/presentation/support_screen.dart`
- Modify: `lib/main.dart`
- Test: `test/features/support/support_screen_test.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/support/support_screen_test.dart`:

```dart
import 'package:edu_ia/features/support/data/support_service.dart';
import 'package:edu_ia/features/support/domain/support_message.dart';
import 'package:edu_ia/features/support/presentation/support_provider.dart';
import 'package:edu_ia/features/support/presentation/support_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _FakeService extends SupportService {
  _FakeService(this.messages);
  final List<SupportMessage> messages;

  @override
  Future<List<SupportMessage>> fetchMessages() async => messages;

  @override
  Future<List<SupportMessage>> sendMessage(String body) async => messages;
}

Widget _harness(SupportProvider provider) => MaterialApp(
      home: ChangeNotifierProvider.value(
        value: provider,
        child: const SupportView(),
      ),
    );

void main() {
  testWidgets('shows empty greeting when there are no messages',
      (tester) async {
    final provider = SupportProvider(service: _FakeService(const []));
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(
      find.text('Olá! Como posso ajudar com seus pedidos hoje?'),
      findsOneWidget,
    );
  });

  testWidgets('renders message bubbles', (tester) async {
    final provider = SupportProvider(
      service: _FakeService([
        SupportMessage(
          id: 'a',
          sender: SupportSender.support,
          body: 'Posso ajudar com seu pedido?',
          createdAt: null,
        ),
      ]),
    );
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(find.text('Posso ajudar com seu pedido?'), findsOneWidget);
    expect(find.text('SUPORTE EDU'), findsOneWidget);
  });
}
```

> Note: the test targets a `SupportView` widget (the screen body that consumes
> an already-provided `SupportProvider`). `SupportScreen` is the route entry that
> wraps `SupportView` in its own `ChangeNotifierProvider`. This split keeps the UI
> testable without hitting the network.

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/support/support_screen_test.dart`
Expected: FAIL — `support_screen.dart` / `SupportView` does not exist.

- [ ] **Step 3: Write the implementation**

Create `lib/features/support/presentation/support_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../../components/nav_bar.dart';
import '../domain/support_message.dart';
import 'support_provider.dart';

/// Entrada de rota do chat de suporte. Cria o [SupportProvider] e dispara o
/// carregamento inicial; a UI vive em [SupportView] para facilitar testes.
class SupportScreen extends StatelessWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => SupportProvider()..load(),
      child: const SupportView(),
    );
  }
}

/// Corpo do chat de suporte. Espera um [SupportProvider] já disponível.
class SupportView extends StatelessWidget {
  const SupportView({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        resizeToAvoidBottomInset: true,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          centerTitle: true,
          leading: IconButton(
            onPressed: () => Navigator.maybePop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
          title: const Text(
            'Suporte de Pedidos',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 2,
        ),
        body: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Consumer<SupportProvider>(
              builder: (context, provider, _) {
                switch (provider.state) {
                  case SupportViewState.loading:
                    return const Center(
                      child: CircularProgressIndicator(color: AppColors.purple),
                    );
                  case SupportViewState.error:
                    return _ErrorView(
                      message: provider.errorMessage ?? 'Erro desconhecido.',
                      onRetry: provider.load,
                    );
                  case SupportViewState.success:
                    return _ChatPanel(provider: provider);
                }
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Não foi possível carregar o chat.',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: onRetry,
            child: const Text(
              'Tentar novamente',
              style: TextStyle(color: AppColors.purple),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatPanel extends StatelessWidget {
  const _ChatPanel({required this.provider});

  final SupportProvider provider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: AppColors.inputFill,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.04),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: provider.messages.isEmpty
                ? const _EmptyState()
                : _MessageList(messages: provider.messages),
          ),
        ),
        const SizedBox(height: 8),
        _InputBar(
          sending: provider.sending,
          onSend: provider.send,
        ),
        const _Disclaimer(),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: const BoxDecoration(
                color: AppColors.primary,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.support_agent,
                color: AppColors.white,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Olá! Como posso ajudar com seus pedidos hoje?',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageList extends StatefulWidget {
  const _MessageList({required this.messages});

  final List<SupportMessage> messages;

  @override
  State<_MessageList> createState() => _MessageListState();
}

class _MessageListState extends State<_MessageList> {
  final _controller = ScrollController();

  void _jumpToEnd() {
    if (!_controller.hasClients) return;
    _controller.jumpTo(_controller.position.maxScrollExtent);
  }

  @override
  void didUpdateWidget(covariant _MessageList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.messages.length != oldWidget.messages.length) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _jumpToEnd());
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      controller: _controller,
      padding: const EdgeInsets.all(16),
      itemCount: widget.messages.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (_, i) => _MessageBubble(message: widget.messages[i]),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final SupportMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.sender == SupportSender.user;
    final time = formatMessageTime(message.createdAt);

    final bubble = Container(
      constraints: const BoxConstraints(maxWidth: 280),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!isUser) ...[
            const Text(
              'SUPORTE EDU',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: AppColors.purple,
              ),
            ),
            const SizedBox(height: 4),
          ],
          Text(
            message.body,
            style: const TextStyle(
              fontSize: 14,
              color: AppColors.textPrimary,
            ),
          ),
          if (time.isNotEmpty) ...[
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                time,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ],
      ),
    );

    return Row(
      mainAxisAlignment:
          isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (!isUser) ...[
          Container(
            width: 32,
            height: 32,
            decoration: const BoxDecoration(
              color: AppColors.primary,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.support_agent,
              size: 18,
              color: AppColors.white,
            ),
          ),
          const SizedBox(width: 8),
        ],
        Flexible(child: bubble),
      ],
    );
  }
}

class _InputBar extends StatefulWidget {
  const _InputBar({required this.sending, required this.onSend});

  final bool sending;
  final ValueChanged<String> onSend;

  @override
  State<_InputBar> createState() => _InputBarState();
}

class _InputBarState extends State<_InputBar> {
  final _controller = TextEditingController();

  bool get _canSend =>
      _controller.text.trim().isNotEmpty && !widget.sending;

  void _submit() {
    if (!_canSend) return;
    final text = _controller.text;
    _controller.clear();
    widget.onSend(text);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              enabled: !widget.sending,
              minLines: 1,
              maxLines: 4,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                hintText: 'Escreva sua mensagem aqui...',
                hintStyle: TextStyle(color: AppColors.textSecondary),
                border: InputBorder.none,
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 12, vertical: 14),
              ),
              style: const TextStyle(color: AppColors.textPrimary),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _canSend ? _submit : null,
            child: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: _canSend
                    ? AppColors.primary
                    : AppColors.primary.withValues(alpha: 0.4),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.send, color: AppColors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}

class _Disclaimer extends StatelessWidget {
  const _Disclaimer();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        'Mentor Edu pode cometer erros, verifique informações importantes.',
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
      ),
    );
  }
}
```

- [ ] **Step 4: Run the screen test to verify it passes**

Run: `flutter test test/features/support/support_screen_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Register the route in main.dart**

In `lib/main.dart`, add the import near the other feature imports:

```dart
import 'features/support/presentation/support_screen.dart';
```

And add the route inside the `routes: { ... }` map (next to `'/orders'`):

```dart
'/support': (_) => const SupportScreen(),
```

- [ ] **Step 6: Verify the app still compiles**

Run: `flutter analyze`
Expected: No errors (warnings pre-existing elsewhere are acceptable, but the new files must be clean).

- [ ] **Step 7: Commit**

```bash
git add lib/features/support/presentation/support_screen.dart lib/main.dart test/features/support/support_screen_test.dart
git commit -m "feat(support): add support chat screen and /support route"
```

---

### Task 6: Wire the store navbar into store screens

**Files:**
- Modify: `lib/features/marketplace/presentation/marketplace_screen.dart:135`
- Modify: `lib/features/marketplace/presentation/order_details_screen.dart:155`
- Modify: `lib/features/order_tracking/presentation/order_tracking_screen.dart:70`
- Modify: `lib/features/marketplace/presentation/orders_screen.dart` (add navbar)

- [ ] **Step 1: Update marketplace_screen.dart**

Change line 135 from:

```dart
        bottomNavigationBar: const NavBar(currentIndex: 4),
```

to:

```dart
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 3,
        ),
```

Ensure the file imports `NavBar` (it already does — same `nav_bar.dart` import). `NavBarMode` comes from the same file, so no extra import is needed.

- [ ] **Step 2: Update order_details_screen.dart**

Change line 155 from:

```dart
        bottomNavigationBar: const NavBar(currentIndex: 4),
```

to:

```dart
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 1,
        ),
```

- [ ] **Step 3: Update order_tracking_screen.dart**

Change line 70 from:

```dart
          bottomNavigationBar: const NavBar(currentIndex: 4),
```

to:

```dart
          bottomNavigationBar: const NavBar(
            mode: NavBarMode.store,
            currentIndex: 1,
          ),
```

- [ ] **Step 4: Add a navbar to orders_screen.dart**

`orders_screen.dart` currently renders no navbar. Add the import at the top (after the existing imports):

```dart
import '../../components/nav_bar.dart';
```

Then add `bottomNavigationBar` to the `Scaffold` (the one starting at line 11), right after `backgroundColor: Colors.transparent,`:

```dart
        backgroundColor: Colors.transparent,
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 1,
        ),
```

- [ ] **Step 5: Verify analyze and full test suite**

Run: `flutter analyze`
Expected: no new errors.

Run: `flutter test`
Expected: all tests pass (existing suite + the new support and navbar tests).

- [ ] **Step 6: Commit**

```bash
git add lib/features/marketplace/presentation/marketplace_screen.dart \
        lib/features/marketplace/presentation/order_details_screen.dart \
        lib/features/order_tracking/presentation/order_tracking_screen.dart \
        lib/features/marketplace/presentation/orders_screen.dart
git commit -m "feat(navbar): use store layout on marketplace and order screens"
```

---

### Task 7: Manual verification

- [ ] **Step 1: Run the app**

Run: `flutter run` (against a backend reachable at `ApiConfig.baseUrl`, default
`http://10.0.2.2:8001/api` for the Android emulator). Confirm the backend serves
`/support` on that base URL — other features (`/orders`, `/auth`) already do.

- [ ] **Step 2: Verify navbar switching**

1. From Home, tap **Loja** → marketplace opens; navbar now shows **Home · Meus Pedidos · Suporte · Loja** with Loja highlighted.
2. Tap **Meus Pedidos** → orders screen, store navbar persists, Meus Pedidos highlighted.
3. Tap **Suporte** → support chat opens, Suporte highlighted.
4. Tap **Home** → home screen, navbar switches back to **Home · Quiz · Revisão · Estudo · Loja**.

- [ ] **Step 3: Verify the support chat**

1. On the Suporte screen, confirm loading spinner → then either the empty greeting or existing history.
2. Type a message and send → input clears, the sent message appears, and the support reply (returned by the backend) appears; list auto-scrolls to the latest.
3. Confirm the disclaimer text shows at the bottom.

- [ ] **Step 4: Done**

No commit needed for manual verification.

---

## Self-Review Notes

- **Spec coverage:** Navbar dual-layout (Task 1, 6); Suporte→`/support` new screen (Task 5); store screens set (Task 6, incl. adding navbar to OrdersScreen per spec); chat model/service/provider/screen (Tasks 2–5); backend contract `id` as UUID string + 201 accepted (Tasks 2, 3); TDD tests for all units (every task). Time formatting `HH:mm` local (Task 2).
- **Type consistency:** `NavBarMode {main, store}`, `SupportSender {user, support}`, `SupportViewState {loading, success, error}`, `SupportMessage{id,sender,body,createdAt}`, `SupportService.fetchMessages()/sendMessage(String)`, `SupportProvider.load()/send(String)/state/messages/errorMessage/sending`, `SupportScreen`/`SupportView` — all referenced consistently across tasks.
- **Store indices:** main: Loja=4. store: Home=0, Meus Pedidos=1, Suporte=2, Loja=3. marketplace→3, orders/order-details/order-tracking→1, support→2. Consistent with Task 1's layout map.
- **No global provider:** `SupportProvider` is screen-scoped in `SupportScreen` (matches order_tracking); `main.dart` `MultiProvider` is untouched.
