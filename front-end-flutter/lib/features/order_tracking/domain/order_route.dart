import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../data/polyline_codec.dart';

/// A named endpoint of the delivery route (origin or destination).
class RoutePoint {
  final String label;
  final double latitude;
  final double longitude;

  const RoutePoint({
    required this.label,
    required this.latitude,
    required this.longitude,
  });

  factory RoutePoint.fromJson(Map<String, dynamic> json) => RoutePoint(
    label: (json['label'] as String?) ?? '',
    latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
    longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
  );

  LatLng get latLng => LatLng(latitude, longitude);
}

/// Street route between the distribution center and the order destination,
/// mirroring the backend `RouteOut` schema (`GET /orders/{id}/route`).
class OrderRoute {
  final RoutePoint origin;
  final RoutePoint destination;
  final String polyline;
  final String distanceText;
  final double distanceKm;
  final String durationText;
  final int durationMinutes;

  const OrderRoute({
    required this.origin,
    required this.destination,
    required this.polyline,
    required this.distanceText,
    required this.distanceKm,
    required this.durationText,
    required this.durationMinutes,
  });

  factory OrderRoute.fromJson(Map<String, dynamic> json) => OrderRoute(
    origin: RoutePoint.fromJson(
      (json['origin'] as Map<String, dynamic>?) ?? const {},
    ),
    destination: RoutePoint.fromJson(
      (json['destination'] as Map<String, dynamic>?) ?? const {},
    ),
    polyline: (json['polyline'] as String?) ?? '',
    distanceText: (json['distance_text'] as String?) ?? '',
    distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
    durationText: (json['duration_text'] as String?) ?? '',
    durationMinutes: (json['duration_minutes'] as int?) ?? 0,
  );

  /// The route geometry, decoded from the encoded [polyline].
  List<LatLng> get polylinePoints => decodePolyline(polyline);
}
