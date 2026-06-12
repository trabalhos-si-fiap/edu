import 'package:flutter/foundation.dart';

import '../../marketplace/domain/product.dart';
import '../domain/cart_item.dart';

/// Estado do carrinho compartilhado entre marketplace, detalhe e checkout.
///
/// Portado do `CartViewModel` do edu-kt. Exposto na árvore via
/// `ChangeNotifierProvider` (pacote `provider`); as telas leem com
/// `context.watch<CartStore>()` (rebuild) ou `context.read<CartStore>()` (ações).
class CartStore extends ChangeNotifier {
  CartStore();

  final List<CartItem> _items = [];

  List<CartItem> get items => List.unmodifiable(_items);
  bool get isEmpty => _items.isEmpty;
  int get totalQuantity => _items.fold(0, (sum, i) => sum + i.quantity);
  double get total => _items.fold(0.0, (sum, i) => sum + i.subtotal);

  int _indexOf(int productId) =>
      _items.indexWhere((i) => i.product.id == productId);

  void add(Product product, [int quantity = 1]) {
    final idx = _indexOf(product.id);
    if (idx >= 0) {
      _items[idx] = _items[idx].copyWith(
        quantity: _items[idx].quantity + quantity,
      );
    } else {
      _items.add(CartItem(product: product, quantity: quantity));
    }
    notifyListeners();
  }

  void decrement(int productId) {
    final idx = _indexOf(productId);
    if (idx < 0) return;
    final next = _items[idx].quantity - 1;
    if (next <= 0) {
      _items.removeAt(idx);
    } else {
      _items[idx] = _items[idx].copyWith(quantity: next);
    }
    notifyListeners();
  }

  void removeAll(int productId) {
    final idx = _indexOf(productId);
    if (idx < 0) return;
    _items.removeAt(idx);
    notifyListeners();
  }

  void clear() {
    if (_items.isEmpty) return;
    _items.clear();
    notifyListeners();
  }
}
