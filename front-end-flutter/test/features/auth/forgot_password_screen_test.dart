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
