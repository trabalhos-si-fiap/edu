import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Estrelas de avaliação (suporta meia estrela). Portado de edu-kt `RatingStars`.
class RatingStars extends StatelessWidget {
  final double rating;
  final int count;
  final double starSize;
  final bool showCount;

  const RatingStars({
    super.key,
    required this.rating,
    required this.count,
    this.starSize = 14,
    this.showCount = true,
  });

  @override
  Widget build(BuildContext context) {
    final halves = (rating * 2).round().clamp(0, 10);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < 5; i++) ...[
          if (i > 0) const SizedBox(width: 2),
          Icon(_iconForStar(halves - i * 2), color: AppColors.star, size: starSize),
        ],
        if (showCount) ...[
          const SizedBox(width: 6),
          Text(
            count == 0
                ? 'Sem avaliações'
                : '${rating.toStringAsFixed(1)} ($count)',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ],
    );
  }

  IconData _iconForStar(int filledHalves) {
    if (filledHalves >= 2) return Icons.star;
    if (filledHalves == 1) return Icons.star_half;
    return Icons.star_border;
  }
}
