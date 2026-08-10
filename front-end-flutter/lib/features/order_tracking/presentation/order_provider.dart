import 'dart:async';

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
///
/// O status do pedido avança no backend ao longo do tempo (pipeline de
/// timers: confirmado -> em separação -> saiu para entrega -> entregue). Como
/// não há canal em tempo real, o provider faz *polling* do endpoint enquanto o
/// pedido não foi entregue, fazendo a tela reagir às transições de status.
class OrderProvider extends ChangeNotifier {
  OrderProvider({OrderService? service, Duration? pollInterval})
    : _service = service ?? OrderService(),
      _pollInterval = pollInterval ?? const Duration(seconds: 8);

  final OrderService _service;
  final Duration _pollInterval;

  OrderViewState _state = OrderViewState.loading;
  OrderViewState get state => _state;

  OrderModel? _order;
  OrderModel? get order => _order;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  String? _orderId;
  Timer? _pollTimer;
  bool _disposed = false;

  /// Carrega o rastreio do pedido. Reutilizada por [retry], que reaproveita o
  /// último [orderId] solicitado. Em caso de sucesso, inicia o polling até o
  /// pedido ser entregue.
  Future<void> load(String orderId) async {
    _orderId = orderId;
    _state = OrderViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _order = await _service.fetchTracking(orderId);
      _state = OrderViewState.success;
      _startPolling();
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

  /// (Re)agenda o polling. Não faz nada se o pedido já foi entregue ou
  /// cancelado — não há mais transições a aguardar. Um pedido cancelado
  /// deixa a timeline inteira PENDING, então `isDelivered` sozinho nunca
  /// pega esse caso (ver `isCancelled` em `order_model.dart`).
  void _startPolling() {
    _pollTimer?.cancel();
    if (_order?.isDelivered ?? false) return;
    if (_order?.isCancelled ?? false) return;
    _pollTimer = Timer.periodic(_pollInterval, (_) => _poll());
  }

  /// Busca silenciosa do status atual: não volta para o estado de loading nem
  /// derruba a tela em caso de falha de rede — mantém o último dado bom e tenta
  /// de novo no próximo tick. Para o polling assim que o pedido é entregue ou
  /// cancelado.
  Future<void> _poll() async {
    final id = _orderId;
    if (id == null) return;
    try {
      final fresh = await _service.fetchTracking(id);
      if (_disposed) return;
      _order = fresh;
      _state = OrderViewState.success;
      notifyListeners();
      if (fresh.isDelivered || fresh.isCancelled) _pollTimer?.cancel();
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
