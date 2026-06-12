import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../domain/order_model.dart';

/// Card "Conteúdo do Kit" com a lista de itens e a transportadora.
class KitContentCard extends StatelessWidget {
  final List<KitItem> kit;
  final String carrier;

  const KitContentCard({super.key, required this.kit, required this.carrier});

  /// Ícone por posição (1º item = apostila, 2º = caderno, ...), com fallback.
  IconData _iconFor(int index) {
    const icons = [Icons.menu_book_outlined, Icons.edit_note_outlined];
    return index < icons.length ? icons[index] : Icons.inventory_2_outlined;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Conteúdo do Kit',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 16),
          for (var i = 0; i < kit.length; i++) ...[
            if (i > 0) const SizedBox(height: 12),
            _KitItemTile(icon: _iconFor(i), label: kit[i].name),
          ],
          const SizedBox(height: 16),
          const Divider(height: 1, color: AppColors.inputBorder),
          const SizedBox(height: 16),
          const Text(
            'TRANSPORTADORA',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: AppColors.textSecondary,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            carrier,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

class _KitItemTile extends StatelessWidget {
  final IconData icon;
  final String label;

  const _KitItemTile({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.white,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: AppColors.purple, size: 20),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
        ),
      ],
    );
  }
}
