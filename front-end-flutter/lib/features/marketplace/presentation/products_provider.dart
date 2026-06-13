import 'package:flutter/foundation.dart';

import '../data/product_service.dart';
import '../domain/product.dart';

enum ProductsViewState { loading, success, error }

/// Estado do catálogo do marketplace: carrega os produtos uma vez e filtra
/// client-side por busca e categoria (mesma UX do mock anterior).
class ProductsProvider extends ChangeNotifier {
  ProductsProvider({ProductService? service})
    : _service = service ?? ProductService();

  final ProductService _service;

  ProductsViewState _state = ProductsViewState.loading;
  List<Product> _products = const [];
  String? _errorMessage;
  String _query = '';
  String? _type;

  ProductsViewState get state => _state;
  List<Product> get products => _products;
  String? get errorMessage => _errorMessage;
  String get query => _query;
  String? get selectedType => _type;

  List<String> get types => _products
      .map((p) => p.type)
      .where((t) => t.isNotEmpty)
      .toSet()
      .toList();

  List<Product> get visibleProducts {
    final q = _query.trim().toLowerCase();
    return _products.where((p) {
      final matchesType = _type == null || p.type == _type;
      final matchesQuery = q.isEmpty ||
          p.name.toLowerCase().contains(q) ||
          p.description.toLowerCase().contains(q);
      return matchesType && matchesQuery;
    }).toList();
  }

  Future<void> load() async {
    _state = ProductsViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _products = await _service.fetchProducts();
      _state = ProductsViewState.success;
    } on ProductException catch (e) {
      _errorMessage = e.message;
      _state = ProductsViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = ProductsViewState.error;
    }
    notifyListeners();
  }

  void setQuery(String value) {
    _query = value;
    notifyListeners();
  }

  void setType(String? value) {
    _type = value;
    notifyListeners();
  }
}
