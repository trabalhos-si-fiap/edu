import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id) => Product(
  id: id, name: 'P-$id', type: 'curso', subtype: '', description: '',
  price: 10.0,
);

void main() {
  test('add increments quantity for the same product id', () {
    final cart = CartStore();
    cart.add(_p('a'));
    cart.add(_p('a'), 2);
    expect(cart.totalQuantity, 3);
    expect(cart.items, hasLength(1));
    expect(cart.total, 30.0);
  });

  test('decrement removes the line when it reaches zero', () {
    final cart = CartStore();
    cart.add(_p('a'));
    cart.decrement('a');
    expect(cart.isEmpty, isTrue);
  });

  test('removeAll drops the whole line', () {
    final cart = CartStore();
    cart.add(_p('a'), 3);
    cart.removeAll('a');
    expect(cart.isEmpty, isTrue);
  });
}
