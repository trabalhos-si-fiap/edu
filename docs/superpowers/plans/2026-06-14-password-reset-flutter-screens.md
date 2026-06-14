# Password Reset Flutter Screens — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the two-screen "forgot password" flow (request code → confirm new password) to the Flutter app, wired to the existing backend password-reset endpoints.

**Architecture:** Two new `StatefulWidget` screens that mirror the existing `login`/`register` screens (gradient + `_Header` + white card, `_submitting` flag, `try/catch (AuthException)` → `SnackBar`). A thin data layer adds two methods to `AuthApi`. The 6-box OTP input is extracted into a reusable, independently-tested `OtpInput` widget. Screens accept an optional injected `AuthApi` (same optional-injection style `AuthApi` already uses for its `http.Client`) so widget tests can drive them with a `MockClient`.

**Tech Stack:** Flutter/Dart, `package:http` (`MockClient` from `package:http/testing.dart` for tests), `flutter_test`.

**Conventions:**
- TDD: write the failing test, run it red, commit the test, implement, run green, `flutter analyze`, commit the implementation.
- All commands run from `front-end-flutter/` (the Flutter package root inside the worktree).
- Conventional Commits in English, imperative mood. One logical unit per commit.
- Both `flutter test` and `flutter analyze` must pass before any `feat`/`fix` commit.

**Backend contract (prefix `/api`, already live):**
- `POST /auth/password-reset/request` body `{email}` → `200` always · `429` (+`Retry-After`) · `422`.
- `POST /auth/password-reset/confirm` body `{email, code, new_password}` → `200` · `400` (generic) · `422`.

---

## File Structure

| File | Responsibility |
|---|---|
| `lib/features/auth/data/auth_api.dart` *(modify)* | Add `requestPasswordReset` + `confirmPasswordReset` (thin HTTP, PT-BR `AuthException` per status). |
| `lib/features/auth/presentation/widgets/otp_input.dart` *(create)* | Reusable 6-box single-use-code input with auto-advance; emits the concatenated code. |
| `lib/features/auth/presentation/forgot_password_screen.dart` *(create)* | Email entry → `request` → neutral confirmation → navigate to reset screen. |
| `lib/features/auth/presentation/reset_password_screen.dart` *(create)* | Code + new password → `confirm` → back to login; resend-with-cooldown. |
| `lib/features/auth/presentation/login_screen.dart` *(modify)* | Wire "Esqueceu sua senha?" link; show success SnackBar when arriving with `{'passwordReset': true}`. |
| `lib/main.dart` *(modify)* | Register `/forgot-password` and `/reset-password` routes. |
| `test/features/auth/auth_api_password_reset_test.dart` *(create)* | API method tests via `MockClient`. |
| `test/features/auth/otp_input_test.dart` *(create)* | OTP widget behavior. |
| `test/features/auth/forgot_password_screen_test.dart` *(create)* | Forgot screen behavior. |
| `test/features/auth/reset_password_screen_test.dart` *(create)* | Reset screen behavior. |
| `test/features/auth/login_screen_reset_test.dart` *(create)* | Login wiring: forgot link + success SnackBar. |
| `docs/back-end/password-reset.md` *(modify)* | §11: move "Telas Flutter" from out-of-scope to delivered. |

---

## Task 1: AuthApi password-reset methods

**Files:**
- Test: `test/features/auth/auth_api_password_reset_test.dart` (create)
- Modify: `lib/features/auth/data/auth_api.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/auth/auth_api_password_reset_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/features/auth/data/auth_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  group('requestPasswordReset', () {
    test('posts the email to the request endpoint and succeeds on 200',
        () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(
          jsonEncode({'detail': 'If the email exists, a reset code was sent.'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = AuthApi(client: client);

      await api.requestPasswordReset(email: 'maria@example.com');

      expect(captured.method, 'POST');
      expect(captured.url.path, endsWith('/auth/password-reset/request'));
      expect(jsonDecode(captured.body), {'email': 'maria@example.com'});
    });

    test('throws AuthException on 429', () async {
      final client = MockClient((req) async => http.Response('', 429));
      final api = AuthApi(client: client);

      expect(
        () => api.requestPasswordReset(email: 'maria@example.com'),
        throwsA(isA<AuthException>()),
      );
    });
  });

  group('confirmPasswordReset', () {
    test('posts email, code and new_password and succeeds on 200', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(
          jsonEncode({'detail': 'Password updated.'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = AuthApi(client: client);

      await api.confirmPasswordReset(
        email: 'maria@example.com',
        code: '123456',
        newPassword: 'NovaSenha!9',
      );

      expect(captured.url.path, endsWith('/auth/password-reset/confirm'));
      expect(jsonDecode(captured.body), {
        'email': 'maria@example.com',
        'code': '123456',
        'new_password': 'NovaSenha!9',
      });
    });

    test('throws AuthException with the invalid-code message on 400', () async {
      final client = MockClient((req) async => http.Response('', 400));
      final api = AuthApi(client: client);

      expect(
        () => api.confirmPasswordReset(
          email: 'maria@example.com',
          code: '000000',
          newPassword: 'NovaSenha!9',
        ),
        throwsA(isA<AuthException>().having(
            (e) => e.message, 'message', 'Código inválido ou expirado')),
      );
    });

    test('throws AuthException on 422', () async {
      final client = MockClient((req) async => http.Response('', 422));
      final api = AuthApi(client: client);

      expect(
        () => api.confirmPasswordReset(
          email: 'maria@example.com',
          code: '123',
          newPassword: 'weak',
        ),
        throwsA(isA<AuthException>()),
      );
    });
  });
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `flutter test test/features/auth/auth_api_password_reset_test.dart`
Expected: FAIL — `The method 'requestPasswordReset' isn't defined for the class 'AuthApi'` (compile error).

- [ ] **Step 3: Commit the failing test**

```bash
git add test/features/auth/auth_api_password_reset_test.dart
git commit -m "test(auth): add password reset AuthApi tests"
```

- [ ] **Step 4: Implement the two methods**

In `lib/features/auth/data/auth_api.dart`, add these two methods inside the `AuthApi` class (place them after `login`, before `_persistAuth`). They do NOT persist tokens — this flow is pre-authentication.

```dart
  /// Requests a password reset code via `POST /auth/password-reset/request`.
  ///
  /// The backend always responds 200 (anti-enumeration), so a successful
  /// return reveals nothing about whether the email exists.
  Future<void> requestPasswordReset({required String email}) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/auth/password-reset/request'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email}),
      );
    } on Exception {
      throw AuthException('Não foi possível conectar ao servidor');
    }

    if (res.statusCode == 429) {
      throw AuthException('Muitas tentativas. Tente novamente mais tarde');
    }
    if (res.statusCode == 422) {
      throw AuthException('Verifique os dados informados');
    }
    if (res.statusCode != 200) {
      throw AuthException(
        'Falha ao solicitar o código (código ${res.statusCode})',
      );
    }
  }

  /// Confirms a reset code and sets a new password via
  /// `POST /auth/password-reset/confirm`. The backend returns a generic 400 for
  /// any verification failure (wrong/expired/locked code, unknown email).
  Future<void> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    final http.Response res;
    try {
      res = await _client.post(
        Uri.parse('${ApiConfig.baseUrl}/auth/password-reset/confirm'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'code': code,
          'new_password': newPassword,
        }),
      );
    } on Exception {
      throw AuthException('Não foi possível conectar ao servidor');
    }

    if (res.statusCode == 400) {
      throw AuthException('Código inválido ou expirado');
    }
    if (res.statusCode == 422) {
      throw AuthException('Verifique os dados informados');
    }
    if (res.statusCode != 200) {
      throw AuthException(
        'Falha ao redefinir a senha (código ${res.statusCode})',
      );
    }
  }
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `flutter test test/features/auth/auth_api_password_reset_test.dart`
Expected: PASS (all 5 tests).

- [ ] **Step 6: Analyze**

Run: `flutter analyze`
Expected: `No issues found!`

- [ ] **Step 7: Commit the implementation**

```bash
git add lib/features/auth/data/auth_api.dart
git commit -m "feat(auth): add password reset request/confirm to AuthApi"
```

---

## Task 2: OtpInput widget

**Files:**
- Test: `test/features/auth/otp_input_test.dart` (create)
- Create: `lib/features/auth/presentation/widgets/otp_input.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/auth/otp_input_test.dart`:

```dart
import 'package:edu_ia/features/auth/presentation/widgets/otp_input.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _harness(ValueChanged<String> onChanged) => MaterialApp(
      home: Scaffold(body: OtpInput(onChanged: onChanged)),
    );

void main() {
  testWidgets('renders six single-digit boxes', (tester) async {
    await tester.pumpWidget(_harness((_) {}));
    expect(find.byType(TextField), findsNWidgets(6));
  });

  testWidgets('emits the concatenated code as digits are typed',
      (tester) async {
    var code = '';
    await tester.pumpWidget(_harness((v) => code = v));

    final boxes = find.byType(TextField);
    for (var i = 0; i < 6; i++) {
      await tester.enterText(boxes.at(i), '${i + 1}');
    }
    await tester.pump();

    expect(code, '123456');
  });

  testWidgets('auto-advances focus to the next box after a digit',
      (tester) async {
    await tester.pumpWidget(_harness((_) {}));

    final boxes = find.byType(TextField);
    await tester.enterText(boxes.at(0), '1');
    await tester.pump();

    final second = tester.widget<TextField>(boxes.at(1));
    expect(second.focusNode!.hasFocus, isTrue);
  });
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `flutter test test/features/auth/otp_input_test.dart`
Expected: FAIL — `Target of URI doesn't exist: '.../otp_input.dart'`.

- [ ] **Step 3: Commit the failing test**

```bash
git add test/features/auth/otp_input_test.dart
git commit -m "test(auth): add OtpInput widget tests"
```

- [ ] **Step 4: Implement the widget**

Create `lib/features/auth/presentation/widgets/otp_input.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/theme/app_colors.dart';

/// A six-box single-use-code input. Each box accepts one digit; typing a digit
/// advances focus to the next box, and backspace on an empty box returns to the
/// previous one. [onChanged] receives the concatenated value (0–6 digits).
class OtpInput extends StatefulWidget {
  const OtpInput({super.key, required this.onChanged});

  final ValueChanged<String> onChanged;

  @override
  State<OtpInput> createState() => _OtpInputState();
}

class _OtpInputState extends State<OtpInput> {
  static const _length = 6;
  late final List<TextEditingController> _controllers;
  late final List<FocusNode> _focusNodes;

  @override
  void initState() {
    super.initState();
    _controllers = List.generate(_length, (_) => TextEditingController());
    _focusNodes = List.generate(_length, (_) => FocusNode());
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    for (final f in _focusNodes) {
      f.dispose();
    }
    super.dispose();
  }

  void _emit() => widget.onChanged(_controllers.map((c) => c.text).join());

  void _onChanged(int index, String value) {
    if (value.isNotEmpty && index < _length - 1) {
      _focusNodes[index + 1].requestFocus();
    }
    _emit();
  }

  KeyEventResult _onKey(int index, KeyEvent event) {
    if (event is KeyDownEvent &&
        event.logicalKey == LogicalKeyboardKey.backspace &&
        _controllers[index].text.isEmpty &&
        index > 0) {
      _controllers[index - 1].clear();
      _focusNodes[index - 1].requestFocus();
      _emit();
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: List.generate(_length, (index) {
        return SizedBox(
          width: 48,
          child: Focus(
            skipTraversal: true,
            canRequestFocus: false,
            onKeyEvent: (node, event) => _onKey(index, event),
            child: TextField(
              controller: _controllers[index],
              focusNode: _focusNodes[index],
              textAlign: TextAlign.center,
              keyboardType: TextInputType.number,
              maxLength: 1,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: const InputDecoration(counterText: ''),
              onChanged: (value) => _onChanged(index, value),
            ),
          ),
        );
      }),
    );
  }
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `flutter test test/features/auth/otp_input_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 6: Analyze**

Run: `flutter analyze`
Expected: `No issues found!`

- [ ] **Step 7: Commit the implementation**

```bash
git add lib/features/auth/presentation/widgets/otp_input.dart
git commit -m "feat(auth): add reusable OtpInput widget"
```

---

## Task 3: ForgotPasswordScreen

**Files:**
- Test: `test/features/auth/forgot_password_screen_test.dart` (create)
- Create: `lib/features/auth/presentation/forgot_password_screen.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/auth/forgot_password_screen_test.dart`:

```dart
import 'package:edu_ia/features/auth/data/auth_api.dart';
import 'package:edu_ia/features/auth/presentation/forgot_password_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

Widget _harness(AuthApi api) => MaterialApp(
      initialRoute: '/forgot-password',
      routes: {
        '/forgot-password': (_) => ForgotPasswordScreen(authApi: api),
        '/reset-password': (_) => const Scaffold(body: Text('reset-screen')),
      },
    );

void main() {
  testWidgets('shows a validation error when the email is empty',
      (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 200)));
    await tester.pumpWidget(_harness(api));

    await tester.tap(find.text('Enviar código'));
    await tester.pump();

    expect(find.text('Informe o e-mail'), findsOneWidget);
    expect(find.text('reset-screen'), findsNothing);
  });

  testWidgets('shows neutral confirmation and navigates to reset on success',
      (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 200)));
    await tester.pumpWidget(_harness(api));

    await tester.enterText(find.byType(TextFormField), 'maria@example.com');
    await tester.tap(find.text('Enviar código'));
    await tester.pump(); // setState(_submitting = true), request starts
    await tester.pump(); // request resolves, snackbar + navigation scheduled
    await tester.pumpAndSettle(); // finish the route transition

    expect(find.text('reset-screen'), findsOneWidget);
  });

  testWidgets('shows an error SnackBar on 429', (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 429)));
    await tester.pumpWidget(_harness(api));

    await tester.enterText(find.byType(TextFormField), 'maria@example.com');
    await tester.tap(find.text('Enviar código'));
    await tester.pump(); // request starts
    await tester.pump(); // request resolves, snackbar shown

    expect(
      find.text('Muitas tentativas. Tente novamente mais tarde'),
      findsOneWidget,
    );
  });
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `flutter test test/features/auth/forgot_password_screen_test.dart`
Expected: FAIL — `Target of URI doesn't exist: '.../forgot_password_screen.dart'`.

- [ ] **Step 3: Commit the failing test**

```bash
git add test/features/auth/forgot_password_screen_test.dart
git commit -m "test(auth): add forgot password screen tests"
```

- [ ] **Step 4: Implement the screen**

Create `lib/features/auth/presentation/forgot_password_screen.dart`:

```dart
import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/auth_api.dart';

class ForgotPasswordScreen extends StatefulWidget {
  ForgotPasswordScreen({super.key, AuthApi? authApi})
      : authApi = authApi ?? AuthApi();

  final AuthApi authApi;

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (_submitting) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final email = _emailController.text.trim();

    setState(() => _submitting = true);
    try {
      await widget.authApi.requestPasswordReset(email: email);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Se o e-mail existir, enviamos um código.'),
        ),
      );
      Navigator.pushNamed(context, '/reset-password', arguments: email);
    } on AuthException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SingleChildScrollView(
          child: Column(
            children: [
              const _Header(),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: _buildCard(),
              ),
              const SizedBox(height: 16),
              GestureDetector(
                onTap: () => Navigator.pop(context),
                child: const Text(
                  'Voltar para o login',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppColors.purple,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCard() {
    return Container(
      width: double.infinity,
      transform: Matrix4.translationValues(0, -20, 0),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 28),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'E-mail',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(hintText: 'nome@email.com'),
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Informe o e-mail';
                if (!v.contains('@')) return 'E-mail inválido';
                return null;
              },
            ),
            const SizedBox(height: 28),
            ElevatedButton(
              onPressed: _submitting ? null : _handleSubmit,
              child: _submitting
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.white,
                      ),
                    )
                  : const Text('Enviar código'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.fromLTRB(24, 60, 24, 40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Edu IA',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          SizedBox(height: 32),
          Text(
            'Esqueceu a senha?',
            style: TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
              height: 1.2,
            ),
          ),
          SizedBox(height: 12),
          Text(
            'Informe seu e-mail e enviaremos um\ncódigo para redefinir sua senha.',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `flutter test test/features/auth/forgot_password_screen_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 6: Analyze**

Run: `flutter analyze`
Expected: `No issues found!`

- [ ] **Step 7: Commit the implementation**

```bash
git add lib/features/auth/presentation/forgot_password_screen.dart
git commit -m "feat(auth): add forgot password screen"
```

---

## Task 4: ResetPasswordScreen

**Files:**
- Test: `test/features/auth/reset_password_screen_test.dart` (create)
- Create: `lib/features/auth/presentation/reset_password_screen.dart`

> Note on timers: the screen starts a 1-second `Timer.periodic` cooldown in
> `initState`. Tests that do NOT navigate away must drain it before ending with
> `await tester.pump(const Duration(seconds: 60));` (otherwise flutter_test
> reports a pending timer). Tests that navigate to `/login` don't need this —
> navigation disposes the screen, which cancels the timer.

- [ ] **Step 1: Write the failing test**

Create `test/features/auth/reset_password_screen_test.dart`:

```dart
import 'package:edu_ia/features/auth/data/auth_api.dart';
import 'package:edu_ia/features/auth/presentation/reset_password_screen.dart';
import 'package:edu_ia/features/auth/presentation/widgets/otp_input.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

const _email = 'maria@example.com';

Widget _harness(AuthApi api) => MaterialApp(
      initialRoute: '/reset-password',
      onGenerateRoute: (settings) {
        if (settings.name == '/reset-password') {
          return MaterialPageRoute(
            builder: (_) => ResetPasswordScreen(authApi: api),
            settings: const RouteSettings(
              name: '/reset-password',
              arguments: _email,
            ),
          );
        }
        return null;
      },
      routes: {
        '/login': (_) => const Scaffold(body: Text('login-screen')),
      },
    );

Future<void> _fillForm(WidgetTester tester) async {
  final boxes = find.descendant(
    of: find.byType(OtpInput),
    matching: find.byType(TextField),
  );
  for (var i = 0; i < 6; i++) {
    await tester.enterText(boxes.at(i), '${i + 1}');
  }
  final passwords = find.byType(TextFormField);
  await tester.enterText(passwords.at(0), 'NovaSenha!9');
  await tester.enterText(passwords.at(1), 'NovaSenha!9');
  await tester.pump();
}

void main() {
  testWidgets('shows the email it received as a route argument',
      (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 200)));
    await tester.pumpWidget(_harness(api));
    await tester.pump();

    expect(find.text(_email), findsOneWidget);

    await tester.pump(const Duration(seconds: 60)); // drain cooldown timer
  });

  testWidgets('resend button is disabled during the cooldown', (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 200)));
    await tester.pumpWidget(_harness(api));
    await tester.pump();

    final button = tester.widget<TextButton>(
      find.widgetWithText(TextButton, 'Reenviar em 60s'),
    );
    expect(button.onPressed, isNull);

    await tester.pump(const Duration(seconds: 60)); // drain cooldown timer
  });

  testWidgets('shows the invalid-code message on 400', (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 400)));
    await tester.pumpWidget(_harness(api));
    await tester.pump();
    await _fillForm(tester);

    await tester.tap(find.text('Redefinir senha'));
    await tester.pump(); // request starts
    await tester.pump(); // request resolves, snackbar shown

    expect(find.text('Código inválido ou expirado'), findsOneWidget);

    await tester.pump(const Duration(seconds: 60)); // drain cooldown timer
  });

  testWidgets('navigates to login on success', (tester) async {
    final api = AuthApi(client: MockClient((_) async => http.Response('', 200)));
    await tester.pumpWidget(_harness(api));
    await tester.pump();
    await _fillForm(tester);

    await tester.tap(find.text('Redefinir senha'));
    await tester.pump(); // request starts
    await tester.pump(); // request resolves, navigation scheduled
    await tester.pumpAndSettle(); // route transition (timer cancelled on dispose)

    expect(find.text('login-screen'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `flutter test test/features/auth/reset_password_screen_test.dart`
Expected: FAIL — `Target of URI doesn't exist: '.../reset_password_screen.dart'`.

- [ ] **Step 3: Commit the failing test**

```bash
git add test/features/auth/reset_password_screen_test.dart
git commit -m "test(auth): add reset password screen tests"
```

- [ ] **Step 4: Implement the screen**

Create `lib/features/auth/presentation/reset_password_screen.dart`:

```dart
import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/auth_api.dart';
import 'widgets/otp_input.dart';

class ResetPasswordScreen extends StatefulWidget {
  ResetPasswordScreen({super.key, AuthApi? authApi})
      : authApi = authApi ?? AuthApi();

  final AuthApi authApi;

  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  static const _cooldownStart = 60;

  final _formKey = GlobalKey<FormState>();
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();
  String _code = '';
  bool _obscurePassword = true;
  bool _obscureConfirm = true;
  bool _submitting = false;
  int _cooldown = _cooldownStart;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startCooldown();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  void _startCooldown() {
    _timer?.cancel();
    setState(() => _cooldown = _cooldownStart);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_cooldown <= 1) {
        timer.cancel();
        setState(() => _cooldown = 0);
      } else {
        setState(() => _cooldown--);
      }
    });
  }

  String _emailArg() => ModalRoute.of(context)!.settings.arguments as String;

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) return 'Informe a senha';
    if (value.length < 8) return 'Mínimo de 8 caracteres';
    if (!RegExp(r'[!@#$%^&*(),.?":{}|<>]').hasMatch(value)) {
      return 'Deve conter pelo menos um caractere especial';
    }
    return null;
  }

  Future<void> _handleSubmit() async {
    if (_submitting) return;
    if (_code.length != 6) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Informe os 6 dígitos do código')),
      );
      return;
    }
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() => _submitting = true);
    try {
      await widget.authApi.confirmPasswordReset(
        email: _emailArg(),
        code: _code,
        newPassword: _passwordController.text,
      );
      if (!mounted) return;
      Navigator.pushNamedAndRemoveUntil(
        context,
        '/login',
        (route) => false,
        arguments: {'passwordReset': true},
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _handleResend() async {
    try {
      await widget.authApi.requestPasswordReset(email: _emailArg());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Se o e-mail existir, enviamos um código.'),
        ),
      );
      _startCooldown();
    } on AuthException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final email = _emailArg();
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SingleChildScrollView(
          child: Column(
            children: [
              const _Header(),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: _buildCard(email),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCard(String email) {
    return Container(
      width: double.infinity,
      transform: Matrix4.translationValues(0, -20, 0),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 28),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Código enviado para',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 4),
            Text(
              email,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 20),
            _label('Código'),
            const SizedBox(height: 8),
            OtpInput(onChanged: (v) => _code = v),
            const SizedBox(height: 20),
            _label('Nova senha'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _passwordController,
              obscureText: _obscurePassword,
              decoration: InputDecoration(
                hintText: 'Mín. 8 caracteres + especial',
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscurePassword ? Icons.visibility_off : Icons.visibility,
                    color: AppColors.textSecondary,
                  ),
                  onPressed: () =>
                      setState(() => _obscurePassword = !_obscurePassword),
                ),
              ),
              validator: _validatePassword,
            ),
            const SizedBox(height: 20),
            _label('Confirmar senha'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _confirmController,
              obscureText: _obscureConfirm,
              decoration: InputDecoration(
                hintText: 'Repita a senha',
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscureConfirm ? Icons.visibility_off : Icons.visibility,
                    color: AppColors.textSecondary,
                  ),
                  onPressed: () =>
                      setState(() => _obscureConfirm = !_obscureConfirm),
                ),
              ),
              validator: (v) {
                if (v == null || v.isEmpty) return 'Confirme a senha';
                if (v != _passwordController.text) {
                  return 'As senhas não coincidem';
                }
                return null;
              },
            ),
            const SizedBox(height: 28),
            ElevatedButton(
              onPressed: _submitting ? null : _handleSubmit,
              child: _submitting
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.white,
                      ),
                    )
                  : const Text('Redefinir senha'),
            ),
            const SizedBox(height: 12),
            Center(
              child: TextButton(
                onPressed: _cooldown > 0 ? null : _handleResend,
                child: Text(
                  _cooldown > 0
                      ? 'Reenviar em ${_cooldown}s'
                      : 'Reenviar código',
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    color: AppColors.purple,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _label(String text) => Text(
        text,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: AppColors.textPrimary,
        ),
      );
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.fromLTRB(24, 60, 24, 40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Edu IA',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          SizedBox(height: 32),
          Text(
            'Redefinir senha',
            style: TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
              height: 1.2,
            ),
          ),
          SizedBox(height: 12),
          Text(
            'Digite o código que enviamos e\ndefina sua nova senha.',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `flutter test test/features/auth/reset_password_screen_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 6: Analyze**

Run: `flutter analyze`
Expected: `No issues found!`

- [ ] **Step 7: Commit the implementation**

```bash
git add lib/features/auth/presentation/reset_password_screen.dart
git commit -m "feat(auth): add reset password screen with resend cooldown"
```

---

## Task 5: Wire login screen + routes

**Files:**
- Test: `test/features/auth/login_screen_reset_test.dart` (create)
- Modify: `lib/features/auth/presentation/login_screen.dart`
- Modify: `lib/main.dart`

- [ ] **Step 1: Write the failing test**

Create `test/features/auth/login_screen_reset_test.dart`:

```dart
import 'package:edu_ia/features/auth/presentation/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('forgot-password link navigates to the forgot screen',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      initialRoute: '/login',
      routes: {
        '/login': (_) => const LoginScreen(),
        '/forgot-password': (_) =>
            const Scaffold(body: Text('forgot-screen')),
      },
    ));

    await tester.tap(find.text('Esqueceu sua senha?'));
    await tester.pumpAndSettle();

    expect(find.text('forgot-screen'), findsOneWidget);
  });

  testWidgets('shows a success SnackBar when arriving after a password reset',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      initialRoute: '/login',
      onGenerateRoute: (settings) => MaterialPageRoute(
        builder: (_) => const LoginScreen(),
        settings: const RouteSettings(
          name: '/login',
          arguments: {'passwordReset': true},
        ),
      ),
    ));

    await tester.pump(); // didChangeDependencies + post-frame callback
    await tester.pump(); // SnackBar animates in

    expect(
      find.text('Senha redefinida! Faça login com a nova senha.'),
      findsOneWidget,
    );
  });
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `flutter test test/features/auth/login_screen_reset_test.dart`
Expected: FAIL — the forgot link does nothing (navigates nowhere; `forgot-screen` not found) and no SnackBar appears.

- [ ] **Step 3: Commit the failing test**

```bash
git add test/features/auth/login_screen_reset_test.dart
git commit -m "test(auth): add login screen password reset wiring tests"
```

- [ ] **Step 4: Wire the login screen**

In `lib/features/auth/presentation/login_screen.dart`:

(a) Add a `didChangeDependencies` override to `_LoginScreenState` (place it right after the `dispose` method) that shows the success SnackBar once when arriving with the reset flag:

```dart
  bool _checkedResetFlag = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_checkedResetFlag) return;
    _checkedResetFlag = true;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map && args['passwordReset'] == true) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Senha redefinida! Faça login com a nova senha.'),
          ),
        );
      });
    }
  }
```

(b) Pass a navigation callback into `_LoginCard`. In `_LoginScreenState.build`, update the `_LoginCard(...)` call to add:

```dart
                onForgotPassword: () =>
                    Navigator.pushNamed(context, '/forgot-password'),
```

(c) In the `_LoginCard` class, add the field + constructor param. Change the constructor to include:

```dart
    required this.onForgotPassword,
```

and add the field next to the other `final` fields:

```dart
  final VoidCallback onForgotPassword;
```

(d) Wire the existing "Esqueceu sua senha?" `GestureDetector` (currently `onTap: () {}`) to the callback:

```dart
            child: GestureDetector(
              onTap: onForgotPassword,
              child: const Text(
                'Esqueceu sua senha?',
```

- [ ] **Step 5: Register the routes in main.dart**

In `lib/main.dart`, add the imports next to the other auth imports (after the `register_screen.dart` import):

```dart
import 'features/auth/presentation/forgot_password_screen.dart';
import 'features/auth/presentation/reset_password_screen.dart';
```

And add to the `routes:` map (after the `'/register'` entry):

```dart
          '/forgot-password': (_) => ForgotPasswordScreen(),
          '/reset-password': (_) => ResetPasswordScreen(),
```

(These are not `const`: the constructors instantiate a default `AuthApi`.)

- [ ] **Step 6: Run the test to verify it passes**

Run: `flutter test test/features/auth/login_screen_reset_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 7: Run the full suite + analyze**

Run: `flutter test`
Expected: `All tests passed!` (88 baseline + new tests).

Run: `flutter analyze`
Expected: `No issues found!`

- [ ] **Step 8: Commit**

```bash
git add lib/features/auth/presentation/login_screen.dart lib/main.dart \
        test/features/auth/login_screen_reset_test.dart
git commit -m "feat(auth): wire password reset flow into login and routes"
```

---

## Task 6: Update backend module docs

**Files:**
- Modify: `docs/back-end/password-reset.md`

- [ ] **Step 1: Move "Telas Flutter" out of "Fora de escopo"**

In `docs/back-end/password-reset.md`, in §11 "Fora de escopo (futuro)", delete this bullet:

```markdown
- **Telas Flutter** ("esqueci a senha" / "digite o código + nova senha").
```

Then add a short note at the end of the document recording the delivery:

```markdown
---

## 12. Telas Flutter (entregue)

O fluxo de "esqueci minha senha" no app Flutter já está implementado
(`front-end-flutter/`), ligado a estes endpoints:

- **Esqueci a senha** (`/forgot-password`) — campo de e-mail → `request` →
  confirmação neutra (anti-enumeração) → navega para a tela de código.
- **Redefinir senha** (`/reset-password`) — código de 6 dígitos (widget
  `OtpInput`) + nova senha → `confirm` → volta ao login. Inclui "Reenviar
  código" com cooldown de 60s.

Camada de dados: `AuthApi.requestPasswordReset` / `AuthApi.confirmPasswordReset`.
Spec: `docs/superpowers/specs/2026-06-14-password-reset-flutter-screens-design.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/back-end/password-reset.md
git commit -m "docs(auth): mark Flutter password reset screens as delivered"
```

---

## Final Verification

- [ ] Run `flutter test` from `front-end-flutter/` → `All tests passed!`
- [ ] Run `flutter analyze` from `front-end-flutter/` → `No issues found!`
- [ ] Manual smoke (optional, needs backend at `ApiConfig.baseUrl`): login → "Esqueceu sua senha?" → enter email → enter code + new password → confirm → back at login with success SnackBar.
- [ ] Use superpowers:finishing-a-development-branch to integrate the work.

## Self-Review Notes (author)

- **Spec coverage:** data-layer methods (Task 1), `OtpInput`/6-box + auto-advance (Task 2), forgot screen + neutral copy + navigation (Task 3), reset screen + read-only email + cooldown resend + 400/422 handling + success→login (Task 4), login link + success SnackBar + routes (Task 5), docs §11 (Task 6). Client-side validation (email non-empty, 6-digit code, password ≥8 + special, confirm match) is in Tasks 3–4.
- **Type consistency:** method names `requestPasswordReset`/`confirmPasswordReset`, widget `OtpInput(onChanged:)`, route names `/forgot-password` and `/reset-password`, and the `{'passwordReset': true}` argument are used identically across tasks.
- **Out of scope (unchanged):** deep linking, backend changes, "lembrar de mim", server-`Retry-After`-synced cooldown.
