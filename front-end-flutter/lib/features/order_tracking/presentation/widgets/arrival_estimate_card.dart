import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import 'order_format.dart';

/// Card "Previsão de Chegada" com a data destacada.
class ArrivalEstimateCard extends StatelessWidget {
  final DateTime estimatedArrival;

  const ArrivalEstimateCard({super.key, required this.estimatedArrival});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 20),
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          const Text(
            'Previsão de Chegada',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            OrderFormat.dayMonth(estimatedArrival),
            style: const TextStyle(
              fontSize: 36,
              fontWeight: FontWeight.w800,
              color: AppColors.purple,
              letterSpacing: -0.5,
            ),
          ),
        ],
      ),
    );
  }
}
