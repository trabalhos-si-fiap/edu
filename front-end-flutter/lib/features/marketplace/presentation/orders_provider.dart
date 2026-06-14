import 'dart:async';

import 'package:flutter/foundation.dart';

import '../data/order_list_service.dart';
import '../domain/order_summary.dart';

enum OrdersViewState { loading, success, error }

/// Estado da tela "Seus pedidos": carrega a lista de pedidos do usuário e a
/// separa entre pedidos ativos (em andamento) e já entregues, para a UI.
///
/// O status de cada pedido avança no backend ao longo do tempo (pipeline de
/// timers). Como não há canal em tempo real, o provider faz *polling* da lista
/// enquanto houver ao menos um pedido ativo, fazendo os cards reagirem às
/// transições de status. O polling para quando todos os pedidos foram entregues.
class OrdersProvider extends ChangeNotifier {
  OrdersProvider({OrderListService? service, Duration? pollInterval})
    : _service = service ?? OrderListService(),
      _pollInterval = pollInterval ?? const Duration(seconds: 8);

  final OrderListService _service;
  final Duration _pollInterval;

  OrdersViewState _state = OrdersViewState.loading;
  List<OrderSummary> _orders = const [];
  String? _errorMessage;

  Timer? _pollTimer;
  bool _disposed = false;

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
      _startPolling();
    } on OrderListException catch (e) {
      _errorMessage = e.message;
      _state = OrdersViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = OrdersViewState.error;
    }
    notifyListeners();
  }

  /// (Re)agenda o polling. Não faz nada se não há pedido ativo — não há mais
  /// transições a aguardar.
  void _startPolling() {
    _pollTimer?.cancel();
    if (activeOrders.isEmpty) return;
    _pollTimer = Timer.periodic(_pollInterval, (_) => _poll());
  }

  /// Recarga silenciosa: não volta para o estado de loading nem derruba a tela
  /// em caso de falha de rede — mantém o último dado bom e tenta de novo no
  /// próximo tick. Para o polling assim que todos os pedidos foram entregues.
  Future<void> _poll() async {
    try {
      final fresh = await _service.fetchOrders();
      if (_disposed) return;
      _orders = fresh;
      _state = OrdersViewState.success;
      notifyListeners();
      if (activeOrders.isEmpty) _pollTimer?.cancel();
    } catch (_) {
      // Falha transitória: preserva o estado atual e tenta no próximo ciclo.
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _pollTimer?.cancel();
    super.dispose();
  }
}
