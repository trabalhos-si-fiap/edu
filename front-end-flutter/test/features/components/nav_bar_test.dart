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
