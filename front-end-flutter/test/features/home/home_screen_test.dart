import 'package:edu_ia/features/home/presentation/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _harness({void Function(RouteSettings)? aoNavegar}) => MaterialApp(
  home: const HomeScreen(),
  onGenerateRoute: (settings) {
    aoNavegar?.call(settings);
    return MaterialPageRoute(builder: (_) => const Scaffold(body: Text('DESTINO')));
  },
);

void main() {
  // Sem token guardado, o nome e o resumo desistem antes de tocar a rede: a
  // home fica só com o que não depende de dado do aluno.
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('não mostra trilhas nem revisão de ciclo com números fixos', (tester) async {
    await tester.pumpWidget(_harness());
    await tester.pumpAndSettle();

    expect(find.text('Suas Trilhas'), findsNothing);
    expect(find.textContaining('aulas concluídas'), findsNothing);
    expect(find.text('Revisão de Ciclo'), findsNothing);
    expect(find.textContaining('Citologia'), findsNothing);
    expect(find.text('Revisar Agora'), findsNothing);
  });
}
