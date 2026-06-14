import 'package:flutter/foundation.dart';

import '../../marketplace/domain/product.dart';
import '../domain/cart_item.dart';
import 'cart_service.dart';

/// Estado do carrinho, com o backend como fonte da verdade.
///
/// Exposto na árvore via `ChangeNotifierProvider`. As mutações são otimistas:
/// o estado local muda na hora (UI instantânea) e a escrita no backend acontece
/// em segundo plano (write-through). Em caso de falha, o estado é ressincronizado
/// a partir do servidor (`load(force: true)`) e [errorMessage] é preenchido.
class CartStore extends ChangeNotifier {
  CartStore({CartService? service}) : _service = service ?? CartService();

  final CartService _service;
  final List<CartItem> _items = [];
  bool _loaded = false;

  // Escritas no backend são serializadas: uma de cada vez, na ordem dos taps,
  // evitando corrida entre POST/DELETE concorrentes.
  Future<void> _writes = Future<void>.value();

  bool _isLoading = false;
  String? _errorMessage;

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  List<CartItem> get items => List.unmodifiable(_items);
  bool get isEmpty => _items.isEmpty;
  int get totalQuantity => _items.fold(0, (sum, i) => sum + i.quantity);
  double get total => _items.fold(0.0, (sum, i) => sum + i.subtotal);

  int _indexOf(String productId) =>
      _items.indexWhere((i) => i.product.id == productId);

  /// Carrega o carrinho do backend. Roda uma vez por sessão; use [force] para
  /// recarregar (ex.: ressincronização após falha de escrita).
  Future<void> load({bool force = false}) async {
    if (_loaded && !force) return;
    _isLoading = true;
    notifyListeners();
    try {
      final items = await _service.fetch();
      _items
        ..clear()
        ..addAll(items);
      _loaded = true;
      _errorMessage = null;
    } on CartException catch (e) {
      _errorMessage = e.message;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

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
    _enqueue(() => _service.addItem(product.id, quantity));
  }

  void decrement(String productId) {
    final idx = _indexOf(productId);
    if (idx < 0) return;
    final next = _items[idx].quantity - 1;
    if (next <= 0) {
      _items.removeAt(idx);
    } else {
      _items[idx] = _items[idx].copyWith(quantity: next);
    }
    notifyListeners();
    _enqueue(() => _service.removeItem(productId, quantity: 1));
  }

  void removeAll(String productId) {
    final idx = _indexOf(productId);
    if (idx < 0) return;
    _items.removeAt(idx);
    notifyListeners();
    _enqueue(() => _service.removeItem(productId));
  }

  /// Zera o estado local. Usado após o checkout — o `POST /orders` já esvaziou
  /// o carrinho no servidor, então não há chamada de API aqui.
  void clear() {
    if (_items.isEmpty) return;
    _items.clear();
    notifyListeners();
  }

  /// Limpa o estado local e a marca de carregamento (ex.: no logout).
  void reset() {
    _items.clear();
    _loaded = false;
    _errorMessage = null;
    notifyListeners();
  }

  /// Enfileira uma operação de escrita para execução serializada.
  void _enqueue(Future<List<CartItem>> Function() op) {
    _writes = _writes.then((_) => _sync(op)).catchError((_) {});
  }

  /// Dispara a escrita no backend; em sucesso, mantém o estado otimista. Em
  /// falha, ressincroniza do servidor e preenche [errorMessage]. A mensagem é
  /// definida *depois* do resync porque `load` zera [errorMessage] no sucesso.
  /// Trade-off: em caso de falha, o carrinho é ressincronizado do servidor
  /// (fonte da verdade), o que pode descartar taps recentes não sincronizados.
  Future<void> _sync(Future<List<CartItem>> Function() op) async {
    try {
      await op();
      _errorMessage = null;
    } on CartException catch (e) {
      await load(force: true);
      _errorMessage = e.message;
      notifyListeners();
    }
  }
}
