import 'package:flutter/foundation.dart';

import '../data/route_service.dart';
import '../domain/order_route.dart';

/// Estados da requisição da rota do mapa, consumidos pela tela do mapa.
enum RouteViewState { loading, success, error }

/// Gerencia o estado da Tela do Mapa do Pedido. Espelha o [OrderProvider]:
/// a View observa [state]/[route]/[errorMessage] e dispara [load]/[retry].
class RouteProvider extends ChangeNotifier {
  RouteProvider({RouteService? service}) : _service = service ?? RouteService();

  final RouteService _service;

  RouteViewState _state = RouteViewState.loading;
  RouteViewState get state => _state;

  OrderRoute? _route;
  OrderRoute? get route => _route;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  String? _orderId;

  Future<void> load(String orderId) async {
    _orderId = orderId;
    _state = RouteViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _route = await _service.fetchRoute(orderId);
      _state = RouteViewState.success;
    } on RouteException catch (e) {
      _errorMessage = e.message;
      _state = RouteViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = RouteViewState.error;
    }
    notifyListeners();
  }

  Future<void> retry() async {
    final id = _orderId;
    if (id == null) return;
    await load(id);
  }
}
