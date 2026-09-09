import 'dart:async';

import 'package:flutter/foundation.dart';

import '../data/order_service.dart';
import '../data/route_service.dart';
import '../domain/order_model.dart';
import '../domain/order_route.dart';

/// Estados da requisição da rota do mapa, consumidos pela tela do mapa.
enum RouteViewState { loading, success, error }

/// Gerencia o estado da Tela do Mapa do Pedido. Espelha o [OrderProvider]:
/// a View observa [state]/[route]/[errorMessage] e dispara [load]/[retry].
///
/// Além da rota (carregada uma vez, como antes), o provider acompanha a
/// posição da transportadora: faz *polling* de `GET /orders/{id}/tracking`
/// — a mesma rota que a tela de rastreio já consulta, via [OrderService] —
/// a cada dez segundos (spec), expondo [courierPosition]. O `OrderProvider`
/// do rastreio faz o mesmo com 8 s; os dois não se coordenam de propósito,
/// são telas diferentes. O polling da posição para quando o pedido é
/// entregue ou cancelado, reusando exatamente o critério de
/// [OrderProvider._startPolling] (`isDelivered`/`isCancelled`), e uma falha
/// de rede no meio do caminho preserva a última posição boa e tenta de novo
/// no próximo tick — mesma tolerância de [OrderProvider._poll]. Nada é
/// inventado no cliente: sem interpolação, o marcador fica onde o backend
/// disse por último.
class RouteProvider extends ChangeNotifier {
  RouteProvider({
    RouteService? service,
    OrderService? orderService,
    Duration? positionInterval,
  }) : _service = service ?? RouteService(),
       _orderService = orderService ?? OrderService(),
       _positionInterval = positionInterval ?? const Duration(seconds: 10);

  final RouteService _service;
  final OrderService _orderService;
  final Duration _positionInterval;

  RouteViewState _state = RouteViewState.loading;
  RouteViewState get state => _state;

  OrderRoute? _route;
  OrderRoute? get route => _route;

  CourierPosition? _courierPosition;
  CourierPosition? get courierPosition => _courierPosition;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  String? _orderId;
  Timer? _positionTimer;
  bool _disposed = false;

  Future<void> load(String orderId) async {
    _orderId = orderId;
    _state = RouteViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      final route = await _service.fetchRoute(orderId);
      // A tela pode ter sido fechada (dispose()) enquanto a rota ainda
      // carregava. Sem esta checagem, o código abaixo criaria um
      // Timer.periodic que nada mais cancela (dispose() já rodou e não há
      // um segundo dispose() por vir) e chamaria notifyListeners() num
      // ChangeNotifier já descartado.
      if (_disposed) return;
      _route = route;
      _state = RouteViewState.success;
      _startPositionPolling();
    } on RouteException catch (e) {
      if (_disposed) return;
      _errorMessage = e.message;
      _state = RouteViewState.error;
    } catch (_) {
      if (_disposed) return;
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

  /// (Re)agenda o polling da posição. Não há como saber de antemão se o
  /// pedido já está entregue/cancelado (a rota não carrega o status do
  /// contrato) — o próprio [_pollPosition] cancela o timer assim que
  /// detectar um desses estados.
  void _startPositionPolling() {
    _positionTimer?.cancel();
    _positionTimer = Timer.periodic(_positionInterval, (_) => _pollPosition());
  }

  /// Busca silenciosa da posição: não derruba a tela em caso de falha de
  /// rede — mantém a última posição boa e tenta de novo no próximo tick.
  /// Para o polling assim que o pedido é entregue ou cancelado.
  Future<void> _pollPosition() async {
    final id = _orderId;
    if (id == null) return;
    try {
      final order = await _orderService.fetchTracking(id);
      if (_disposed) return;
      _courierPosition = order.courierPosition;
      notifyListeners();
      if (order.isDelivered || order.isCancelled) _positionTimer?.cancel();
    } catch (_) {
      // Falha transitória: preserva a última posição boa e tenta no próximo ciclo.
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _positionTimer?.cancel();
    super.dispose();
  }
}
