import 'package:flutter/foundation.dart';

import '../domain/payment_method.dart';

/// Armazena os métodos de pagamento em memória.
///
/// Portado do `PaymentMethodViewModel` + `PaymentMethodLocalStore` do edu-kt.
/// Sem persistência (dados mockados) — começa semeado com um cartão padrão para
/// que o checkout tenha algo selecionável. Exposto via `ChangeNotifierProvider`
/// (pacote `provider`) e lido com `context.watch`/`context.read<PaymentStore>()`.
class PaymentStore extends ChangeNotifier {
  PaymentStore() {
    _seed();
  }

  final List<PaymentMethod> _methods = [];
  int _counter = 0;

  List<PaymentMethod> get methods => List.unmodifiable(_methods);

  String _nextId() => 'pm_${_counter++}';

  void _seed() {
    _methods.add(
      PaymentMethod(
        id: _nextId(),
        type: PaymentMethodType.creditCard,
        isDefault: true,
        cardLast4: '4492',
        cardBrand: 'Visa',
        cardholderName: 'MARIA SILVA',
        cardExpiry: '1228',
      ),
    );
  }

  PaymentMethod? byId(String id) {
    for (final m in _methods) {
      if (m.id == id) return m;
    }
    return null;
  }

  void _clearDefaults() {
    for (var i = 0; i < _methods.length; i++) {
      if (_methods[i].isDefault) {
        _methods[i] = _methods[i].copyWith(isDefault: false);
      }
    }
  }

  void add(PaymentMethod method, {bool makeDefault = false}) {
    final shouldDefault = makeDefault || _methods.isEmpty;
    if (shouldDefault) _clearDefaults();
    _methods.add(method.copyWith(id: _nextId(), isDefault: shouldDefault));
    notifyListeners();
  }

  void update(PaymentMethod method, {bool makeDefault = false}) {
    final idx = _methods.indexWhere((m) => m.id == method.id);
    if (idx < 0) return;
    if (makeDefault) _clearDefaults();
    _methods[idx] = method.copyWith(
      isDefault: makeDefault ? true : _methods[idx].isDefault,
    );
    notifyListeners();
  }

  void delete(String id) {
    final removed = byId(id);
    _methods.removeWhere((m) => m.id == id);
    // Se removemos o padrão, promove o primeiro restante.
    if (removed?.isDefault == true &&
        _methods.isNotEmpty &&
        _methods.every((m) => !m.isDefault)) {
      _methods[0] = _methods[0].copyWith(isDefault: true);
    }
    notifyListeners();
  }

  void setDefault(String id) {
    _clearDefaults();
    final idx = _methods.indexWhere((m) => m.id == id);
    if (idx >= 0) _methods[idx] = _methods[idx].copyWith(isDefault: true);
    notifyListeners();
  }
}
