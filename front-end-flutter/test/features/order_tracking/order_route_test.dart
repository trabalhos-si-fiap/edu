import 'package:edu_ia/features/order_tracking/domain/order_route.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('OrderRoute.fromJson parses the backend contract', () {
    final route = OrderRoute.fromJson({
      'origin': {
        'label': 'Centro de Distribuição',
        'latitude': -23.3558,
        'longitude': -46.8769,
      },
      'destination': {
        'label': 'Endereço de entrega',
        'latitude': -23.561414,
        'longitude': -46.655881,
      },
      'polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
      'distance_text': '32 km',
      'distance_km': 32.4,
      'duration_text': '48 min',
      'duration_minutes': 48,
    });

    expect(route.origin.label, 'Centro de Distribuição');
    expect(route.origin.latitude, -23.3558);
    expect(route.destination.longitude, -46.655881);
    expect(route.distanceText, '32 km');
    expect(route.durationMinutes, 48);
    // Decoded lazily from the encoded polyline.
    expect(route.polylinePoints.length, 3);
  });
}
