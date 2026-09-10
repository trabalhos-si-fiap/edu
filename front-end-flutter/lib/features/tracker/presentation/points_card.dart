import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/study_summary.dart';

/// Formata 3120 como "3.120" — separador de milhar do português, sem
/// depender de `intl` (o app não o tem hoje).
String _milhar(int valor) {
  final digitos = valor.abs().toString();
  final partes = <String>[];
  for (var fim = digitos.length; fim > 0; fim -= 3) {
    partes.insert(0, digitos.substring(fim - 3 < 0 ? 0 : fim - 3, fim));
  }
  return (valor < 0 ? '-' : '') + partes.join('.');
}

/// Total de pontos e nível — os dois vindos de `GET /profile/summary`.
///
/// O valor que estava aqui antes era um total de pontos escrito no código,
/// igual para todo mundo. O teste que trava isso é "aluno zerado mostra
/// zero".
class PointsCard extends StatelessWidget {
  const PointsCard({super.key, required this.points});

  final Points points;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Total de pontos',
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 4),
              Text(
                _milhar(points.total),
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Nível ${points.level}',
                style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.purple,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.star, color: AppColors.white, size: 22),
          ),
        ],
      ),
    );
  }
}

/// Questões respondidas e sequência atual.
///
/// O rótulo mudou de "Testes" para "Questões" porque é o que o backend
/// conta (`estudo.questoes_respondidas`, a soma de `total_respondidas`).
/// Manter "Testes" sobre um número de questões seria trocar um dado
/// inventado por um rótulo inventado.
class StudyStatsRow extends StatelessWidget {
  const StudyStatsRow({super.key, required this.points, required this.study});

  final Points points;
  final Study study;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _StatBox(
            icone: Icons.description_outlined,
            valor: study.answeredQuestions,
            rotulo: 'Questões',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatBox(
            icone: Icons.local_fire_department_outlined,
            valor: points.streak,
            rotulo: 'Sequência',
          ),
        ),
      ],
    );
  }
}

class _StatBox extends StatelessWidget {
  const _StatBox({required this.icone, required this.valor, required this.rotulo});

  final IconData icone;
  final int valor;
  final String rotulo;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icone, size: 24, color: AppColors.textSecondary),
          const SizedBox(height: 12),
          Text(
            '$valor',
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(rotulo, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}
