import 'package:flutter/foundation.dart';

import '../data/order_list_service.dart';
import '../domain/order_summary.dart';

enum OrdersViewState { loading, success, error }

/// Estado da tela "Seus pedidos": carrega a lista de pedidos do usuário e a
/// separa entre pedidos ativos (em andamento) e já entregues, para a UI.
class OrdersProvider extends ChangeNotifier {
  OrdersProvider({OrderListService? service})
    : _service = service ?? OrderListService();

  final OrderListService _service;

  OrdersViewState _state = OrdersViewState.loading;
  List<OrderSummary> _orders = const [];
  String? _errorMessage;

  OrdersViewState get state => _state;
  List<OrderSummary> get orders => _orders;
  String? get errorMessage => _errorMessage;

  /// Pedidos ainda em andamento (não entregues), na ordem retornada.
  List<OrderSummary> get activeOrders =>
      _orders.where((o) => !o.isDelivered).toList();

  /// Pedidos já entregues, na ordem retornada.
  List<OrderSummary> get deliveredOrders =>
      _orders.where((o) => o.isDelivered).toList();

  /// `true` quando a carga foi bem-sucedida mas não há pedidos.
  bool get isEmpty =>
      _state == OrdersViewState.success && _orders.isEmpty;

  Future<void> load() async {
    _state = OrdersViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _orders = await _service.fetchOrders();
      _state = OrdersViewState.success;
    } on OrderListException catch (e) {
      _errorMessage = e.message;
      _state = OrdersViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = OrdersViewState.error;
    }
    notifyListeners();
  }
}
