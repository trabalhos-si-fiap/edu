import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Product.fromJson maps snake_case fields', () {
    final p = Product.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'name': 'Guia',
      'type': 'apostila',
      'subtype': 'Digital',
      'description': 'desc',
      'price': '49.90',
      'image_url': 'https://signed/url',
      'rating_avg': 4.5,
      'rating_count': 128,
    });
    expect(p.id, '11111111-1111-1111-1111-111111111111');
    expect(p.price, 49.90);
    expect(p.imageUrl, 'https://signed/url');
    expect(p.ratingCount, 128);
  });

  test('Review.fromJson maps fields', () {
    final r = Review.fromJson({
      'id': '22222222-2222-2222-2222-222222222222',
      'author': 'Ana',
      'rating': 5,
      'comment': 'ótimo',
      'created_at': '2025-03-12T10:00:00Z',
    });
    expect(r.id, '22222222-2222-2222-2222-222222222222');
    expect(r.rating, 5);
  });
}
