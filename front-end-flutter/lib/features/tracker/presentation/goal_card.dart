import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/study_summary.dart';

/// O cartão de meta da tela inicial.
///
/// Antes da spec D ele anunciava um título de meta fixo no código, um par
/// de dias inventado e uma barra parada em pouco mais de dois terços — os
/// três fixos no código, para qualquer aluno. Agora os três vêm de
/// `GET /profile/summary`, e **sem objetivo o cartão não é desenhado**: um
/// cartão vazio com zeros seria outro jeito de mostrar um número que
/// ninguém escolheu.
class GoalCard extends StatelessWidget {
  const GoalCard({super.key, required this.summary});

  final StudySummary summary;

  @override
  Widget build(BuildContext context) {
    final goal = summary.goal;
    if (goal == null) return const SizedBox.shrink();

    final progresso = summary.roadmap.progress.clamp(0.0, 1.0);
    final percentual = (progresso * 100).round();

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/tracker'),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '$percentual% do\nPercurso',
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                    height: 1.2,
                  ),
                ),
                Image.asset('assets/images/target.png', width: 80, height: 80),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Meta: ${goal.title}',
                  style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
                Text(
                  '${goal.daysElapsed}/${goal.daysTotal} dias',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: progresso,
                minHeight: 10,
                backgroundColor: const Color(0xFFE5E7EB),
                valueColor: const AlwaysStoppedAnimation<Color>(AppColors.purple),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
