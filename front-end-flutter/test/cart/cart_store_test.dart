import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id) => Product(
      id: id,
      name: 'P$id',
      type: 't',
      subtype: 's',
      description: 'd',
      price: 10.0,
    );

void main() {
  test('add/decrement/removeAll work with string ids', () {
    final store = CartStore();
    store.add(_p('a'));
    store.add(_p('a'));
    store.add(_p('b'));
    expect(store.totalQuantity, 3);

    store.decrement('a');
    expect(store.totalQuantity, 2);

    store.removeAll('b');
    expect(store.items.length, 1);
    expect(store.items.first.product.id, 'a');
  });
}
