import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/goal_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

StudySummary _resumo({Goal? goal, double progresso = 0.0}) => StudySummary(
  goal: goal,
  roadmap: RoadmapProgress(totalSteps: 50, completedSteps: 34, progress: progresso),
  points: const Points(total: 0, level: 1, streak: 0),
  study: const Study(answeredQuestions: 0, startedSubtopics: 0),
);

void main() {
  testWidgets('sem objetivo, o cartão inteiro não é desenhado', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: GoalCard(summary: _resumo()))),
    );

    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.textContaining('dias'), findsNothing);
  });

  testWidgets('com objetivo, mostra título, dias e progresso do backend', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalCard(
            summary: _resumo(
              goal: Goal(
                title: 'Medicina USP',
                targetDate: DateTime(2027, 11, 7),
                daysElapsed: 124,
                daysTotal: 200,
              ),
              progresso: 0.68,
            ),
          ),
        ),
      ),
    );

    expect(find.text('Meta: Medicina USP'), findsOneWidget);
    expect(find.text('124/200 dias'), findsOneWidget);
    expect(find.text('68% do\nPercurso'), findsOneWidget);

    final barra = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator),
    );
    expect(barra.value, 0.68);
  });

  testWidgets('aluno com objetivo e nenhuma etapa concluída mostra 0%', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalCard(
            summary: _resumo(
              goal: Goal(
                title: 'Direito',
                targetDate: DateTime(2027, 11, 7),
                daysElapsed: 0,
                daysTotal: 300,
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('0% do\nPercurso'), findsOneWidget);
    expect(find.text('0/300 dias'), findsOneWidget);
  });

  testWidgets('tocar o cartão leva ao tracker', (tester) async {
    var rotaAberta = '';
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalCard(
            summary: _resumo(
              goal: Goal(
                title: 'Medicina',
                targetDate: DateTime(2027, 11, 7),
                daysElapsed: 1,
                daysTotal: 10,
              ),
            ),
          ),
        ),
        onGenerateRoute: (settings) {
          rotaAberta = settings.name ?? '';
          return MaterialPageRoute(builder: (_) => const SizedBox());
        },
      ),
    );

    await tester.tap(find.text('Meta: Medicina'));
    await tester.pumpAndSettle();
    expect(rotaAberta, '/tracker');
  });
}
