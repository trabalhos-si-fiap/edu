import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Product.fromJson parses fields and string price', () {
    final p = Product.fromJson({
      'id': 'a1b2',
      'name': 'Guia',
      'type': 'apostila',
      'subtype': 'Digital',
      'description': 'desc',
      'price': '49.90',
      'image_url': 'http://img/1.png',
      'rating_avg': 4.5,
      'rating_count': 128,
    });

    expect(p.id, 'a1b2');
    expect(p.name, 'Guia');
    expect(p.price, 49.90);
    expect(p.imageUrl, 'http://img/1.png');
    expect(p.ratingAvg, 4.5);
    expect(p.ratingCount, 128);
    expect(p.categoryLabel, 'DIGITAL');
  });

  test('Product.fromJson tolerates missing optional fields', () {
    final p = Product.fromJson({
      'id': 'x', 'name': 'N', 'type': 'curso', 'price': '0.00',
    });
    expect(p.subtype, '');
    expect(p.ratingCount, 0);
    // Sem subtype, o rótulo vem do código do tipo, em pt-BR com acento.
    expect(p.categoryLabel, 'CURSOS');
  });

  test('categoryLabelFor traduz os códigos de tipo do catálogo', () {
    expect(categoryLabelFor('mobiliario'), 'Mobiliário');
    expect(categoryLabelFor('iluminacao'), 'Iluminação');
    expect(categoryLabelFor('organizacao'), 'Organização');
    expect(categoryLabelFor('curso'), 'Cursos');
    expect(categoryLabelFor('digital'), 'Digital');
    expect(categoryLabelFor('apostila'), 'Apostilas');
    // Mesma normalização de `product_visuals.dart`: caixa e espaços não
    // mudam o tipo.
    expect(categoryLabelFor(' ILUMINACAO '), 'Iluminação');
  });

  test('categoryLabelFor capitaliza um código desconhecido', () {
    expect(categoryLabelFor('papelaria'), 'Papelaria');
    expect(categoryLabelFor('apostila_digital'), 'Apostila digital');
    expect(categoryLabelFor(''), '');
  });

  test('categoryLabel sem subtype usa o rótulo do tipo em maiúsculas', () {
    const p = Product(
      id: 'x', name: 'Mesa', type: 'mobiliario', subtype: ' ',
      description: '', price: 1.0,
    );
    expect(p.categoryLabel, 'MOBILIÁRIO');
  });

  test('Review.fromJson parses fields', () {
    final r = Review.fromJson({
      'id': 'r1',
      'author': 'Ana',
      'rating': 5,
      'comment': 'Ótimo',
      'created_at': '2026-03-12T00:00:00Z',
    });
    expect(r.id, 'r1');
    expect(r.author, 'Ana');
    expect(r.rating, 5);
    expect(r.comment, 'Ótimo');
    expect(r.createdAt, '2026-03-12T00:00:00Z');
  });
}
