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

    final submit = find.widgetWithText(ElevatedButton, 'Redefinir senha');
    await tester.ensureVisible(submit);
    await tester.tap(submit);
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

    final submit = find.widgetWithText(ElevatedButton, 'Redefinir senha');
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pump(); // request starts
    await tester.pump(); // request resolves, navigation scheduled
    await tester.pumpAndSettle(); // route transition (timer cancelled on dispose)

    expect(find.text('login-screen'), findsOneWidget);
  });
}
