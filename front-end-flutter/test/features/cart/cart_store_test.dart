import 'package:edu_ia/features/cart/data/cart_service.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/cart/domain/cart_item.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id) => Product(
      id: id, name: 'P-$id', type: 'curso', subtype: '', description: '',
      price: 10.0,
    );

class _FakeCartService extends CartService {
  final List<String> calls = [];
  List<CartItem> serverItems = [];
  bool failMutations = false;

  @override
  Future<List<CartItem>> fetch() async {
    calls.add('fetch');
    return List.of(serverItems);
  }

  @override
  Future<List<CartItem>> addItem(String productId, int quantity) async {
    calls.add('addItem:$productId:$quantity');
    if (failMutations) throw CartException('boom');
    return List.of(serverItems);
  }

  @override
  Future<List<CartItem>> removeItem(String productId, {int? quantity}) async {
    calls.add('removeItem:$productId:${quantity ?? 'all'}');
    if (failMutations) throw CartException('boom');
    return List.of(serverItems);
  }
}

void main() {
  test('add updates local state immediately and writes through', () async {
    final service = _FakeCartService();
    final cart = CartStore(service: service);

    cart.add(_p('a'), 2);

    expect(cart.totalQuantity, 2); // optimistic, synchronous
    expect(cart.items, hasLength(1));
    await pumpEventQueue();
    expect(service.calls, contains('addItem:a:2'));
  });

  test('add increments quantity for the same product id', () {
    final cart = CartStore(service: _FakeCartService());
    cart.add(_p('a'));
    cart.add(_p('a'), 2);
    expect(cart.totalQuantity, 3);
    expect(cart.items, hasLength(1));
    expect(cart.total, 30.0);
  });

  test('decrement removes the line when it reaches zero', () {
    final cart = CartStore(service: _FakeCartService());
    cart.add(_p('a'));
    cart.decrement('a');
    expect(cart.isEmpty, isTrue);
  });

  test('removeAll drops the whole line', () {
    final cart = CartStore(service: _FakeCartService());
    cart.add(_p('a'), 3);
    cart.removeAll('a');
    expect(cart.isEmpty, isTrue);
  });

  test('load populates items and is guarded unless forced', () async {
    final service = _FakeCartService()
      ..serverItems = [CartItem(product: _p('a'), quantity: 4)];
    final cart = CartStore(service: service);

    await cart.load();
    expect(cart.totalQuantity, 4);
    expect(service.calls, ['fetch']);

    await cart.load(); // guarded
    expect(service.calls, ['fetch']);

    await cart.load(force: true);
    expect(service.calls, ['fetch', 'fetch']);
  });

  test('mutation failure resyncs from the server and sets errorMessage',
      () async {
    final service = _FakeCartService()
      ..serverItems = [] // server cart is empty
      ..failMutations = true;
    final cart = CartStore(service: service);

    cart.add(_p('a'));
    expect(cart.totalQuantity, 1); // optimistic

    await pumpEventQueue();
    expect(cart.errorMessage, isNotNull);
    expect(service.calls, contains('fetch')); // resync via load(force: true)
    expect(cart.isEmpty, isTrue); // resynced to the empty server cart
  });

  test('clear zeroes local state without calling the service', () {
    final service = _FakeCartService();
    final cart = CartStore(service: service)..add(_p('a'));
    service.calls.clear();

    cart.clear();

    expect(cart.isEmpty, isTrue);
    expect(service.calls, isEmpty);
  });

  test('successful write keeps optimistic state (does not adopt server response)',
      () async {
    // serverItems is empty — a divergent snapshot from what the optimistic
    // mutation produces. If _sync adopted the server response on success, the
    // cart would become empty after the write.
    final service = _FakeCartService()
      ..serverItems = []
      ..failMutations = false;
    final cart = CartStore(service: service);

    cart.add(_p('a'));
    expect(cart.totalQuantity, 1); // optimistic state

    await pumpEventQueue(); // let _sync complete

    // Must still reflect optimistic state, NOT the empty serverItems snapshot.
    expect(cart.totalQuantity, 1);
    expect(cart.items, hasLength(1));
  });

  test('writes are serialized in tap order', () async {
    final service = _FakeCartService();
    final cart = CartStore(service: service);

    cart.add(_p('a'));
    cart.add(_p('b'));
    cart.removeAll('a');

    await pumpEventQueue();

    expect(service.calls, ['addItem:a:1', 'addItem:b:1', 'removeItem:a:all']);
  });

  test('reset clears items, loaded flag and error', () async {
    final service = _FakeCartService()
      ..serverItems = [CartItem(product: _p('z'), quantity: 2)];
    final cart = CartStore(service: service);

    await cart.load();
    expect(cart.isEmpty, isFalse);
    expect(service.calls, ['fetch']);

    cart.reset();

    expect(cart.isEmpty, isTrue);

    // _loaded was cleared — next load() must refetch.
    await cart.load();
    expect(service.calls, ['fetch', 'fetch']);
  });
}
