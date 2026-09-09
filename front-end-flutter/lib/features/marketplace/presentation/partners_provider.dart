import 'package:flutter/foundation.dart';

import '../data/partner_service.dart';
import '../domain/partner.dart';
import '../domain/product.dart';

enum PartnersViewState { loading, success, error }

/// Estado da seção de parceiros do marketplace: busca quem está ativo e, em
/// paralelo, o catálogo de cada um — a lista é curta e uma chamada por
/// parceiro em série somaria latência visível.
class PartnersProvider extends ChangeNotifier {
  PartnersProvider({PartnerService? service})
    : _service = service ?? PartnerService();

  final PartnerService _service;

  PartnersViewState _state = PartnersViewState.loading;
  List<Partner> _partners = const [];
  Map<int, List<Product>> _productsByPartner = const {};
  String? _errorMessage;

  PartnersViewState get state => _state;
  List<Partner> get partners => _partners;
  Map<int, List<Product>> get productsByPartner => _productsByPartner;
  String? get errorMessage => _errorMessage;

  Future<void> load() async {
    _state = PartnersViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      final partners = await _service.fetchActivePartners();
      final productsPerPartner = await Future.wait(
        partners.map((p) => _service.fetchPartnerProducts(p.id)),
      );
      _partners = partners;
      _productsByPartner = {
        for (var i = 0; i < partners.length; i++) partners[i].id: productsPerPartner[i],
      };
      _state = PartnersViewState.success;
    } on PartnerException catch (e) {
      _errorMessage = e.message;
      _state = PartnersViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = PartnersViewState.error;
    }
    notifyListeners();
  }
}
