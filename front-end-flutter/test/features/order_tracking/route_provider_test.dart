import 'package:edu_ia/features/order_tracking/data/route_service.dart';
import 'package:edu_ia/features/order_tracking/domain/order_route.dart';
import 'package:edu_ia/features/order_tracking/presentation/route_provider.dart';
import 'package:flutter_test/flutter_test.dart';

class _OkService extends RouteService {
  _OkService() : super(useMock: true);
}

class _FailingService extends RouteService {
  _FailingService() : super();
  @override
  Future<OrderRoute> fetchRoute(String orderId) async =>
      throw RouteException('boom');
}

void main() {
  test('load() reaches success with a route', () async {
    final provider = RouteProvider(service: _OkService());
    await provider.load('ED-1');

    expect(provider.state, RouteViewState.success);
    expect(provider.route, isNotNull);
    expect(provider.route!.polylinePoints, isNotEmpty);
    // Successful load starts the courier-position timer; cancel it so it
    // doesn't outlive the test.
    provider.dispose();
  });

  test('load() maps RouteException to the error state', () async {
    final provider = RouteProvider(service: _FailingService());
    await provider.load('ED-1');

    expect(provider.state, RouteViewState.error);
    expect(provider.errorMessage, 'boom');
  });
}
