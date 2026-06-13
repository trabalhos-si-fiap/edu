import 'package:edu_ia/features/order_tracking/presentation/widgets/order_format.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('OrderFormat.estimatedArrivalLabel', () {
    test('same day → "hoje, ~HH:MM"', () {
      final label = OrderFormat.estimatedArrivalLabel(
        DateTime(2026, 6, 13, 14, 48),
        now: DateTime(2026, 6, 13, 14, 0),
      );
      expect(label, 'hoje, ~14:48');
    });

    test('next day → "amanhã, ~HH:MM" with zero padding', () {
      final label = OrderFormat.estimatedArrivalLabel(
        DateTime(2026, 6, 14, 9, 5),
        now: DateTime(2026, 6, 13, 23, 30),
      );
      expect(label, 'amanhã, ~09:05');
    });

    test('further away → "DD Mon, ~HH:MM"', () {
      final label = OrderFormat.estimatedArrivalLabel(
        DateTime(2026, 6, 16, 14, 48),
        now: DateTime(2026, 6, 13, 10, 0),
      );
      expect(label, '16 Jun, ~14:48');
    });
  });
}
