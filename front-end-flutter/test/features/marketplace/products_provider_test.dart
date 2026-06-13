import 'package:edu_ia/features/marketplace/data/product_service.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/products_provider.dart';
import 'package:flutter_test/flutter_test.dart';

Product _p(String id, String name, String type) => Product(
  id: id, name: name, type: type, subtype: '', description: '', price: 1.0,
);

class _FakeService extends ProductService {
  _FakeService(this.products);
  final List<Product> products;
  @override
  Future<List<Product>> fetchProducts({int limit = 100}) async => products;
}

class _FailingService extends ProductService {
  @override
  Future<List<Product>> fetchProducts({int limit = 100}) async =>
      throw ProductException('boom');
}

void main() {
  test('load success populates products and derives types', () async {
    final provider = ProductsProvider(
      service: _FakeService([
        _p('a', 'Guia', 'apostila'),
        _p('b', 'Curso', 'curso'),
      ]),
    );
    await provider.load();

    expect(provider.state, ProductsViewState.success);
    expect(provider.products, hasLength(2));
    expect(provider.types, containsAll(['apostila', 'curso']));
  });

  test('load failure sets error state', () async {
    final provider = ProductsProvider(service: _FailingService());
    await provider.load();
    expect(provider.state, ProductsViewState.error);
    expect(provider.errorMessage, 'boom');
  });

  test('visibleProducts filters by query and type', () async {
    final provider = ProductsProvider(
      service: _FakeService([
        _p('a', 'Guia de Redação', 'apostila'),
        _p('b', 'Curso de Matemática', 'curso'),
      ]),
    );
    await provider.load();

    provider.setQuery('redação');
    expect(provider.visibleProducts.map((p) => p.id), ['a']);

    provider.setQuery('');
    provider.setType('curso');
    expect(provider.visibleProducts.map((p) => p.id), ['b']);
  });
}
