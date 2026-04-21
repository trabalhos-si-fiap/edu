import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  static const Color primary = Color(0xFF1A1A2E);
  static const Color blue = Color(0xFF369FFF);
  static const Color purple = Color(0xFF5B00DF);
  static const Color background = Color(0xFFA9CADD);
  static const Color white = Color(0xFFFFFFFF);
  static const Color textPrimary = Color(0xFF1A1A2E);
  static const Color textSecondary = Color(0xFF6B7280);
  static const Color inputFill = Color(0xFFF3F4F6);
  static const Color inputBorder = Color(0xFFE5E7EB);

  static const LinearGradient headerGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      Color(0xFFA9CADD),
      Color(0xFFBDD5E5),
      Color(0xFFD1E0EE),
    ],
  );
}
