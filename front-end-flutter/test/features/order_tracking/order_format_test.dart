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

  group('OrderFormat mostra instantes da API no fuso local', () {
    // 22:32 de 13/09 em São Paulo (UTC-3), do jeito que o backend manda: UTC.
    final utc = DateTime.utc(2026, 9, 14, 1, 32);
    const saoPaulo = Duration(hours: -3);

    test('dayMonthTime usa o relógio local, não o UTC', () {
      expect(OrderFormat.dayMonthTime(utc, utcOffset: saoPaulo), '13 Set, 22:32');
    });

    test('dayMonth usa o dia local', () {
      expect(OrderFormat.dayMonth(utc, utcOffset: saoPaulo), '13 Set');
    });

    test('estimatedArrivalLabel compara dias locais', () {
      final label = OrderFormat.estimatedArrivalLabel(
        utc,
        now: DateTime.utc(2026, 9, 13, 15, 0),
        utcOffset: saoPaulo,
      );
      expect(label, 'hoje, ~22:32');
    });

    test('uma data já local sai como está', () {
      expect(OrderFormat.dayMonthTime(DateTime(2026, 9, 13, 22, 32)), '13 Set, 22:32');
    });

    test('sem utcOffset, vale o fuso do aparelho', () {
      expect(OrderFormat.dayMonthTime(utc), OrderFormat.dayMonthTime(utc.toLocal()));
    });
  });
}
