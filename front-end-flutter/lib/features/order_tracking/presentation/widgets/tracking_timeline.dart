import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../domain/order_model.dart';
import 'order_format.dart';

/// Card branco com a linha do tempo (Stepper) das etapas do pedido.
/// Renderiza qualquer quantidade de [TrackingStep] vinda do model.
class TrackingTimeline extends StatelessWidget {
  final List<TrackingStep> steps;

  const TrackingTimeline({super.key, required this.steps});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          for (var i = 0; i < steps.length; i++)
            _TrackingStepTile(step: steps[i], isLast: i == steps.length - 1),
        ],
      ),
    );
  }
}

class _TrackingStepTile extends StatelessWidget {
  final TrackingStep step;
  final bool isLast;

  const _TrackingStepTile({required this.step, required this.isLast});

  /// Mapeia o `code` do model para o ícone, mantendo o model agnóstico de UI.
  IconData get _icon {
    switch (step.code) {
      case 'processed':
        return Icons.inventory_2_outlined;
      case 'in_transit':
        return Icons.local_shipping;
      case 'delivered':
        return Icons.location_on_outlined;
      default:
        return Icons.circle_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isPending = step.status == OrderStepStatus.pending;
    final isCurrent = step.status == OrderStepStatus.current;

    final iconBgColor = isPending ? AppColors.inputFill : AppColors.purple;
    final iconColor = isPending ? AppColors.textSecondary : AppColors.white;
    final titleColor = isPending
        ? AppColors.textSecondary
        : (isCurrent ? AppColors.purple : AppColors.textPrimary);
    final subtitle = step.timestamp == null
        ? null
        : OrderFormat.dayMonthTime(step.timestamp!);

    return Padding(
      padding: EdgeInsets.only(bottom: isLast ? 0 : 20),
      child: Row(
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: iconBgColor,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: isCurrent
                      ? [
                          BoxShadow(
                            color: AppColors.purple.withValues(alpha: 0.35),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ]
                      : null,
                ),
                child: Icon(_icon, color: iconColor, size: 30),
              ),
              if (isCurrent)
                Positioned(
                  top: -2,
                  right: -2,
                  child: Container(
                    width: 14,
                    height: 14,
                    decoration: BoxDecoration(
                      color: AppColors.success,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppColors.white, width: 2),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  step.title,
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: titleColor,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
