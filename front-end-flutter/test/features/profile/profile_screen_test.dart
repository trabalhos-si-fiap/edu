import 'package:edu_ia/features/auth/data/auth_api.dart';
import 'package:edu_ia/features/profile/presentation/profile_screen.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeAuthApi extends AuthApi {
  @override
  Future<String?> currentDisplayName() async => 'Ana Ensaio';
}

class _FakeTrackerApi extends TrackerApi {
  _FakeTrackerApi({this.nivel, this.erro});

  final int? nivel;
  final String? erro;

  @override
  Future<StudySummary> fetchSummary() async {
    if (erro != null) throw TrackerException(erro!);
    return StudySummary.fromJson({
      'objetivo': null,
      'roadmap': {'etapas_totais': 0, 'etapas_concluidas': 0, 'progresso': 0.0},
      'pontos': {'total': 150, 'nivel': nivel, 'streak': 1},
      'estudo': {'questoes_respondidas': 3, 'subtemas_iniciados': 1},
    });
  }
}

Future<void> _pump(WidgetTester tester, TrackerApi trackerApi) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ProfileScreen(authApi: _FakeAuthApi(), trackerApi: trackerApi),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('o selo abaixo do nome mostra o nível real, não um de exemplo', (
    tester,
  ) async {
    await _pump(tester, _FakeTrackerApi(nivel: 2));

    expect(find.text('LEVEL 18 SCHOLAR'), findsNothing);
    expect(find.text('NÍVEL 2'), findsOneWidget);
  });

  testWidgets('sem o resumo, o selo não inventa um nível', (tester) async {
    await _pump(tester, _FakeTrackerApi(erro: 'Não foi possível conectar ao servidor'));

    expect(find.text('LEVEL 18 SCHOLAR'), findsNothing);
    expect(find.textContaining('NÍVEL'), findsNothing);
  });

  testWidgets('o menu do perfil fala português', (tester) async {
    await _pump(tester, _FakeTrackerApi(nivel: 2));

    expect(find.text('Ajuda e suporte'), findsOneWidget);
    expect(find.text('Política de privacidade'), findsOneWidget);
    expect(find.text('Sair'), findsOneWidget);
    expect(find.text('Help & Support'), findsNothing);
    expect(find.text('Privacy Policy'), findsNothing);
    expect(find.text('Logout'), findsNothing);
  });
}
