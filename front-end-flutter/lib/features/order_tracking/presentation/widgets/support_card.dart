import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Card escuro de suporte ("Alguma dúvida sobre o envio?").
class SupportCard extends StatelessWidget {
  final VoidCallback? onContactSupport;

  const SupportCard({super.key, this.onContactSupport});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: AppColors.purple,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.support_agent,
                color: AppColors.white,
                size: 32,
              ),
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'Alguma dúvida sobre o envio?',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w800,
              color: AppColors.white,
              height: 1.2,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Posso ajudar a reagendar a entrega ou tirar dúvidas sobre o '
            'material que está chegando.',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.white.withValues(alpha: 0.7),
              height: 1.5,
            ),
          ),
          const SizedBox(height: 20),
          Align(
            alignment: Alignment.centerRight,
            child: ElevatedButton(
              onPressed: onContactSupport,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purpleSoft,
                foregroundColor: AppColors.purple,
                elevation: 0,
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 16,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                'Falar com suporte',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
