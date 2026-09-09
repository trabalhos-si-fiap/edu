import 'package:edu_ia/features/marketplace/data/partner_service.dart';
import 'package:edu_ia/features/marketplace/domain/partner.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/partners_provider.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakePartnerService implements PartnerService {
  _FakePartnerService({this.partners = const [], this.products = const {}, this.error});

  final List<Partner> partners;
  final Map<int, List<Product>> products;
  final String? error;

  @override
  Future<List<Partner>> fetchActivePartners() async {
    if (error != null) throw PartnerException(error!);
    return partners;
  }

  @override
  Future<List<Product>> fetchPartnerProducts(int partnerId) async {
    if (error != null) throw PartnerException(error!);
    return products[partnerId] ?? const [];
  }
}

const _produto = Product(
  id: 'a',
  name: 'Luminária',
  type: 'iluminacao',
  subtype: '',
  description: '',
  price: 129.90,
);

void main() {
  test('an empty active list leaves the section empty, not broken', () async {
    final provider = PartnersProvider(service: _FakePartnerService());
    await provider.load();
    expect(provider.state, PartnersViewState.success);
    expect(provider.partners, isEmpty);
    expect(provider.errorMessage, isNull);
  });

  test('one active partner loads its catalog', () async {
    final provider = PartnersProvider(
      service: _FakePartnerService(
        partners: const [Partner(id: 2, name: 'Leroy Merlin', active: true, originLabel: 'Cajamar, SP')],
        products: const {2: [_produto]},
      ),
    );
    await provider.load();
    expect(provider.state, PartnersViewState.success);
    expect(provider.partners.single.name, 'Leroy Merlin');
    expect(provider.productsByPartner[2], hasLength(1));
  });

  test('a network error lands in the error state with a message', () async {
    final provider = PartnersProvider(
      service: _FakePartnerService(error: 'Não foi possível conectar ao servidor'),
    );
    await provider.load();
    expect(provider.state, PartnersViewState.error);
    expect(provider.errorMessage, 'Não foi possível conectar ao servidor');
  });
}
