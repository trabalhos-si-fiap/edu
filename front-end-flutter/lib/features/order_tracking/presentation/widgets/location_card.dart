import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../domain/order_model.dart';
import 'order_format.dart';

/// Card de "Última Localização" com um mapa estilizado e o botão "Ver mapa".
class LocationCard extends StatelessWidget {
  final TrackingLocation location;
  final VoidCallback? onOpenMap;

  const LocationCard({super.key, required this.location, this.onOpenMap});

  @override
  Widget build(BuildContext context) {
    final updated = location.updatedAt;
    final subtitle = [
      location.cityState,
      if (updated != null) 'Atualizado ${OrderFormat.relativeFromNow(updated)}',
    ].where((s) => s.trim().isNotEmpty).join(' • ');

    return Container(
      width: double.infinity,
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
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: Stack(
                children: [
                  Container(
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          Color(0xFFD7E3F2),
                          Color(0xFFC2D6EA),
                          Color(0xFFB0C8E0),
                        ],
                      ),
                    ),
                  ),
                  CustomPaint(painter: _MapLinesPainter(), size: Size.infinite),
                  const Center(
                    child: Icon(
                      Icons.location_on,
                      color: AppColors.purple,
                      size: 48,
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.purpleSoft,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(
                        Icons.place_outlined,
                        color: AppColors.purple,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Última Localização',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppColors.textSecondary,
                              letterSpacing: 0.5,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            location.name,
                            style: const TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            subtitle,
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: onOpenMap,
                    icon: const Icon(
                      Icons.map_outlined,
                      size: 18,
                      color: AppColors.purple,
                    ),
                    label: const Text(
                      'Ver mapa',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: AppColors.purple,
                      ),
                    ),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: const BorderSide(
                        color: AppColors.purple,
                        width: 1.5,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Desenha linhas/rota estilizadas sobre o "mapa" de fundo.
class _MapLinesPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.white.withValues(alpha: 0.45)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    final h = size.height;
    final w = size.width;

    canvas.drawLine(Offset(0, h * 0.35), Offset(w, h * 0.25), paint);
    canvas.drawLine(Offset(0, h * 0.7), Offset(w, h * 0.6), paint);
    canvas.drawLine(Offset(w * 0.3, 0), Offset(w * 0.5, h), paint);
    canvas.drawLine(Offset(w * 0.75, 0), Offset(w * 0.9, h), paint);

    final dashed = Paint()
      ..color = AppColors.purple.withValues(alpha: 0.6)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;

    final path = Path()
      ..moveTo(w * 0.15, h * 0.8)
      ..quadraticBezierTo(w * 0.35, h * 0.3, w * 0.5, h * 0.5);
    _drawDashedPath(canvas, path, dashed);
  }

  void _drawDashedPath(Canvas canvas, Path path, Paint paint) {
    const dash = 6.0;
    const gap = 4.0;
    for (final metric in path.computeMetrics()) {
      double d = 0;
      while (d < metric.length) {
        canvas.drawPath(
          metric.extractPath(d, (d + dash).clamp(0, metric.length)),
          paint,
        );
        d += dash + gap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
