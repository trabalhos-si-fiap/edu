import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/points_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('aluno zerado mostra zero, não 3.120', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: PointsCard(points: Points(total: 0, level: 1, streak: 0))),
      ),
    );

    expect(find.text('0'), findsOneWidget);
    expect(find.text('3,120'), findsNothing);
    expect(find.textContaining('Nível 1'), findsOneWidget);
  });

  testWidgets('total grande sai formatado com separador de milhar', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: PointsCard(points: Points(total: 3120, level: 8, streak: 4))),
      ),
    );

    expect(find.text('3.120'), findsOneWidget);
    expect(find.textContaining('Nível 8'), findsOneWidget);
  });

  testWidgets('a linha de estatísticas vem do resumo', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StudyStatsRow(
            points: Points(total: 100, level: 2, streak: 6),
            study: Study(answeredQuestions: 42, startedSubtopics: 7),
          ),
        ),
      ),
    );

    expect(find.text('42'), findsOneWidget);
    expect(find.text('Questões'), findsOneWidget);
    expect(find.text('6'), findsOneWidget);
    expect(find.text('Sequência'), findsOneWidget);
  });

  testWidgets('aluno zerado na linha de estatísticas mostra dois zeros', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StudyStatsRow(
            points: Points(total: 0, level: 1, streak: 0),
            study: Study(answeredQuestions: 0, startedSubtopics: 0),
          ),
        ),
      ),
    );

    expect(find.text('0'), findsNWidgets(2));
  });
}
