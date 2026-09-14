import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../../../../core/theme/app_colors.dart';

/// Renderiza um ícone Material ([icon]) dentro de um pino circular e o converte
/// em um [BitmapDescriptor]. O mapa usa dois: o armazém (`warehouse`) no ponto
/// de partida (Centro de Distribuição) e o caminhão (`local_shipping`) na
/// transportadora em movimento — com o mesmo ícone, pareciam dois caminhões.
///
/// `google_maps_flutter` não aceita um `IconData` direto, então pintamos o glifo
/// num canvas off-screen e geramos um PNG. É assíncrono (a codificação da imagem
/// é async); o chamador carrega o ícone uma vez e reusa.
Future<BitmapDescriptor> markerBitmap(
  IconData icon, {
  double size = 120,
  double displayWidth = 46,
  Color iconColor = AppColors.white,
  Color backgroundColor = AppColors.purple,
}) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  final center = Offset(size / 2, size / 2);

  // Pino circular de fundo (com uma borda branca sutil para destacar no mapa).
  canvas.drawCircle(center, size / 2, Paint()..color = AppColors.white);
  canvas.drawCircle(center, size / 2 - size * 0.06, Paint()..color = backgroundColor);

  final painter = TextPainter(textDirection: TextDirection.ltr)
    ..text = TextSpan(
      text: String.fromCharCode(icon.codePoint),
      style: TextStyle(
        fontSize: size * 0.52,
        fontFamily: icon.fontFamily,
        package: icon.fontPackage,
        color: iconColor,
      ),
    )
    ..layout();
  painter.paint(
    canvas,
    Offset((size - painter.width) / 2, (size - painter.height) / 2),
  );

  final image = await recorder.endRecording().toImage(size.toInt(), size.toInt());
  final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
  // Render at high resolution (size) but display at displayWidth logical px so
  // the marker stays sharp yet proportional to the default destination pin.
  return BitmapDescriptor.bytes(
    bytes!.buffer.asUint8List(),
    width: displayWidth,
  );
}
