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
