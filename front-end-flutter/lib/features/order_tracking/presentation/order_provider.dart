import 'package:flutter/foundation.dart';

import '../data/order_service.dart';
import '../domain/order_model.dart';

/// Estados possíveis da requisição de rastreio, consumidos pela View para
/// decidir entre loading / success / error.
enum OrderViewState { loading, success, error }

/// Gerencia o estado da Tela de Acompanhamento de Pedido.
///
/// Concentra toda a regra de negócio (qual estado mostrar, quando recarregar,
/// como mapear erros) fora da camada de UI. A View apenas observa
/// [state]/[order]/[errorMessage] e dispara [load]/[retry].
class OrderProvider extends ChangeNotifier {
  OrderProvider({OrderService? service})
    : _service = service ?? OrderService();

  final OrderService _service;

  OrderViewState _state = OrderViewState.loading;
  OrderViewState get state => _state;

  OrderModel? _order;
  OrderModel? get order => _order;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  String? _orderId;

  /// Carrega o rastreio do pedido. Reutilizada por [retry], que reaproveita o
  /// último [orderId] solicitado.
  Future<void> load(String orderId) async {
    _orderId = orderId;
    _state = OrderViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _order = await _service.fetchTracking(orderId);
      _state = OrderViewState.success;
    } on OrderException catch (e) {
      _errorMessage = e.message;
      _state = OrderViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = OrderViewState.error;
    }
    notifyListeners();
  }

  /// Reexecuta a última busca (botão "Tentar Novamente").
  Future<void> retry() async {
    final id = _orderId;
    if (id == null) return;
    await load(id);
  }
}
