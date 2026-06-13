import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/order_route.dart';
import 'route_provider.dart';
import 'widgets/order_error_view.dart';

/// Tela do mapa: rota real entre o Centro de Distribuição e o destino.
///
/// Recebe o id do pedido via `Navigator.pushNamed(arguments: '<id>')`,
/// delega o estado ao [RouteProvider] e renderiza o [GoogleMap] no sucesso.
class OrderMapScreen extends StatelessWidget {
  const OrderMapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final orderId =
        ModalRoute.of(context)?.settings.arguments as String? ?? 'ED-99420';

    return ChangeNotifierProvider(
      create: (_) => RouteProvider()..load(orderId),
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: const Text(
            'Rota da Entrega',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 18),
          ),
          leading: IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
        ),
        body: Consumer<RouteProvider>(
          builder: (context, provider, _) {
            switch (provider.state) {
              case RouteViewState.loading:
                return const Center(
                  child: CircularProgressIndicator(color: AppColors.purple),
                );
              case RouteViewState.error:
                return OrderErrorView(
                  message: provider.errorMessage ?? 'Erro desconhecido.',
                  onRetry: provider.retry,
                );
              case RouteViewState.success:
                return _RouteMap(route: provider.route!);
            }
          },
        ),
      ),
    );
  }
}

class _RouteMap extends StatelessWidget {
  final OrderRoute route;

  const _RouteMap({required this.route});

  @override
  Widget build(BuildContext context) {
    final origin = route.origin.latLng;
    final destination = route.destination.latLng;

    return GoogleMap(
      initialCameraPosition: CameraPosition(target: origin, zoom: 10),
      onMapCreated: (controller) {
        controller.animateCamera(
          CameraUpdate.newLatLngBounds(_bounds(origin, destination), 64),
        );
      },
      markers: {
        Marker(
          markerId: const MarkerId('origin'),
          position: origin,
          infoWindow: InfoWindow(title: route.origin.label),
        ),
        Marker(
          markerId: const MarkerId('destination'),
          position: destination,
          infoWindow: InfoWindow(title: route.destination.label),
        ),
      },
      polylines: {
        Polyline(
          polylineId: const PolylineId('route'),
          color: AppColors.purple,
          width: 5,
          points: route.polylinePoints,
        ),
      },
    );
  }

  LatLngBounds _bounds(LatLng a, LatLng b) {
    return LatLngBounds(
      southwest: LatLng(math.min(a.latitude, b.latitude), math.min(a.longitude, b.longitude)),
      northeast: LatLng(math.max(a.latitude, b.latitude), math.max(a.longitude, b.longitude)),
    );
  }
}
