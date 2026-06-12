import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Ícone placeholder por tipo de produto. Portado de `iconFor` do edu-kt.
IconData iconForProduct(String type) {
  switch (type.toLowerCase()) {
    case 'apostila':
    case 'apostila_digital':
    case 'digital':
      return Icons.menu_book_outlined;
    default:
      return Icons.auto_stories_outlined;
  }
}

/// Cores (fundo, texto) da tag de categoria por tipo. Portado de `colorsFor`.
({Color background, Color foreground}) categoryColorsFor(String type) {
  switch (type.toLowerCase()) {
    case 'apostila':
    case 'apostila_digital':
    case 'digital':
      return (background: AppColors.purpleSoft, foreground: AppColors.purple);
    default:
      return (background: AppColors.greenSoft, foreground: AppColors.greenDark);
  }
}
