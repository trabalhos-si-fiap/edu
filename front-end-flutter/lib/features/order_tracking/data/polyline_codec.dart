import 'package:google_maps_flutter/google_maps_flutter.dart';

/// Decodes a Google "encoded polyline" string into a list of [LatLng].
///
/// Implements the standard algorithm
/// (https://developers.google.com/maps/documentation/utilities/polylinealgorithm)
/// inline to avoid pulling an extra package for ~20 lines of logic.
List<LatLng> decodePolyline(String encoded) {
  final points = <LatLng>[];
  int index = 0;
  int lat = 0;
  int lng = 0;

  while (index < encoded.length) {
    lat += _nextDelta(encoded, () => index, (v) => index = v);
    lng += _nextDelta(encoded, () => index, (v) => index = v);
    points.add(LatLng(lat / 1e5, lng / 1e5));
  }
  return points;
}

/// Reads one zig-zag-encoded varint starting at the current index, advancing
/// it via [setIndex], and returns the signed delta.
int _nextDelta(String encoded, int Function() getIndex, void Function(int) setIndex) {
  int index = getIndex();
  int shift = 0;
  int result = 0;
  int byte;
  do {
    byte = encoded.codeUnitAt(index++) - 63;
    result |= (byte & 0x1f) << shift;
    shift += 5;
  } while (byte >= 0x20);
  setIndex(index);
  return (result & 1) != 0 ? ~(result >> 1) : (result >> 1);
}
